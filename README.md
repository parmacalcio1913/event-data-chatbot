# Event Data Chatbot

A CLI chatbot that lets you ask Claude analytical questions about football event data — *"Who scored the most goals in the 2015/2016 La Liga?"*, *"Compare Barcelona's home and away xG"*, and so on. Under the hood, an MCP (Model Context Protocol) server exposes a local StatsBomb open-data snapshot as a single read-only SQL tool; Claude writes the queries against the underlying DuckDB, you just chat.

## Data source

This project queries [StatsBomb open data](https://github.com/statsbomb/open-data). If you publish analysis based on this data you must credit **StatsBomb** and display their logo — see [ATTRIBUTION.md](ATTRIBUTION.md) for full requirements. Before using the data, register at the [StatsBomb resource centre](https://statsbomb.com/resource-centre/).

## Prerequisites

- Python 3.9+
- Anthropic API Key

## Setup

### Step 1: Configure the environment variables

1. Create or edit the `.env` file in the project root and verify that the following variables are set correctly:

```
ANTHROPIC_API_KEY=""  # Enter your Anthropic API secret key
```

### Step 2: Install dependencies

[uv](https://github.com/astral-sh/uv) is a fast Python package installer and resolver.

1. Install uv, if not already installed:

```bash
pip install uv
```

2. Clone the repository:

```bash
git clone https://github.com/parmacalcio1913/event-data-chatbot.git
cd event-data-chatbot
```

3. Create and activate a virtual environment:

```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

4. Install dependencies:

```bash
uv pip install -e .
```

5. Run the project

```bash
uv run main.py
```

## Usage

### Basic Interaction

Type your question and press Enter. For example, ask:

```
> Who scored the most goals in the 2015/2016 Premier League?
```

Under the hood:

1. The orchestration loop (`Chat.run()` in [core/chat.py](core/chat.py)) receives your message. Before each call to Claude it collects every MCP tool exposed by every connected server via `ToolManager.get_all_tools()` ([core/tools.py](core/tools.py)).
2. `ToolManager.get_all_tools()` calls `MCPClient.list_tools()` on each client ([mcp_client.py](mcp_client.py)), which sends a `ListToolsRequest` to the corresponding MCP server. The server returns the registered tools — here, just the `query` SQL tool defined in [mcp_server.py](mcp_server.py). Its description includes the full StatsBomb events schema, so Claude already knows what columns exist without inspecting the catalog at request time.
3. `Chat.run()` calls `Claude.chat(messages=..., tools=...)` ([core/claude.py](core/claude.py)), forwarding your question along with the available tools. Claude decides the question needs data, formulates a SQL statement, and asks to call the `query` tool.
4. Claude returns `stop_reason == "tool_use"`. `Chat.run()` detects this and calls `ToolManager.execute_tool_requests()`, which finds the client that owns `query` and calls `MCPClient.call_tool("query", {"sql": "..."})`.
5. The MCP server runs the SQL against the local DuckDB via `StatsBomb.query()` ([core/statsbomb.py](core/statsbomb.py)), JSON-serializes the result (dates → ISO strings, `Decimal` → `float`), and returns up to 1000 rows with a `truncated` flag. Errors come back as MCP error responses with the SQL exception message attached.
6. `Chat.run()` appends the tool result as a user message and loops back to call Claude again (step 3) — this time with the result in the conversation history. Claude either produces a final answer (`stop_reason == "end_turn"`) or asks to call the tool again with a refined query.

The same loop handles multi-step questions naturally: Claude may issue a small exploratory query first ("what competition names exist in the database?"), look at the answer, then issue a follow-up aggregation query — all within one user turn.



### Commands

Use the `/` prefix to invoke an MCP prompt defined on the server. This project exposes one — `summary` — which produces a structured match report. Pass the match ID as a positional argument:

```
> /summary 3877313
```

Under the hood:

1. `CliApp.run()` ([core/cli.py](core/cli.py)) reads the input and forwards it to `CliChat.run()`. `CliChat._process_query()` delegates first to `_process_command()` ([core/cli_chat.py](core/cli_chat.py)).
2. `_process_command()` notices the leading `/`, splits the input into a command name (`summary`) and its positional arguments (`["3877313"]`), and looks up the corresponding `Prompt` definition via `MCPClient.list_prompts()`. It zips the positional args onto the prompt's declared argument names — the server's `summary` prompt declares one argument called `match_id`, so this becomes `{"match_id": "3877313"}`.
3. `MCPClient.get_prompt("summary", {"match_id": "3877313"})` ([mcp_client.py](mcp_client.py)) sends a `GetPromptRequest` to the MCP server. The server's `summary` handler ([mcp_server.py](mcp_server.py)) renders the pre-built report template — instructions plus the exact `matches` / `lineups` / `events` SQL queries Claude is allowed to run — and returns it as a sequence of `PromptMessage` objects.
4. Those messages are converted into Anthropic `MessageParam` objects by `convert_prompt_messages_to_message_params()` and appended to the conversation history.
5. `_process_command()` returns `True`, signalling that the user input has already been turned into messages. `Chat.run()` then calls Claude with the pre-built conversation — Claude executes the prescribed queries via the `query` tool and writes the report.

Tab completion is provided by `UnifiedCompleter` ([core/cli.py](core/cli.py)): typing `/` opens a menu of the prompts exposed by the connected servers. Once a command name is in place, `CommandAutoSuggest` shows the first declared argument name (e.g. `match_id`) inline as a hint.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full dev guide. In short:

```bash
uv sync --group dev          # installs ruff, mypy, pre-commit, pytest
uv run pre-commit install    # wires git hooks
```

The four quality gates can be run manually:

```bash
uv run ruff check .          # lint
uv run ruff format .         # format
uv run mypy .                # type check
uv run pytest                # tests
```

CI runs the same four checks on push and on every PR against `main`, matrixed over Python 3.10, 3.11, and 3.12.

## Security

If you find a vulnerability, please **do not** open a public issue. See [SECURITY.md](SECURITY.md) for the private reporting channel and the project's threat model.

## License

MIT — see [LICENSE](LICENSE). The MIT license covers the code in this repository only; StatsBomb data remains subject to the [StatsBomb user agreement](https://github.com/statsbomb/open-data/blob/master/LICENSE.pdf).
