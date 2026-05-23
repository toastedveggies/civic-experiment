from __future__ import annotations

from datetime import datetime


DATE_FORMATS = (
    "%Y-%m-%d",
    "%B %d, %Y",
    "%A, %B %d, %Y",
    "%m/%d/%Y",
)


def normalize_meeting_date_iso(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = " ".join(str(value).strip().split())
    if not cleaned:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).date().isoformat()
        except ValueError:
            continue
    return None
