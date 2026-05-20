from typing import Literal, cast

from anthropic.types import MessageParam
from mcp.types import Prompt, PromptMessage

from core.chat import Chat
from core.claude import Claude
from mcp_client import MCPClient


class CliChat(Chat):
    def __init__(
        self,
        client: MCPClient,
        clients: dict[str, MCPClient],
        claude_service: Claude,
        show_usage: bool = False,
        show_query: bool = False,
    ):
        super().__init__(
            clients=clients,
            claude_service=claude_service,
            show_usage=show_usage,
            show_query=show_query,
        )

        self.client: MCPClient = client

    async def list_prompts(self) -> list[Prompt]:
        return await self.client.list_prompts()

    async def _process_command(self, query: str) -> bool:
        if not query.startswith("/"):
            return False

        words = query.split()
        command = words[0].replace("/", "")

        # Map the positional command arguments to the prompt's declared
        # argument names — they are not always called "doc_id".
        prompts = await self.client.list_prompts()
        prompt = next((p for p in prompts if p.name == command), None)
        if prompt is None:
            raise ValueError(f"Unknown command: /{command}")

        arg_names = [arg.name for arg in (prompt.arguments or [])]
        # strict=False: extra positional args are intentionally ignored; missing
        # ones simply don't get filled.
        args = dict(zip(arg_names, words[1:], strict=False))

        messages = await self.client.get_prompt(command, args)

        self.messages += convert_prompt_messages_to_message_params(messages)
        return True

    async def _process_query(self, query: str):
        if await self._process_command(query):
            return

        self.messages.append({"role": "user", "content": query})


def convert_prompt_message_to_message_param(
    prompt_message: "PromptMessage",
) -> MessageParam:
    role: Literal["user", "assistant"] = cast(
        Literal["user", "assistant"],
        "user" if prompt_message.role == "user" else "assistant",
    )

    content = prompt_message.content

    # Check if content is a dict-like object with a "type" field
    if isinstance(content, dict) or hasattr(content, "__dict__"):
        content_type = (
            content.get("type", None)
            if isinstance(content, dict)
            else getattr(content, "type", None)
        )
        if content_type == "text":
            content_text = (
                content.get("text", "")
                if isinstance(content, dict)
                else getattr(content, "text", "")
            )
            return {"role": role, "content": content_text}

    if isinstance(content, list):
        text_blocks = []
        for item in content:
            # Check if item is a dict-like object with a "type" field
            if isinstance(item, dict) or hasattr(item, "__dict__"):
                item_type = (
                    item.get("type", None)
                    if isinstance(item, dict)
                    else getattr(item, "type", None)
                )
                if item_type == "text":
                    item_text = (
                        item.get("text", "")
                        if isinstance(item, dict)
                        else getattr(item, "text", "")
                    )
                    text_blocks.append({"type": "text", "text": item_text})

        if text_blocks:
            return {"role": role, "content": text_blocks}

    return {"role": role, "content": ""}


def convert_prompt_messages_to_message_params(
    prompt_messages: list[PromptMessage],
) -> list[MessageParam]:
    return [convert_prompt_message_to_message_param(msg) for msg in prompt_messages]
