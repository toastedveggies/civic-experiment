from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from policy_tracker.ingestion import assess_gmail_message_file
from policy_tracker.source_loader import get_source_config


class LaCountyGmailTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.config_dir = self.repo_root / "configs" / "sources"
        self.source = get_source_config(self.config_dir, "la_county_board_agendas")

    def test_board_agenda_message_is_classified(self) -> None:
        fixture = self.repo_root / "tests" / "fixtures" / "gmail_board_agenda.json"
        assessment = assess_gmail_message_file(
            source_id=self.source.source_id,
            message_path=fixture,
            config_dir=self.config_dir,
        )

        self.assertTrue(assessment.relevant)
        self.assertEqual(assessment.message_type, "supplemental_board_agenda")
        self.assertEqual(assessment.meeting_date, "2026-05-19")
        self.assertEqual(
            [link.category for link in assessment.links],
            [
                "external_page",
                "board_agenda_page",
                "live_board_page",
                "public_comment_page",
            ],
        )

    def test_cluster_message_yields_direct_pdf_links(self) -> None:
        fixture = self.repo_root / "tests" / "fixtures" / "gmail_cluster_agendas.json"
        assessment = assess_gmail_message_file(
            source_id=self.source.source_id,
            message_path=fixture,
            config_dir=self.config_dir,
        )

        pdf_links = [link for link in assessment.links if link.category == "direct_pdf"]
        self.assertEqual(assessment.message_type, "cluster_meeting_agendas")
        self.assertEqual(assessment.meeting_date, "2026-05-15")
        self.assertEqual(len(pdf_links), 3)
        self.assertEqual(pdf_links[0].text, "Operations Cluster")


if __name__ == "__main__":
    unittest.main()
