from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from policy_tracker.runtime_config import load_runtime_config


def main() -> int:
    args = sys.argv[1:]
    if len(args) > 1:
        print("Usage: python scripts/init_db.py [<sqlite-path>]")
        return 1

    if args:
        db_path = Path(args[0]).expanduser().resolve()
    else:
        db_path = load_runtime_config().database_path.resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    schema_path = REPO_ROOT / "sql" / "schema_v1.sql"
    schema_sql = schema_path.read_text(encoding="utf-8")

    with sqlite3.connect(db_path) as connection:
        connection.executescript(schema_sql)

    print(f"Initialized database at {db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
