from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/db_counts.py <sqlite-path>")
        return 1

    db_path = Path(sys.argv[1]).expanduser().resolve()
    with sqlite3.connect(db_path) as connection:
        for table in ["structured_documents", "structured_agenda_items", "structured_item_topics"]:
            count = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"{table}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
