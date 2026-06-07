from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from policy_tracker.lahsa_import import (
    discover_lahsa_scope_documents,
    discover_lahsa_scopes,
    filter_document_links,
    parse_lahsa_detail_metadata,
)


SCOPE_HTML = """
<a href="documents?scope=106" class="doclib-browse-tile doclib-animate">
  <div class="tile-label">Finance</div>
</a>
<a href="documents?scope=107" class="doclib-browse-tile doclib-animate">
  <div class="tile-label">Policy</div>
</a>
"""

DOCUMENTS_HTML = """
<a href="documents?id=9678-fy2025-26-lahsa-budget-adoption.pdf" class="doclib-item">
  <div class="doclib-item-info">
    <div class="doclib-item-name">Fy2025-26 LAHSA Budget Adoption</div>
  </div>
</a>
<a href="documents?id=9000-random-training.pdf" class="doclib-item">
  <div class="doclib-item-info">
    <div class="doclib-item-name">Random Training</div>
  </div>
</a>
"""

DETAIL_HTML = """
<script type="application/ld+json">{
  "@context": "https://schema.org",
  "@type": "DigitalDocument",
  "name": "Fy2025-26 LAHSA Budget Adoption",
  "datePublished": "2025-12-10",
  "dateModified": "2025-12-10"
}</script>
<a id="bodycontent_hlDownload" class="doclib-btn-download"
   href="https://www.lahsa.org/item.ashx?id=9678-fy2025-26-lahsa-budget-adoption.pdf&amp;dl=true">Download</a>
<span id="bodycontent_lblDocumentType">Budget</span>
<span id="bodycontent_lblProject"></span>
<span id="bodycontent_lblProgramType"></span>
<span id="bodycontent_lblScope">Finance</span>
<span id="bodycontent_lblPubDate">12/10/2025</span>
<span id="bodycontent_lblLastmodified">12/10/2025 5:07:17 PM</span>
"""


class LAHSAImportTests(unittest.TestCase):
    def test_discover_lahsa_scopes_parses_scope_tiles(self) -> None:
        with patch("policy_tracker.lahsa_import.fetch_text", return_value=SCOPE_HTML):
            scopes = discover_lahsa_scopes()

        self.assertEqual(scopes, {"106": "Finance", "107": "Policy"})

    def test_discover_lahsa_scope_documents_parses_document_cards(self) -> None:
        with patch("policy_tracker.lahsa_import.fetch_text", return_value=DOCUMENTS_HTML):
            links = discover_lahsa_scope_documents("106", "Finance")

        self.assertEqual(len(links), 2)
        self.assertEqual(links[0].title, "Fy2025-26 LAHSA Budget Adoption")
        self.assertEqual(links[0].lahsa_document_id, "9678-fy2025-26-lahsa-budget-adoption.pdf")
        self.assertEqual(links[0].detail_url, "https://www.lahsa.org/documents?id=9678-fy2025-26-lahsa-budget-adoption.pdf")

    def test_filter_document_links_applies_keywords(self) -> None:
        with patch("policy_tracker.lahsa_import.fetch_text", return_value=DOCUMENTS_HTML):
            links = discover_lahsa_scope_documents("106", "Finance")

        filtered = filter_document_links(links, ["budget"])

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].title, "Fy2025-26 LAHSA Budget Adoption")

    def test_parse_lahsa_detail_metadata_reads_json_ld_and_fields(self) -> None:
        metadata = parse_lahsa_detail_metadata(DETAIL_HTML)

        self.assertEqual(metadata["title"], "Fy2025-26 LAHSA Budget Adoption")
        self.assertEqual(
            metadata["download_url"],
            "https://www.lahsa.org/item.ashx?id=9678-fy2025-26-lahsa-budget-adoption.pdf&dl=true",
        )
        self.assertEqual(metadata["document_type"], "Budget")
        self.assertEqual(metadata["project_scope"], "Finance")
        self.assertEqual(metadata["published_date"], "12/10/2025")
        self.assertEqual(metadata["last_modified"], "12/10/2025 5:07:17 PM")


if __name__ == "__main__":
    unittest.main()
