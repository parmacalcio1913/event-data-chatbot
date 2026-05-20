# Contributing

Thanks for your interest in contributing. This guide covers the dev setup and the conventions the project follows.

## Dev setup

The project uses [uv](https://github.com/astral-sh/uv) for environment and dependency management.

```bash
git clone https://github.com/parmacalcio1913/event-data-chatbot.git
cd event-data-chatbot

uv venv
source .venv/bin/activate
uv sync --group dev          # installs project deps + ruff, mypy, pre-commit, pytest
uv run pre-commit install    # wires git hooks
```

## StatsBomb data

The MCP server reads from a local DuckDB built from StatsBomb open data. Before running the server, populate the database once:

```bash
uv run scripts/download_data.py
```

This pulls competitions, matches, lineups, and events from `github.com/statsbomb/open-data` into `data/statsbomb.duckdb` (~550 MB). The file is gitignored and rebuilt on demand.

Before using StatsBomb data, register at the [StatsBomb resource centre](https://statsbomb.com/resource-centre/). See [ATTRIBUTION.md](ATTRIBUTION.md) for the full attribution requirements.

## Quality gates

These run automatically via `pre-commit` on each commit and again in CI on push/PR. You can also run them manually:

```bash
uv run ruff check .          # lint
uv run ruff format .         # format
uv run mypy .                # type check
uv run pytest                # tests
```

CI is matrixed over Python 3.10, 3.11, and 3.12. Code that passes locally on one version should pass on all three, but the matrix is the final word.

## Branching and PRs

- Branch from `main`. Open a PR back to `main`.
- Keep PRs focused: one logical change per PR. A bug fix and an unrelated refactor are two PRs.
- The PR template will prompt for a summary and a brief test plan — fill both in.
- CI must be green before merge.

## Reporting bugs and proposing features

Use the issue templates in `.github/ISSUE_TEMPLATE/`. For security vulnerabilities, do **not** open a public issue — see [SECURITY.md](SECURITY.md).

## Code conventions

A handful of project-specific rules live in [CLAUDE.md](CLAUDE.md) under "Design decisions" — worth a skim before non-trivial changes. The headline ones:

- The server exposes one general `query` SQL tool rather than many narrow ones. Adding new tools is a design decision, not a default move.
- Column comments and schema documentation are authored in `scripts/download_data.py`, not in the server's tool description.
- The DuckDB connection is opened read-only. The model cannot mutate state.
