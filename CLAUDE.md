# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A CLI chatbot built on the Anthropic API and MCP (Model Context Protocol). The MCP server exposes a local [StatsBomb open-data](https://github.com/statsbomb/open-data) snapshot as a DuckDB database, and offers the model a single SQL tool plus one prompt template for writing match summaries.

## Setup & Running

Requires `.env` with:
```
ANTHROPIC_API_KEY=sk-...
CLAUDE_MODEL=claude-sonnet-4-6   # or any valid model ID
```

Install and run:
```bash
uv venv && source .venv/activate
uv pip install -e .

# One-shot: download StatsBomb data into data/statsbomb.duckdb (~550 MB).
# Re-run only when you want to refresh the snapshot.
uv run scripts/download_data.py

uv run main.py                    # starts the interactive CLI
```

Test the MCP client in isolation:
```bash
uv run mcp_client.py
```

There are no automated tests or linters configured.

## Architecture

The system has two independent processes that communicate over stdio via the MCP protocol.

**MCP Server** (`mcp_server.py`)
A `FastMCP` server backed by a local DuckDB file (`data/statsbomb.duckdb`). It exposes:
- One tool, `query(sql)` — runs a read-only `SELECT` against the DuckDB. The events table schema is rendered once at server startup by `StatsBomb.events_schema()` and baked into the tool description, so the model never has to inspect the table at request time. Results are capped at `MAX_RESULT_ROWS = 1000` and the response includes a `truncated` flag when the cap is hit.
- One prompt, `summary(match_id)` — returns a user message instructing Claude to write a structured match report, with the exact `matches`/`lineups`/`events` queries it is allowed to run embedded inline.

The DuckDB file is populated by `scripts/download_data.py`, which pulls competitions, matches, lineups, and events through `statsbombpy`, flattens StatsBomb location arrays into `*_x` / `*_y` / `*_z` columns, drops blob/array columns that don't belong in a flat SQL table, and writes column comments that ship as part of the schema description.

**MCP Client + Agentic Loop** (`mcp_client.py`, `core/`)
- `MCPClient` — wraps `mcp.ClientSession`; exposes `list_tools`, `call_tool`, `list_prompts`, `get_prompt`. No resource API: the server doesn't expose resources.
- `core/statsbomb.py` (`StatsBomb`) — DuckDB wrapper used by the server. Opens the database read-only, executes a query, JSON-serializes the result (dates → ISO strings, `Decimal` → `float`), and caps row count. Also renders the events schema (table comment + per-column comments) into the text block consumed by the tool description.
- `core/claude.py` (`Claude`) — thin wrapper around `anthropic.Anthropic`; handles message construction and the optional extended thinking parameter.
- `core/chat.py` (`Chat`) — base agentic loop: sends messages to Claude, handles `tool_use` stop reason by calling `ToolManager.execute_tool_requests`, loops until `end_turn`. Prints per-turn token usage to stdout.
- `core/cli_chat.py` (`CliChat`) — extends `Chat`; routes `/command arg1 arg2 ...` inputs through MCP prompts (positional args are zipped onto the prompt's declared argument names), then delegates to the base loop.
- `core/tools.py` (`ToolManager`) — aggregates tools from all connected `MCPClient` instances and dispatches `tool_use` blocks to the correct client.
- `core/cli.py` (`CliApp`) — `prompt_toolkit` REPL; `UnifiedCompleter` provides Tab completion for `/commands` (MCP prompts); `CommandAutoSuggest` shows the first argument name inline as a hint.

**Startup flow** (`main.py`): creates one `MCPClient` for `mcp_server.py` plus one per extra script passed on the command line, wires them all into `CliChat`, then runs `CliApp`.

## Design decisions

These shape how new code should be written for this project.

- **Single SQL tool, not a tool taxonomy.** The server exposes one general `query` tool rather than many narrow ones (`get_match_summary`, `get_shot_map`, etc.). The cost — the model has to know SQL and the schema — is paid once via the static description baked into the tool. The win is flexibility: any analytical question is answerable without server changes. Adding new narrow tools should only happen when the SQL approach genuinely can't express the workflow.
- **Schema as static text, not catalog queries.** The events table is wide (~80 columns). Letting the model run `DESCRIBE events` per conversation wastes context. `StatsBomb.events_schema()` is called once at import time and the resulting text is concatenated into `QUERY_DESCRIPTION`. The data-loading script (`scripts/download_data.py`) is where column comments are authored — keep schema documentation there, not in the tool description code.
- **DuckDB on disk, not `statsbombpy` at request time.** Data is downloaded once into `data/statsbomb.duckdb` (~550 MB, gitignored). The server has no network dependency and no per-request caching layer to maintain. The trade-off is that refreshing the snapshot is a manual rerun of the download script.
- **Read-only by construction.** `StatsBomb` opens the DuckDB connection with `read_only=True`. The model cannot mutate state.
- **Result size is capped, not unlimited.** Every query goes through `MAX_RESULT_ROWS` (1000) and surfaces a `truncated` flag. The tool description tells the model to prefer aggregates over raw rows, but the cap is the hard backstop.
- **Errors surface as MCP error responses with actionable messages.** Don't swallow exceptions silently in the tool path — the model needs to see what went wrong to recover.
- **Under the local stdio model, model-written SQL runs with the user's own privileges against their own data — no trust boundary, no sandbox needed.** If a network transport is ever added, the `query` tool must be sandboxed (`enable_external_access=false`, `lock_configuration=true`) first.
