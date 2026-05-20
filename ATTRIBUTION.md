# Attribution

## Data source

This project queries data from the [StatsBomb open data](https://github.com/statsbomb/open-data) project. StatsBomb makes a subset of their event data freely available for non-commercial research and educational purposes.

## Required attribution

If you publish analysis produced with this tool, the [StatsBomb user agreement](https://github.com/statsbomb/open-data/blob/master/LICENSE.pdf) requires you to:

1. State the data source as **StatsBomb**.
2. Display the StatsBomb logo alongside any visualisation or published analysis. The logo is available from the [StatsBomb resource centre](https://statsbomb.com/resource-centre/).
3. Register at the [StatsBomb resource centre](https://statsbomb.com/resource-centre/) before using the data.

## What this project does and does not redistribute

This repository **does not** vendor or redistribute StatsBomb event data. The local DuckDB database produced by `scripts/download_data.py` is built on the user's own machine by pulling from `github.com/statsbomb/open-data` at runtime and is excluded from version control.

The only StatsBomb-derived content that ships in this repository is a small set of redacted fixture rows used by the test suite. Each fixture file documents the match it was derived from.

## This project's own license

The code in this repository is released under the MIT License — see [LICENSE](LICENSE). The MIT license applies to the code only and does **not** extend to the StatsBomb data, which remains subject to the StatsBomb user agreement.