"""Tests for date parsing."""

import pytest

from la_agendas.parse import parse_date


def test_parse_date_full_month_name():
    """Test parsing dates with full month names."""
    assert parse_date("October 15, 2025", "") == "2025-10-15"
    assert parse_date("January 1, 2024", "") == "2024-01-01"
    assert parse_date("December 31, 2023", "") == "2023-12-31"


def test_parse_date_abbreviated_month():
    """Test parsing dates with abbreviated month names."""
    assert parse_date("Oct 15, 2025", "") == "2025-10-15"
    assert parse_date("Jan 1, 2024", "") == "2024-01-01"


def test_parse_date_slash_format():
    """Test parsing dates in MM/DD/YYYY format."""
    assert parse_date("10/15/2025", "") == "2025-10-15"
    assert parse_date("1/1/2024", "") == "2024-01-01"
    assert parse_date("12/31/2023", "") == "2023-12-31"


def test_parse_date_dash_format():
    """Test parsing dates in MM-DD-YYYY format."""
    assert parse_date("10-15-2025", "") == "2025-10-15"
    assert parse_date("1-1-2024", "") == "2024-01-01"


def test_parse_date_dot_format():
    """Test parsing dates in MM.DD.YYYY format."""
    assert parse_date("10.15.2025", "") == "2025-10-15"
    assert parse_date("1.1.2024", "") == "2024-01-01"


def test_parse_date_2digit_year():
    """Test parsing dates with 2-digit years."""
    assert parse_date("10/15/25", "") == "2025-10-15"
    assert parse_date("1/1/24", "") == "2024-01-01"


def test_parse_date_from_filename():
    """Test parsing date from filename when link text has no date."""
    assert parse_date("", "agenda_10-15-2025.pdf") == "2025-10-15"
    assert parse_date("Some Link", "meeting_01-01-2024.pdf") == "2024-01-01"


def test_parse_date_unknown():
    """Test that unknown dates return 'unknown_date'."""
    assert parse_date("No date here", "filename.pdf") == "unknown_date"
    assert parse_date("", "") == "unknown_date"


def test_parse_date_prefers_link_text():
    """Test that link text is preferred over filename."""
    # If both have dates, link text should win
    result = parse_date("Meeting on 10/15/2025", "agenda_01-01-2024.pdf")
    assert result == "2025-10-15"

