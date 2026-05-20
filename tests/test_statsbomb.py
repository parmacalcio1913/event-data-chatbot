from pathlib import Path

import pytest

from core.statsbomb import MAX_RESULT_ROWS, StatsBomb


@pytest.fixture
def sb(fixture_db_path: Path) -> StatsBomb:
    return StatsBomb(db_path=fixture_db_path)


def test_init_raises_when_db_missing(tmp_path: Path) -> None:
    missing = tmp_path / "nope.duckdb"
    with pytest.raises(FileNotFoundError):
        StatsBomb(db_path=missing)


def test_query_returns_columns_rows_and_metadata(sb: StatsBomb) -> None:
    result = sb.query("SELECT 1 AS one, 'a' AS letter")

    assert result["columns"] == ["one", "letter"]
    assert result["rows"] == [{"one": 1, "letter": "a"}]
    assert result["row_count"] == 1
    assert result["truncated"] is False


def test_query_caps_at_max_result_rows(sb: StatsBomb) -> None:
    # The fixture has 1010 events; the cap is 1000.
    result = sb.query("SELECT event_id FROM events ORDER BY event_id")

    assert result["row_count"] == MAX_RESULT_ROWS
    assert len(result["rows"]) == MAX_RESULT_ROWS
    assert result["truncated"] is True


def test_query_does_not_truncate_when_under_cap(sb: StatsBomb) -> None:
    result = sb.query("SELECT event_id FROM events LIMIT 5")

    assert result["row_count"] == 5
    assert result["truncated"] is False


def test_query_serializes_date_as_iso_string(sb: StatsBomb) -> None:
    result = sb.query("SELECT DATE '2024-01-15' AS d")

    assert result["rows"][0]["d"] == "2024-01-15"


def test_query_serializes_decimal_as_float(sb: StatsBomb) -> None:
    result = sb.query("SELECT CAST(0.123 AS DECIMAL(5, 3)) AS xg")
    value = result["rows"][0]["xg"]

    assert isinstance(value, float)
    assert value == pytest.approx(0.123)


def test_events_schema_includes_table_comment(sb: StatsBomb) -> None:
    schema = sb.events_schema()

    assert "Synthetic events table for tests." in schema


def test_events_schema_lists_columns_with_comments(sb: StatsBomb) -> None:
    schema = sb.events_schema()

    # Column appears with its data type and its comment.
    assert "type VARCHAR" in schema
    assert "Event type, e.g. Shot or Pass." in schema
    assert "Expected goals for the shot." in schema


def test_events_schema_preserves_column_order(sb: StatsBomb) -> None:
    schema = sb.events_schema()
    # The fixture defines columns in this order; the schema renderer must
    # emit them in `column_index` order, not alphabetical.
    pos_event_id = schema.index("event_id ")
    pos_minute = schema.index("minute ")
    pos_player = schema.index("player ")
    assert pos_event_id < pos_minute < pos_player
