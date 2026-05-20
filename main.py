import argparse
import asyncio
import os
from contextlib import AsyncExitStack

from dotenv import load_dotenv

from core.claude import Claude
from core.cli import CliApp
from core.cli_chat import CliChat
from mcp_client import MCPClient

load_dotenv()

# Anthropic Config
claude_model = os.getenv("CLAUDE_MODEL", "")
anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "")


assert claude_model, "Error: CLAUDE_MODEL cannot be empty. Update .env"
assert anthropic_api_key, "Error: ANTHROPIC_API_KEY cannot be empty. Update .env"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="StatsBomb MCP chatbot CLI.")
    parser.add_argument(
        "--usage",
        action="store_true",
        help="Print Anthropic token usage per turn and a running total.",
    )
    parser.add_argument(
        "--query",
        action="store_true",
        help="Print each tool call with its input (e.g. the SQL sent to the query tool).",
    )
    parser.add_argument(
        "server_scripts",
        nargs="*",
        help="Optional extra MCP server scripts to launch alongside mcp_server.py.",
    )
    return parser.parse_args()


async def main():
    cli_args = parse_args()
    claude_service = Claude(model=claude_model)

    clients = {}

    command, args = ("uv", ["run", "mcp_server.py"])

    async with AsyncExitStack() as stack:
        client = await stack.enter_async_context(MCPClient(command=command, args=args))
        clients["main"] = client

        for i, server_script in enumerate(cli_args.server_scripts):
            client_id = f"client_{i}_{server_script}"
            clients[client_id] = await stack.enter_async_context(
                MCPClient(command="uv", args=["run", server_script])
            )

        chat = CliChat(
            client=client,
            clients=clients,
            claude_service=claude_service,
            show_usage=cli_args.usage,
            show_query=cli_args.query,
        )

        cli = CliApp(chat, show_usage=cli_args.usage)
        await cli.initialize()
        await cli.run()


if __name__ == "__main__":
    asyncio.run(main())
