# Sample queries

A handful of natural-language prompts that exercise the server well. They assume the default data slice loaded by `scripts/download_data.py`: the Big 5 European leagues (Premier League, La Liga, Bundesliga, Serie A, Ligue 1) for the **2015/2016** season.

Paste any of these into your MCP client (Claude Desktop, the included CLI, etc.) once the server is connected.

## Quick aggregates

These exercise the `query` SQL tool with simple GROUP BY logic — fast, cheap, and a good first check that the server is alive.

> Which team scored the most goals across all five leagues in 2015/2016?

> What were the five biggest wins (by goal difference) of the 2015/2016 season?

> Show me the most common shot outcomes in the 2015/2016 Premier League.

## Player-level analysis

These join `events` to itself or to `lineups`, and stress the model's understanding of the events schema.

> Who took the most shots from inside the penalty box in La Liga 2015/2016, and what was their conversion rate?

> Rank the top 10 players by total expected goals (`shot_statsbomb_xg`) across all five leagues, excluding penalties.

> Which midfielders had the highest pass completion rate in the Bundesliga, minimum 500 attempted passes?

## Tactical / match-level

These usually require multiple aggregations and a coherent narrative — good for stretching the model on a single SQL tool.

> Compare Barcelona's home and away performance in La Liga 2015/2016: goals scored, goals conceded, average xG for and against.

> Find Serie A matches where the home team trailed by 2+ goals at half-time but won.

> What time of the match (5-minute bins) saw the most goals in the 2015/2016 Premier League?

## Match summary (uses the `summary` prompt)

The server also exposes a prompt called `summary` that produces a structured match report. Invoke it via the `/summary <match_id>` command in the included CLI, or by selecting it in a client that surfaces MCP prompts.

> /summary 3877313

To find a valid `match_id`, ask first:

> Give me 3 interesting match IDs from the 2015/2016 Premier League, picked for being high-scoring or close finishes.

## Things the model is *not* expected to do well

- **Questions outside the loaded data slice.** Asking about 2018/2019 or about MLS will produce empty results (correctly) or hallucinated reasoning (incorrectly). Stick to the Big 5, 2015/2016.
- **Per-event raw dumps.** The tool is capped at `MAX_RESULT_ROWS = 1000`. If you ask for "every pass in this match," expect truncation. Aggregate or filter instead.
- **xG-explainer-style narrative.** The data has `shot_statsbomb_xg` but no explanation of how it was computed. The model can describe relative values, not the underlying model.
