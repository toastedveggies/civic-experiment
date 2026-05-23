from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from policy_tracker.ingestion import assess_gmail_message_file


class LaCityGmailTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.config_dir = self.repo_root / "configs" / "sources"

    def test_city_council_notice_extracts_primegov_link_and_metadata(self) -> None:
        fixture = self.repo_root / "tests" / "fixtures" / "gmail_la_city_council_notice.json"
        assessment = assess_gmail_message_file(
            source_id="la_city_agendas",
            message_path=fixture,
            config_dir=self.config_dir,
        )

        self.assertTrue(assessment.relevant)
        self.assertEqual(assessment.message_type, "agenda_notice")
        self.assertEqual(assessment.meeting_date, "2026-05-26")
        self.assertEqual([link.category for link in assessment.links], ["primegov_meeting_page"])

        notices = assessment.metadata["attachment_notices"]
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0]["body_name"], "Los Angeles City Council")
        self.assertEqual(notices[0]["primegov_meeting_template_id"], "155180")
        self.assertFalse(notices[0]["is_cancellation"])


if __name__ == "__main__":
    unittest.main()
