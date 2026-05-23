from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from policy_tracker.la_county_ceo_import import download_county_ceo_agendas

REQUESTED_BODIES = [
    "Community Services Cluster",
    "Operations Cluster",
    "Family and Social Services Cluster",
    "Health and Mental Health Services Cluster",
    "Public Safety Cluster",
    "Homelessness and Housing Cluster",
    "Affordable Housing",
    "Community Care and Justice",
    "Executive Committee for Regional Homeless Alignment",
    "LACTA Board Deputies",
    "Leadership Table for Regional Homeless Alignment",
    "Real Estate Management Commission",
]


def main() -> int:
    today = date.today()
    from_date = today - timedelta(days=365)
    summary = download_county_ceo_agendas(
        requested_bodies=REQUESTED_BODIES,
        from_date=from_date,
        to_date=today,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
