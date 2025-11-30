"""Tests for extraction logic."""

import pytest
from lxml import html

from la_agendas.discovery import (
    find_all_pdf_links,
    find_h4_headings,
    find_nearest_preceding_h4,
    find_tab_containers,
)
from la_agendas.extract import extract_links
from la_agendas.util import dedupe_records, filter_agenda_pdfs, filter_cancellations


def test_find_h4_headings():
    """Test finding h4 headings with keywords."""
    html_content = """
    <html>
        <body>
            <h4>Cluster Meeting</h4>
            <h4>Some Other Heading</h4>
            <h4>Deputies Committee</h4>
        </body>
    </html>
    """
    doc = html.fromstring(html_content)
    h4s = find_h4_headings(doc)
    assert len(h4s) == 2  # "Cluster Meeting" and "Deputies Committee"
    texts = [text for _, text in h4s]
    assert "Cluster Meeting" in texts
    assert "Deputies Committee" in texts


def test_find_all_pdf_links():
    """Test finding all PDF links."""
    html_content = """
    <html>
        <body>
            <a href="/doc1.pdf">Document 1</a>
            <a href="/doc2.PDF">Document 2</a>
            <a href="/page.html">Not a PDF</a>
            <a href="https://example.com/file.pdf">External PDF</a>
        </body>
    </html>
    """
    doc = html.fromstring(html_content)
    links = find_all_pdf_links(doc, "https://example.com")
    assert len(links) == 3  # All PDF links


def test_find_nearest_preceding_h4():
    """Test finding nearest preceding h4."""
    html_content = """
    <html>
        <body>
            <h4>Cluster Meeting</h4>
            <div>
                <a href="/doc.pdf">Link</a>
            </div>
        </body>
    </html>
    """
    doc = html.fromstring(html_content)
    anchor = doc.xpath("//a[@href='/doc.pdf']")[0]
    result = find_nearest_preceding_h4(anchor)
    assert result is not None
    h4, text = result
    assert text == "Cluster Meeting"


def test_filter_agenda_pdfs():
    """Test agenda PDF filter."""
    assert filter_agenda_pdfs("Agenda for Meeting", "file.pdf") is True
    assert filter_agenda_pdfs("Regular Document", "agenda.pdf") is True
    assert filter_agenda_pdfs("Regular Document", "file.pdf") is False


def test_filter_cancellations():
    """Test cancellation filter."""
    assert filter_cancellations("Cancelled Meeting", "file.pdf") is True
    assert filter_cancellations("Regular Document", "cancel.pdf") is True
    assert filter_cancellations("Regular Document", "file.pdf") is False


def test_dedupe_records():
    """Test record deduplication."""
    records = [
        {"group": "A", "link_text": "Link 1", "url": "http://example.com/1.pdf"},
        {"group": "A", "link_text": "Link 1", "url": "http://example.com/1.pdf"},  # Duplicate
        {"group": "B", "link_text": "Link 2", "url": "http://example.com/2.pdf"},
    ]
    unique = dedupe_records(records)
    assert len(unique) == 2


def test_extract_links_basic():
    """Test basic link extraction."""
    html_content = """
    <html>
        <body>
            <h4>Cluster Meeting</h4>
            <div>
                <a href="/agenda_10-15-2025.pdf">Agenda</a>
            </div>
        </body>
    </html>
    """
    records = extract_links(html_content, "https://example.com")
    assert len(records) > 0
    # Should find the PDF link
    pdf_records = [r for r in records if r["url"].endswith(".pdf")]
    assert len(pdf_records) > 0


def test_extract_links_only_agenda_filter():
    """Test extraction with only-agenda filter."""
    html_content = """
    <html>
        <body>
            <a href="/agenda.pdf">Agenda Document</a>
            <a href="/other.pdf">Other Document</a>
        </body>
    </html>
    """
    records = extract_links(
        html_content, "https://example.com", only_agenda_pdfs=True
    )
    # Should only include agenda.pdf
    assert all("agenda" in r["link_text"].lower() or "agenda" in r["filename"].lower() for r in records)


def test_extract_links_exclude_cancellations():
    """Test extraction with cancellation exclusion."""
    html_content = """
    <html>
        <body>
            <a href="/meeting.pdf">Regular Meeting</a>
            <a href="/cancelled.pdf">Cancelled Meeting</a>
        </body>
    </html>
    """
    records = extract_links(
        html_content, "https://example.com", exclude_cancellations=True
    )
    # Should exclude cancelled.pdf
    assert not any("cancel" in r["link_text"].lower() or "cancel" in r["filename"].lower() for r in records)

