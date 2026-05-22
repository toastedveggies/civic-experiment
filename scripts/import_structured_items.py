from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from policy_tracker.sqlite_import import import_items_index


def main() -> int:
    args = sys.argv[1:]
    if not args or len(args) > 2:
        print("Usage: python scripts/import_structured_items.py <index-path> [<sqlite-path>]")
        return 1

    index_path = Path(args[0]).expanduser().resolve()
    db_path = Path(args[1]).expanduser().resolve() if len(args) == 2 else None

    summary = import_items_index(index_path=index_path, db_path=db_path)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
