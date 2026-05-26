from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from policy_tracker.la_county_ceo_import import (
    DownloadedCEODocument,
    download_supporting_documents_for_agenda,
    resolve_supporting_resource,
    should_follow_supporting_link,
)


class LaCountyCeoImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.tmp_dir = self.repo_root / "tests" / "tmp_ceo_supporting_docs"
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def build_agenda(self, text_content: str = "Supporting Document\nAttachments:\n") -> DownloadedCEODocument:
        agenda_pdf = self.tmp_dir / "agenda.pdf"
        agenda_txt = self.tmp_dir / "agenda.txt"
        agenda_pdf.write_bytes(b"%PDF-1.4 test agenda")
        agenda_txt.write_text(text_content, encoding="utf-8")
        return DownloadedCEODocument(
            requested_name="Executive Committee for Regional Homeless Alignment",
            body_name="Executive Committee for Regional Homeless Alignment",
            label="May 29, 2025",
            agenda_date="2025-05-29",
            url="https://example.test/agenda.pdf",
            file_path=str(agenda_pdf.resolve()),
            text_path=str(agenda_txt.resolve()),
            sha256="agenda",
            bytes_downloaded=18,
            status="ready",
            document_id="doc_agenda",
            external_id="https://example.test/agenda.pdf",
            document_type="ceo_agenda_pdf",
            mime_type="application/pdf",
        )

    def test_should_follow_supporting_link_prefers_known_backend_families(self) -> None:
        self.assertTrue(should_follow_supporting_link("https://file.lacounty.gov/SDSInter/bos/supdocs/203061.pdf"))
        self.assertTrue(
            should_follow_supporting_link(
                "https://lacounty.sharepoint.com/:b:/t/AdvancePlanningDivision/EcoqlUjsLdFAhxDB7rH-aogBulVBdGtkGq2XT85H_VF47Q?e=1L4jxm"
            )
        )
        self.assertFalse(should_follow_supporting_link("https://lacountyboardofsupervisors.webex.com/meeting"))
        self.assertFalse(should_follow_supporting_link("https://status.salesforce.com/status"))

    def test_resolve_supporting_resource_follows_single_landing_page_hop(self) -> None:
        html_bytes = (
            b'<html><body><a href="https://file.lacounty.gov/SDSInter/bos/supdocs/203061.pdf">Download</a></body></html>'
        )
        pdf_bytes = b"%PDF-1.4 final"

        with patch(
            "policy_tracker.la_county_ceo_import.fetch_resource",
            side_effect=[
                (html_bytes, "text/html", "https://example.test/landing"),
                (pdf_bytes, "application/pdf", "https://file.lacounty.gov/SDSInter/bos/supdocs/203061.pdf"),
            ],
        ):
            binary, content_type, final_url, reason = resolve_supporting_resource(
                "https://example.test/landing"
            )

        self.assertEqual(binary, pdf_bytes)
        self.assertEqual(content_type, "application/pdf")
        self.assertEqual(final_url, "https://file.lacounty.gov/SDSInter/bos/supdocs/203061.pdf")
        self.assertEqual(reason, "followed_landing_page")

    def test_download_supporting_documents_materializes_trusted_link(self) -> None:
        agenda = self.build_agenda()

        with (
            patch(
                "policy_tracker.la_county_ceo_import.extract_pdf_annotation_links",
                return_value=["https://file.lacounty.gov/SDSInter/bos/supdocs/203061.pdf"],
            ),
            patch(
                "policy_tracker.la_county_ceo_import.resolve_supporting_resource",
                return_value=(
                    b"%PDF-1.4 support",
                    "application/pdf",
                    "https://file.lacounty.gov/SDSInter/bos/supdocs/203061.pdf",
                    "direct_download",
                ),
            ),
            patch(
                "policy_tracker.la_county_ceo_import.extract_pdf_text",
                return_value=SimpleNamespace(status="extracted", text_path=str((self.tmp_dir / "support.txt").resolve())),
            ),
        ):
            documents, review_targets = download_supporting_documents_for_agenda(agenda)

        self.assertEqual(len(documents), 1)
        self.assertEqual(review_targets, [])
        self.assertEqual(documents[0].document_type, "ceo_supporting_document_pdf")
        self.assertEqual(documents[0].parent_external_id, agenda.external_id)
        self.assertIn("supporting_docs", documents[0].file_path)

    def test_download_supporting_documents_queues_manual_review_when_labels_have_no_trusted_links(self) -> None:
        agenda = self.build_agenda()

        with patch(
            "policy_tracker.la_county_ceo_import.extract_pdf_annotation_links",
            return_value=["https://status.salesforce.com/status"],
        ):
            documents, review_targets = download_supporting_documents_for_agenda(agenda)

        self.assertEqual(documents, [])
        self.assertEqual(len(review_targets), 1)
        self.assertEqual(review_targets[0].reason, "supporting_labels_without_trusted_links")


if __name__ == "__main__":
    unittest.main()
