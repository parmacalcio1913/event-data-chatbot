from anthropic.types import MessageParam

from core.claude import Claude
from core.tools import ToolManager
from mcp_client import MCPClient


class Chat:
    def __init__(
        self,
        claude_service: Claude,
        clients: dict[str, MCPClient],
        show_usage: bool = False,
        show_query: bool = False,
    ):
        self.claude_service: Claude = claude_service
        self.clients: dict[str, MCPClient] = clients
        self.messages: list[MessageParam] = []
        self.show_usage = show_usage
        self.show_query = show_query

    async def _process_query(self, query: str):
        self.messages.append({"role": "user", "content": query})

    async def run(
        self,
        query: str,
    ) -> str:
        final_text_response = ""
        self.last_usage = {"input_tokens": 0, "output_tokens": 0}

        await self._process_query(query)

        while True:
            response = self.claude_service.chat(
                messages=self.messages,
                tools=await ToolManager.get_all_tools(self.clients),
            )

            in_tok = response.usage.input_tokens
            out_tok = response.usage.output_tokens
            if self.show_usage:
                print(f"[tokens] in={in_tok} out={out_tok}")
            self.last_usage["input_tokens"] += in_tok
            self.last_usage["output_tokens"] += out_tok

            self.claude_service.add_assistant_message(self.messages, response)

            if response.stop_reason == "tool_use":
                print(self.claude_service.text_from_message(response))
                tool_result_parts = await ToolManager.execute_tool_requests(
                    self.clients, response, show_query=self.show_query
                )

                self.claude_service.add_user_message(self.messages, tool_result_parts)
            else:
                final_text_response = self.claude_service.text_from_message(response)
                break

        return final_text_response
