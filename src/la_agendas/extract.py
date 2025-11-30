"""Extract PDF links and label them with meeting groups."""

import logging
from typing import List
from urllib.parse import urljoin

from lxml import etree

from la_agendas.discovery import (
    find_all_pdf_links,
    find_h4_headings,
    find_nearest_preceding_h4,
    find_tab_containers,
    parse_html,
)
from la_agendas.parse import parse_date
from la_agendas.util import (
    dedupe_records,
    extract_filename,
    filter_agenda_pdfs,
    filter_cancellations,
    is_pdf_url,
    normalize_url,
)

logger = logging.getLogger(__name__)


def extract_links(
    html_content: str,
    base_url: str,
    only_agenda_pdfs: bool = False,
    exclude_cancellations: bool = False,
) -> List[dict]:
    """
    Extract all PDF links from HTML and label them with meeting groups.
    Returns list of dicts with keys: group, date, link_text, url, filename.
    """
    doc = parse_html(html_content)
    records = []

    # Forward pass: h4 -> tab containers -> PDFs
    h4s = find_h4_headings(doc)
    tab_containers = find_tab_containers(doc)

    # Build mapping: h4 -> following tab containers
    h4_to_tabs = {}
    for h4, h4_text in h4s:
        h4_to_tabs[h4] = []
        # Find tab containers that follow this h4
        for tab in tab_containers:
            # Check if tab is a descendant or following sibling of h4's parent
            h4_parent = h4.getparent()
            if h4_parent is not None:
                # Simple heuristic: tab comes after h4 in document order
                h4_pos = doc.getelementpath(h4) if hasattr(doc, "getelementpath") else None
                tab_pos = doc.getelementpath(tab) if hasattr(doc, "getelementpath") else None
                # For now, collect all tabs and match by proximity later
                h4_to_tabs[h4].append(tab)

    # Reverse pass: tab containers -> nearest preceding h4
    tab_to_h4 = {}
    for tab in tab_containers:
        nearest = find_nearest_preceding_h4(tab)
        if nearest:
            tab_to_h4[tab] = nearest[1]  # Store h4 text

    # Collect PDFs from tab containers
    for tab in tab_containers:
        group = tab_to_h4.get(tab, "(unlabeled)")
        # Find all PDF links within this tab
        pdf_links = tab.xpath(".//a[@href]")
        for anchor in pdf_links:
            href = anchor.get("href", "")
            if not is_pdf_url(href):
                continue
            link_text = "".join(anchor.itertext()).strip()
            abs_url = normalize_url(base_url, href)
            filename = extract_filename(abs_url)
            date = parse_date(link_text, filename)

            # Apply filters
            if only_agenda_pdfs and not filter_agenda_pdfs(link_text, filename):
                continue
            if exclude_cancellations and filter_cancellations(link_text, filename):
                continue

            records.append(
                {
                    "group": group,
                    "date": date,
                    "link_text": link_text,
                    "url": abs_url,
                    "filename": filename,
                }
            )

    # Global PDF sweep: find all PDFs anywhere in the document
    all_pdf_links = find_all_pdf_links(doc, base_url)
    for anchor, link_text, href in all_pdf_links:
        abs_url = normalize_url(base_url, href)
        filename = extract_filename(abs_url)

        # Find nearest preceding h4 for labeling
        nearest = find_nearest_preceding_h4(anchor)
        group = nearest[1] if nearest else "(unlabeled)"

        date = parse_date(link_text, filename)

        # Apply filters
        if only_agenda_pdfs and not filter_agenda_pdfs(link_text, filename):
            continue
        if exclude_cancellations and filter_cancellations(link_text, filename):
            continue

        records.append(
            {
                "group": group,
                "date": date,
                "link_text": link_text,
                "url": abs_url,
                "filename": filename,
            }
        )

    # Deduplicate
    records = dedupe_records(records)

    logger.info(f"Extracted {len(records)} unique PDF links")
    return records

