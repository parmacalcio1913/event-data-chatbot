# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
- Attributing Anthropic's course material

### Fixed
- Bug in versioning

## [0.2.0]
### Added
- Parameters (`--query`, `--usage`) when running `uv run main.py`

## [0.1.0]

### Added
- MCP server (`mcp_server.py`) exposing a single read-only `query` SQL tool over a local StatsBomb DuckDB snapshot, with the events table schema baked into the tool description.
- MCP prompt `summary(match_id)` producing a structured match report using a fixed set of allowed queries against the `matches`, `lineups`, and `events` tables.
- One-shot data loader (`scripts/download_data.py`) that pulls competitions, matches, lineups, and events through `statsbombpy`, flattens StatsBomb location arrays into `*_x`/`*_y`/`*_z` columns, and writes column comments consumed by the schema description.
- CLI host (`main.py` + `core/`) with `prompt_toolkit`-based REPL, `/command` tab completion, and inline argument hints.
- MIT license, StatsBomb attribution document, and gitignore coverage for build artifacts and tool caches.
