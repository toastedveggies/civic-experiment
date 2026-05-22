from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from policy_tracker.item_extraction import extract_agenda_items_from_text_path


class ItemExtractionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_extracts_community_services_items(self) -> None:
        path = self.repo_root / "tests" / "fixtures" / "community_services_sample.txt"
        document = extract_agenda_items_from_text_path(path)

        self.assertEqual(document.cluster_name, "Community Services Cluster")
        self.assertEqual(document.meeting_date, "May 20, 2026")
        self.assertEqual(document.item_count, 3)
        self.assertIn("contracting", document.items[0].topic_tags)
        self.assertIn("governance", document.items[2].topic_tags)

    def test_extracts_public_safety_items_and_topics(self) -> None:
        path = self.repo_root / "tests" / "fixtures" / "public_safety_sample.txt"
        document = extract_agenda_items_from_text_path(path)

        self.assertEqual(document.cluster_name, "Public Safety Cluster")
        self.assertEqual(document.item_count, 3)
        probation_item = document.items[2]
        self.assertIn("public_safety", probation_item.topic_tags)
        self.assertIn("probation", probation_item.topic_tags)
        self.assertIn("contracting", probation_item.topic_tags)
        self.assertTrue(probation_item.speakers)

    def test_extracts_homelessness_housing_items_from_roman_numeral_agenda(self) -> None:
        path = self.repo_root / "tests" / "fixtures" / "homelessness_housing_sample.txt"
        document = extract_agenda_items_from_text_path(path)

        self.assertEqual(document.cluster_name, "Homelessness & Housing Cluster")
        self.assertEqual(document.meeting_date, "May 14, 2026")
        self.assertEqual(document.item_count, 4)
        self.assertEqual(document.items[0].item_type, "other")
        self.assertIn("homelessness", document.items[0].topic_tags)
        self.assertIn("housing", document.items[1].topic_tags)
        self.assertIn("Manny Ruiz", document.items[2].speakers[0])
