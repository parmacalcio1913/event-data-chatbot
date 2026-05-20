import datetime
from decimal import Decimal
from pathlib import Path

import duckdb

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "statsbomb.duckdb"
MAX_RESULT_ROWS = 1000


def _jsonable(value):
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


class StatsBomb:
    def __init__(self, db_path: str | Path | None = None):
        path = Path(db_path) if db_path is not None else DB_PATH
        if not path.exists():
            raise FileNotFoundError(
                f"Database not found at {path}. "
                "Run `uv run scripts/download_data.py` to create it."
            )
        self._conn = duckdb.connect(str(path), read_only=True)

    def query(self, sql: str) -> dict:
        cursor = self._conn.execute(sql)
        columns = [col[0] for col in cursor.description]
        fetched = cursor.fetchmany(MAX_RESULT_ROWS + 1)
        truncated = len(fetched) > MAX_RESULT_ROWS
        rows = [
            {col: _jsonable(val) for col, val in zip(columns, row, strict=True)}
            for row in fetched[:MAX_RESULT_ROWS]
        ]
        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "truncated": truncated,
        }

    def events_schema(self) -> str:
        """Render the events table schema as a static text block.

        Called once at server startup so the schema can be baked into the
        query tool's description — the model never has to inspect the table
        at request time (which dumped ~80 catalog rows into context per
        conversation).
        """
        table_comment = self._conn.execute(
            "SELECT comment FROM duckdb_tables() WHERE table_name = 'events'"
        ).fetchone()
        columns = self._conn.execute(
            """
            SELECT column_name, data_type, comment
            FROM duckdb_columns()
            WHERE table_name = 'events'
            ORDER BY column_index
            """
        ).fetchall()

        lines: list[str] = []
        if table_comment and table_comment[0]:
            lines.append(table_comment[0])
            lines.append("")
        for name, data_type, comment in columns:
            line = f"  {name} {data_type}"
            if comment:
                line += f" — {comment}"
            lines.append(line)
        return "\n".join(lines)
