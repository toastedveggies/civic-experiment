from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import json
import sqlite3

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from policy_tracker.la_county_ceo_import import (
    DownloadedCEODocument,
    backfill_downloaded_ceo_supporting_documents,
    collect_existing_supporting_documents,
    discover_ceo_agenda_sections,
    download_supporting_documents_for_agenda,
    downloaded_ceo_document_from_dict,
    infer_supporting_document_url_from_filename,
    parse_ceo_agenda_api_sections,
    upsert_document_record,
    resolve_supporting_resource,
    should_follow_supporting_link,
)
from policy_tracker.primegov_import import ensure_base_schema


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

    def test_parse_ceo_agenda_api_sections_maps_department_abbreviations(self) -> None:
        sections = parse_ceo_agenda_api_sections(
            [
                {
                    "date": "2026-06-03",
                    "deptAbbrv": "CSC",
                    "url": "https://file.lacounty.gov/SDSInter/clusteragendas/1209751_sample.pdf",
                    "title": "Agenda",
                    "documentTitle": "Community Services Cluster Meeting",
                }
            ]
        )

        self.assertIn("Community Services Cluster", sections)
        link = sections["Community Services Cluster"][0]
        self.assertEqual(link.agenda_date.isoformat(), "2026-06-03")
        self.assertEqual(link.label, "Community Services Cluster Meeting")

    def test_discover_ceo_agenda_sections_prefers_api(self) -> None:
        with patch(
            "policy_tracker.la_county_ceo_import.fetch_json",
            return_value=[
                {
                    "date": "2026-06-03",
                    "deptAbbrv": "FSSC",
                    "url": "https://file.lacounty.gov/SDSInter/clusteragendas/1209710_sample.pdf",
                    "title": "Agenda",
                    "documentTitle": "Family Services",
                }
            ],
        ):
            sections, method = discover_ceo_agenda_sections()

        self.assertEqual(method, "agenda_data_api")
        self.assertIn("Family and Social Services Cluster", sections)

    def test_discover_ceo_agenda_sections_falls_back_to_static_html(self) -> None:
        html = """
        <h4>Operations Cluster</h4>
        <a href="https://file.lacounty.gov/SDSInter/clusteragendas/sample.pdf">June 3, 2026 Agenda</a>
        """
        with patch("policy_tracker.la_county_ceo_import.fetch_json", side_effect=ValueError("api down")), patch(
            "policy_tracker.la_county_ceo_import.fetch_text",
            return_value=html,
        ):
            sections, method = discover_ceo_agenda_sections()

        self.assertEqual(method, "static_html_fallback")
        self.assertIn("Operations Cluster", sections)

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

    def test_downloaded_ceo_document_from_legacy_manifest_defaults_agenda_fields(self) -> None:
        document = downloaded_ceo_document_from_dict(
            {
                "requested_name": "Operations Cluster",
                "body_name": "Operations Cluster",
                "label": "June 4, 2025",
                "agenda_date": "2025-06-04",
                "url": "https://example.test/agenda.pdf",
                "file_path": "C:/tmp/agenda.pdf",
                "text_path": "C:/tmp/agenda.txt",
                "sha256": "abc",
                "bytes_downloaded": 10,
                "status": "extracted",
                "document_id": "doc_1",
                "external_id": "https://example.test/agenda.pdf",
            }
        )
        self.assertEqual(document.document_type, "ceo_agenda_pdf")
        self.assertEqual(document.mime_type, "application/pdf")

    def test_backfill_downloaded_ceo_supporting_documents_writes_manifest_without_db(self) -> None:
        agenda = self.build_agenda()
        download_root = self.tmp_dir / "downloads"
        download_root.mkdir(parents=True, exist_ok=True)
        manifest_path = download_root / "ceo_last_12_months_manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "source_id": "la_county_ceo_agendas",
                    "documents": [agenda.to_dict()],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        supporting_doc = DownloadedCEODocument(
            requested_name=agenda.requested_name,
            body_name=agenda.body_name,
            label="Support 1",
            agenda_date=agenda.agenda_date,
            url="https://file.lacounty.gov/SDSInter/bos/supdocs/203061.pdf",
            file_path=str((self.tmp_dir / "downloads" / "supporting.pdf").resolve()),
            text_path=None,
            sha256="support",
            bytes_downloaded=25,
            status="downloaded",
            document_id="doc_support",
            external_id="https://file.lacounty.gov/SDSInter/bos/supdocs/203061.pdf",
            document_type="ceo_supporting_document_pdf",
            mime_type="application/pdf",
            parent_external_id=agenda.external_id,
        )

        with patch(
            "policy_tracker.la_county_ceo_import.download_supporting_documents_for_agenda",
            return_value=([supporting_doc], []),
        ):
            summary = backfill_downloaded_ceo_supporting_documents(
                download_root=download_root,
                db_path=None,
            )

        self.assertEqual(summary["agenda_documents_considered"], 1)
        self.assertEqual(summary["supporting_documents_downloaded"], 1)
        backfill_manifest = download_root / "ceo_supporting_docs_backfill_manifest.json"
        self.assertTrue(backfill_manifest.exists())

    def test_backfill_downloaded_ceo_supporting_documents_inventory_only_skips_fetch(self) -> None:
        agenda = self.build_agenda()
        download_root = self.tmp_dir / "downloads_inventory"
        download_root.mkdir(parents=True, exist_ok=True)
        (download_root / "ceo_last_12_months_manifest.json").write_text(
            json.dumps({"source_id": "la_county_ceo_agendas", "documents": [agenda.to_dict()]}, indent=2),
            encoding="utf-8",
        )

        with patch(
            "policy_tracker.la_county_ceo_import.download_supporting_documents_for_agenda",
            side_effect=AssertionError("should not fetch in inventory-only mode"),
        ):
            summary = backfill_downloaded_ceo_supporting_documents(
                download_root=download_root,
                db_path=None,
                inventory_only=True,
            )

        self.assertTrue(summary["inventory_only"])
        self.assertEqual(summary["supporting_documents_downloaded"], 0)

    def test_collect_existing_supporting_documents_infers_url_and_writes_metadata(self) -> None:
        agenda = self.build_agenda()
        supporting_dir = Path(agenda.file_path).parent / "supporting_docs"
        supporting_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = supporting_dir / "supporting_001_203061.pdf"
        txt_path = supporting_dir / "supporting_001_203061.txt"
        pdf_path.write_bytes(b"%PDF-1.4 support")
        txt_path.write_text("support text", encoding="utf-8")

        documents = collect_existing_supporting_documents(agenda)

        self.assertEqual(len(documents), 1)
        self.assertEqual(
            documents[0].external_id,
            "https://file.lacounty.gov/SDSInter/bos/supdocs/203061.pdf",
        )
        self.assertTrue((supporting_dir / "supporting_001_203061.metadata.json").exists())

    def test_infer_supporting_document_url_from_filename_handles_poc_pattern(self) -> None:
        path = Path("supporting_001_POC26-0022.pdf")
        self.assertEqual(
            infer_supporting_document_url_from_filename(path),
            "https://file.lacounty.gov/SDSInter/bos/supdocs/POC26-0022.pdf",
        )

    def test_upsert_document_record_reuses_existing_row_for_same_file_path(self) -> None:
        agenda = self.build_agenda()
        support_path = self.tmp_dir / "supporting_docs" / "supporting_001_203061.pdf"
        support_path.parent.mkdir(parents=True, exist_ok=True)
        support_path.write_bytes(b"%PDF-1.4 support")

        first = DownloadedCEODocument(
            requested_name=agenda.requested_name,
            body_name=agenda.body_name,
            label="Support Existing",
            agenda_date=agenda.agenda_date,
            url="https://file.lacounty.gov/SDSInter/bos/supdocs/203061.pdf",
            file_path=str(support_path.resolve()),
            text_path=None,
            sha256="one",
            bytes_downloaded=10,
            status="existing_local",
            document_id="doc_existing",
            external_id=str(support_path.resolve()),
            document_type="ceo_supporting_document_pdf",
            mime_type="application/pdf",
            parent_external_id=agenda.external_id,
        )
        second = DownloadedCEODocument(
            requested_name=agenda.requested_name,
            body_name=agenda.body_name,
            label="Support Downloaded",
            agenda_date=agenda.agenda_date,
            url="https://file.lacounty.gov/SDSInter/bos/supdocs/203061.pdf",
            file_path=str(support_path.resolve()),
            text_path=None,
            sha256="two",
            bytes_downloaded=10,
            status="downloaded",
            document_id="doc_downloaded",
            external_id="https://file.lacounty.gov/SDSInter/bos/supdocs/203061.pdf",
            document_type="ceo_supporting_document_pdf",
            mime_type="application/pdf",
            parent_external_id=agenda.external_id,
        )

        conn = sqlite3.connect(":memory:")
        try:
            ensure_base_schema(conn)
            upsert_document_record(conn, "la_county_ceo_agendas", first)
            upsert_document_record(conn, "la_county_ceo_agendas", second)
            conn.commit()
            count = conn.execute(
                "select count(*) from documents where source_id='la_county_ceo_agendas' and file_path=?",
                (str(support_path.resolve()),),
            ).fetchone()[0]
            row = conn.execute(
                "select document_id, external_id from documents where source_id='la_county_ceo_agendas' and file_path=?",
                (str(support_path.resolve()),),
            ).fetchone()
        finally:
            conn.close()

        self.assertEqual(count, 1)
        self.assertEqual(row[0], "doc_existing")
        self.assertEqual(row[1], "https://file.lacounty.gov/SDSInter/bos/supdocs/203061.pdf")


if __name__ == "__main__":
    unittest.main()
