from __future__ import annotations

import json
import os
from datetime import date, timedelta

from policy_tracker.la_county_bos_import import download_bos_agendas_last_year


def main() -> int:
    today = date.today()
    summary = download_bos_agendas_last_year(
        from_date=today - timedelta(days=365),
        to_date=today,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUTF8", "1")
    raise SystemExit(main())
