from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/init_db.py <sqlite-path>")
        return 1

    db_path = Path(sys.argv[1]).expanduser().resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    schema_path = Path(__file__).resolve().parents[1] / "sql" / "schema_v1.sql"
    schema_sql = schema_path.read_text(encoding="utf-8")

    with sqlite3.connect(db_path) as connection:
        connection.executescript(schema_sql)

    print(f"Initialized database at {db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
