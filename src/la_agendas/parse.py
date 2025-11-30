"""Date parsing utilities."""

import re
from datetime import datetime
from typing import Optional


def parse_date(link_text: str, filename: str) -> str:
    """
    Parse date from link text or filename.
    Returns YYYY-MM-DD or 'unknown_date'.
    """
    # Try link text first, then filename
    for text in [link_text, filename]:
        if not text:
            continue
        date_str = _extract_date_from_text(text)
        if date_str:
            return date_str
    return "unknown_date"


def _extract_date_from_text(text: str) -> Optional[str]:
    """Extract date from text using multiple patterns."""
    if not text:
        return None

    # Pattern 1: "October 15, 2025" or "Oct 15, 2025"
    month_names = [
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
    ]
    month_abbrevs = [
        "jan",
        "feb",
        "mar",
        "apr",
        "may",
        "jun",
        "jul",
        "aug",
        "sep",
        "oct",
        "nov",
        "dec",
    ]

    # Full month name pattern
    for i, month in enumerate(month_names + month_abbrevs, 1):
        pattern = rf"{month}\s+(\d{{1,2}}),?\s+(\d{{4}})"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            day = int(match.group(1))
            year = int(match.group(2))
            month_num = i if i <= 12 else (i - 12)
            try:
                date_obj = datetime(year, month_num, day)
                return date_obj.strftime("%Y-%m-%d")
            except ValueError:
                continue

    # Pattern 2: "10/15/2025" or "10-15-2025" or "10.15.2025"
    patterns = [
        r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})",  # MM/DD/YYYY or MM-DD-YYYY
        r"(\d{1,2})\.(\d{1,2})\.(\d{4})",  # MM.DD.YYYY
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            month = int(match.group(1))
            day = int(match.group(2))
            year = int(match.group(3))
            try:
                date_obj = datetime(year, month, day)
                return date_obj.strftime("%Y-%m-%d")
            except ValueError:
                continue

    # Pattern 3: "10/15/25" or "10-15-25" (2-digit year, assume 20yy)
    patterns_2digit = [
        r"(\d{1,2})[/-](\d{1,2})[/-](\d{2})\b",  # MM/DD/YY
        r"(\d{1,2})\.(\d{1,2})\.(\d{2})\b",  # MM.DD.YY
    ]
    for pattern in patterns_2digit:
        match = re.search(pattern, text)
        if match:
            month = int(match.group(1))
            day = int(match.group(2))
            year_2digit = int(match.group(3))
            year = 2000 + year_2digit if year_2digit < 100 else year_2digit
            try:
                date_obj = datetime(year, month, day)
                return date_obj.strftime("%Y-%m-%d")
            except ValueError:
                continue

    return None

