from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from policy_tracker.primegov_import import download_la_city_agendas_last_12_months


def main() -> int:
    summary = download_la_city_agendas_last_12_months(
        from_date="05-21-2025",
        to_date="05-21-2026",
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
