from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from policy_tracker.document_context import build_download_targets
from policy_tracker.downloader import download_assessed_message_targets, write_manifest
from policy_tracker.ingestion import assess_gmail_message_file


class DownloadPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.config_dir = self.repo_root / "configs" / "sources"

    def test_build_download_targets_filters_non_documents(self) -> None:
        fixture = self.repo_root / "tests" / "fixtures" / "gmail_board_agenda.json"
        assessment = assess_gmail_message_file(
            source_id="la_county_board_agendas",
            message_path=fixture,
            config_dir=self.config_dir,
        )
        targets = build_download_targets(assessment)

        self.assertEqual([target.document_kind for target in targets], ["board_agenda_page"])

    def test_download_message_links_writes_files_and_metadata(self) -> None:
        tmp_path = self.repo_root / "tests" / "tmp_download_pipeline"
        tmp_path.mkdir(parents=True, exist_ok=True)
        sample_pdf = (self.repo_root / "tests" / "fixtures" / "sample_context.pdf").resolve()
        message_path = tmp_path / "message.json"
        payload = {
            "id": "msg-local-1",
            "from_": "\"Executive Office, L.A. County Board of Supervisors\" BOSEXEC@subscriptions.lacounty.gov",
            "to": ["robert@civicexperiment.com"],
            "subject": "Cluster Meeting Agendas – May 15, 2026",
            "body": f"- [Operations Cluster](file:///{sample_pdf.as_posix()})",
            "email_ts": "2026-05-15T23:01:57",
            "labels": ["UNREAD"],
        }
        message_path.write_text(json.dumps(payload), encoding="utf-8")

        results = download_assessed_message_targets(
            source_id="la_county_board_agendas",
            message_path=message_path,
            config_dir=self.config_dir,
            output_dir=tmp_path / "downloads",
        )

        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertTrue(Path(result.local_path).exists())
        self.assertTrue(Path(result.metadata_path).exists())
        self.assertEqual(result.target.document_kind, "cluster_agenda_packet")
        self.assertEqual(result.bytes_downloaded, sample_pdf.stat().st_size)
        self.assertIn(result.processing_status, {"ready", "downloaded_without_text"})

    def test_missing_file_is_queued_for_failure_not_silent_drop(self) -> None:
        tmp_path = self.repo_root / "tests" / "tmp_download_pipeline_failure"
        tmp_path.mkdir(parents=True, exist_ok=True)
        missing_pdf = "file:///C:/definitely-not-here/missing.pdf"
        message_path = tmp_path / "message.json"
        payload = {
            "id": "msg-local-missing",
            "from_": "\"Executive Office, L.A. County Board of Supervisors\" BOSEXEC@subscriptions.lacounty.gov",
            "to": ["robert@civicexperiment.com"],
            "subject": "Cluster Meeting Agendas – May 15, 2026",
            "body": f"- [Operations Cluster]({missing_pdf})",
            "email_ts": "2026-05-15T23:01:57",
            "labels": ["UNREAD"],
        }
        message_path.write_text(json.dumps(payload), encoding="utf-8")

        results = download_assessed_message_targets(
            source_id="la_county_board_agendas",
            message_path=message_path,
            config_dir=self.config_dir,
            output_dir=tmp_path / "downloads",
            max_fetch_attempts=1,
        )

        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertEqual(result.processing_status, "download_failed")
        self.assertEqual(result.bytes_downloaded, 0)
        self.assertTrue(result.errors)

    def test_manifest_writes_retry_and_manual_review_queues(self) -> None:
        tmp_path = self.repo_root / "tests" / "tmp_download_pipeline_manifest"
        tmp_path.mkdir(parents=True, exist_ok=True)
        sample_pdf = (self.repo_root / "tests" / "fixtures" / "sample_context.pdf").resolve()
        message_path = tmp_path / "message.json"
        payload = {
            "id": "msg-local-manifest",
            "from_": "\"Executive Office, L.A. County Board of Supervisors\" BOSEXEC@subscriptions.lacounty.gov",
            "to": ["robert@civicexperiment.com"],
            "subject": "Cluster Meeting Agendas – May 15, 2026",
            "body": f"- [Operations Cluster](file:///{sample_pdf.as_posix()})",
            "email_ts": "2026-05-15T23:01:57",
            "labels": ["UNREAD"],
        }
        message_path.write_text(json.dumps(payload), encoding="utf-8")

        results = download_assessed_message_targets(
            source_id="la_county_board_agendas",
            message_path=message_path,
            config_dir=self.config_dir,
            output_dir=tmp_path / "downloads",
        )
        manifest_path = tmp_path / "downloads" / "manifest.json"
        write_manifest(results, manifest_path)

        self.assertTrue(manifest_path.exists())
        self.assertTrue((tmp_path / "downloads" / "retry_queue.json").exists())
        self.assertTrue((tmp_path / "downloads" / "manual_review_queue.json").exists())


if __name__ == "__main__":
    unittest.main()
