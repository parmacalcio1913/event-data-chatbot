"""Synthetic DuckDB fixtures for the StatsBomb wrapper tests.

The fixture is built from synthetic data, not StatsBomb. The shape only needs
to satisfy what the StatsBomb wrapper itself touches — an `events` table with
table + column comments (for `events_schema()`) and enough rows to exercise
the `MAX_RESULT_ROWS` cap. The full ~80-column events schema produced by
`scripts/download_data.py` is out of scope here.
"""

from pathlib import Path

import duckdb
import pytest


def _build_fixture_db(db_path: Path) -> None:
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE events (
                event_id INTEGER,
                minute INTEGER,
                player VARCHAR,
                team VARCHAR,
                type VARCHAR,
                shot_statsbomb_xg DECIMAL(5, 3),
                event_date DATE
            )
            """
        )
        conn.execute("COMMENT ON TABLE events IS 'Synthetic events table for tests.'")
        conn.execute(
            "COMMENT ON COLUMN events.type IS 'Event type, e.g. Shot or Pass.'"
        )
        conn.execute(
            "COMMENT ON COLUMN events.shot_statsbomb_xg "
            "IS 'Expected goals for the shot.'"
        )
        # 1010 rows so the MAX_RESULT_ROWS=1000 cap is exercised.
        conn.execute(
            """
            INSERT INTO events
            SELECT
                i AS event_id,
                (i % 90) + 1 AS minute,
                'Player ' || i AS player,
                CASE WHEN i % 2 = 0 THEN 'Home FC' ELSE 'Away FC' END AS team,
                CASE WHEN i % 5 = 0 THEN 'Shot' ELSE 'Pass' END AS type,
                CASE WHEN i % 5 = 0 THEN 0.123 ELSE NULL END AS shot_statsbomb_xg,
                DATE '2024-01-15' AS event_date
            FROM range(1, 1011) AS t(i)
            """
        )
    finally:
        conn.close()


@pytest.fixture(scope="session")
def fixture_db_path(tmp_path_factory) -> Path:
    db_path = tmp_path_factory.mktemp("statsbomb_fixture") / "test.duckdb"
    _build_fixture_db(db_path)
    return db_path
