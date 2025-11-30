"""Utility functions for URL normalization, filtering, and deduplication."""

import re
from typing import Set, Tuple
from urllib.parse import urljoin, urlparse


def normalize_url(base_url: str, url: str) -> str:
    """Convert relative URL to absolute, or return absolute URL as-is."""
    if not url:
        return ""
    parsed = urlparse(url)
    if parsed.scheme in ("http", "https"):
        return url
    return urljoin(base_url, url)


def is_pdf_url(url: str) -> bool:
    """Check if URL points to a PDF file."""
    if not url:
        return False
    url_lower = url.lower()
    return url_lower.endswith(".pdf") or ".pdf" in url_lower


def extract_filename(url: str) -> str:
    """Extract filename from URL."""
    if not url:
        return ""
    parsed = urlparse(url)
    path = parsed.path
    if "/" in path:
        return path.rsplit("/", 1)[-1]
    return path or "unknown.pdf"


def filter_agenda_pdfs(link_text: str, filename: str) -> bool:
    """Check if link text or filename contains 'agenda' (case-insensitive)."""
    text = f"{link_text} {filename}".lower()
    return bool(re.search(r"agenda", text, flags=re.I))


def filter_cancellations(link_text: str, filename: str) -> bool:
    """Check if link text or filename contains 'cancel' (case-insensitive)."""
    text = f"{link_text} {filename}".lower()
    return bool(re.search(r"cancel", text, flags=re.I))


def dedupe_records(records: list[dict]) -> list[dict]:
    """Remove duplicate records based on (group, link_text, url) tuple."""
    seen: Set[Tuple[str, str, str]] = set()
    unique_records = []
    for record in records:
        key = (
            record.get("group", ""),
            record.get("link_text", ""),
            record.get("url", ""),
        )
        if key not in seen:
            seen.add(key)
            unique_records.append(record)
    return unique_records


def is_meeting_detail_link(url: str, link_text: str) -> bool:
    """Check if link appears to be a meeting detail page (not a PDF)."""
    if is_pdf_url(url):
        return False
    url_lower = url.lower()
    text_lower = link_text.lower()
    return (
        "/meeting/" in url_lower
        or "agenda" in text_lower
        or "meeting" in text_lower
    )

