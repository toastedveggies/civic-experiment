from __future__ import annotations

import sqlite3
import shutil
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from policy_tracker.la_city_email_ingestion import ingest_la_city_gmail_message_file


class LaCityEmailIngestionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.config_dir = self.repo_root / "configs" / "sources"
        self.fixture = self.repo_root / "tests" / "fixtures" / "gmail_la_city_council_notice.json"
        self.primegov_html = (
            self.repo_root / "tests" / "fixtures" / "la_city_primegov_sample.html.txt"
        ).read_text(encoding="utf-8")
        self.tmp_dir = self.repo_root / "tests" / "tmp_la_city_email_ingestion"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_ingest_saved_message_materializes_notice_and_structured_items(self) -> None:
        db_path = self.tmp_dir / "policy_tracker.sqlite"
        download_root = self.tmp_dir / "downloads"
        structured_root = self.tmp_dir / "structured"
        real_sqlite_connect = sqlite3.connect

        with patch(
            "policy_tracker.la_city_email_ingestion.fetch_binary",
            return_value=self.primegov_html.encode("utf-8"),
        ), patch(
            "policy_tracker.la_city_email_ingestion.import_items_index",
            return_value={"documents_imported": 1, "items_imported": 12, "topics_imported": 8},
        ), patch(
            "policy_tracker.la_city_email_ingestion.sqlite3.connect",
            side_effect=lambda *_args, **_kwargs: real_sqlite_connect(":memory:"),
        ):
            summary = ingest_la_city_gmail_message_file(
                message_path=self.fixture,
                config_dir=self.config_dir,
                db_path=db_path,
                download_root=download_root,
                structured_output_dir=structured_root,
            )

        self.assertEqual(summary["notice_documents_written"], 1)
        self.assertEqual(summary["primegov_documents_written"], 1)
        self.assertEqual(summary["structured_documents_written"], 1)
        self.assertGreater(summary["import_summary"]["items_imported"], 0)

        message_dir = download_root / "gmail" / "msg-la-city-1"
        self.assertTrue((message_dir / "clkcouncilagenda155180_05262026.htm").exists())
        self.assertTrue((message_dir / "clkcouncilagenda155180_05262026.txt").exists())

        primegov_txt_files = list((download_root / "primegov_email").rglob("*_html-email.txt"))
        self.assertEqual(len(primegov_txt_files), 1)
        self.assertTrue((structured_root / "batches" / "msg-la-city-1.agenda_items.index.json").exists())


if __name__ == "__main__":
    unittest.main()
