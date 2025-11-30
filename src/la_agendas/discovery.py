"""DOM discovery for h4 headings, tab containers, and PDF links."""

import logging
import re
from typing import List, Tuple
from urllib.parse import urljoin, urlparse

from lxml import etree, html

logger = logging.getLogger(__name__)

# Configurable selectors
H4_KEYWORD_PATTERN = r"(cluster|deputies|committee|meeting)"
TAB_CONTAINER_SELECTORS = [
    "div[contains(@class,'et-tabs')]",
    "div[contains(@class,'tabs')]",
    "div[contains(@class,'tab-container')]",
    "div[contains(@class,'tabbed')]",
]


def parse_html(html_content: str) -> etree._Element:
    """Parse HTML string into lxml Element."""
    return html.fromstring(html_content)


def find_h4_headings(doc: etree._Element) -> List[Tuple[etree._Element, str]]:
    """
    Find all h4 headings that match the keyword pattern.
    Returns list of (element, text) tuples.
    """
    h4s = doc.xpath("//h4")
    results = []
    for h4 in h4s:
        text = "".join(h4.itertext()).strip()
        if text and __import__("re").search(H4_KEYWORD_PATTERN, text, re.IGNORECASE):
            results.append((h4, text))
    return results


def find_tab_containers(doc: etree._Element) -> List[etree._Element]:
    """Find all tab containers using configurable selectors."""
    containers = []
    for selector in TAB_CONTAINER_SELECTORS:
        found = doc.xpath(f"//{selector}")
        containers.extend(found)
    # Deduplicate by element identity
    seen = set()
    unique = []
    for container in containers:
        if id(container) not in seen:
            seen.add(id(container))
            unique.append(container)
    return unique


def find_all_pdf_links(doc: etree._Element, base_url: str) -> List[Tuple[etree._Element, str, str]]:
    """
    Find all PDF links in the document.
    Returns list of (anchor_element, link_text, href) tuples.
    """
    # Find all anchors with href containing .pdf
    anchors = doc.xpath("//a[@href]")
    results = []
    for anchor in anchors:
        href = anchor.get("href", "")
        if not href:
            continue
        href_lower = href.lower()
        if ".pdf" in href_lower or href_lower.endswith(".pdf"):
            link_text = "".join(anchor.itertext()).strip()
            results.append((anchor, link_text, href))
    return results


def find_meeting_detail_links(doc: etree._Element, base_url: str) -> List[str]:
    """
    Find links that appear to be meeting detail pages (same domain, not PDFs).
    Returns list of absolute URLs.
    """
    anchors = doc.xpath("//a[@href]")
    results = []
    base_domain = urlparse(base_url).netloc
    for anchor in anchors:
        href = anchor.get("href", "")
        if not href:
            continue
        # Normalize to absolute URL
        abs_url = urljoin(base_url, href)
        url_domain = urlparse(abs_url).netloc
        # Must be same domain, not a PDF, and link text suggests it's a detail page
        if url_domain == base_domain and not abs_url.lower().endswith(".pdf"):
            link_text = "".join(anchor.itertext()).strip().lower()
            if "agenda" in link_text or "meeting" in link_text or "/meeting/" in abs_url.lower():
                if abs_url not in results:
                    results.append(abs_url)
    return results


def find_nearest_preceding_h4(element: etree._Element) -> Tuple[etree._Element, str] | None:
    """
    Walk upward from element to find nearest preceding h4 with keyword pattern.
    Returns (h4_element, text) or None.
    """
    current = element
    while current is not None:
        # Check if current is an h4
        if current.tag == "h4":
            text = "".join(current.itertext()).strip()
            if text and re.search(H4_KEYWORD_PATTERN, text, re.IGNORECASE):
                return (current, text)
        # Move to previous sibling
        prev_sibling = current.getprevious()
        if prev_sibling is not None:
            # Check siblings and their descendants
            for sibling in [prev_sibling] + list(prev_sibling.iterdescendants()):
                if sibling.tag == "h4":
                    text = "".join(sibling.itertext()).strip()
                    if text and re.search(H4_KEYWORD_PATTERN, text, re.IGNORECASE):
                        return (sibling, text)
        # Move to parent
        current = current.getparent()
    return None

