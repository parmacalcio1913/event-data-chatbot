# Security Policy

## Supported versions

This project is at version 0.x. Only the latest tagged release on `main` is supported; older releases will not receive security fixes.

## Reporting a vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.** Report them privately by email:

**analytics@parmacalcio1913.com**

When reporting, include:
- A description of the vulnerability and its impact.
- Steps to reproduce, or a proof of concept.
- Affected version (commit SHA or release tag).
- Your name and contact, if you'd like to be credited.

You can expect:
- An acknowledgement within 5 business days.
- A status update within 14 days.
- Coordinated disclosure once a fix is ready, with credit to the reporter unless they prefer to remain anonymous.

## Threat model

This server is designed to run as a local stdio MCP server invoked by the user's own MCP client. Under that deployment:

- **Model-written SQL runs with the user's own privileges, against their own data.** There is no trust boundary between the model and the host. The DuckDB connection is opened read-only, so the model cannot mutate state; this is a hardening choice, not a security boundary.
- **The MCP server has no network listeners and no per-request external calls.** The only network access is the one-shot data download via `scripts/download_data.py`, which contacts `github.com` for StatsBomb open data.
- **The `query` tool currently accepts arbitrary SELECT statements.** This is acceptable under the local-stdio threat model. If a network transport is ever added (HTTP, SSE), the `query` tool **must** be sandboxed first — at minimum `enable_external_access=false` and `lock_configuration=true` on the DuckDB connection — before exposure.

## Out of scope

The following are not considered vulnerabilities in this project:
- The model writing SQL that consumes resources or hits the result-row cap (`MAX_RESULT_ROWS = 1000`). This is by design.
- Behavior of upstream dependencies (`anthropic`, `mcp`, `duckdb`, `statsbombpy`) — report those to their respective projects.
- Issues that require an attacker to already have local code execution as the user.
