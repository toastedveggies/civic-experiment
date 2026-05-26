from __future__ import annotations

import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from policy_tracker.query_layer import (
    QueryFilters,
    build_weekly_digest,
    fetch_items_from_connection,
    render_weekly_digest_markdown,
    summarize_parliamentary,
    summarize_by_cluster,
    summarize_by_topic,
)
from policy_tracker.sqlite_import import (
    STRUCTURED_TABLES_SQL,
    build_document_summaries,
    load_items_index,
    replace_structured_topics,
    upsert_structured_documents,
    upsert_structured_items,
)


class QueryLayerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.index_path = self.repo_root / "local" / "structured" / "live_test" / "agenda_items.index.json"
        rows = load_items_index(self.index_path)
        rows[0]["meeting_id"] = "meeting_test_1"
        rows[0]["document_role"] = "agenda"
        rows[0]["motion_by"] = "Solis"
        rows[0]["second_by"] = "Hahn"
        rows[0]["final_action"] = "approved"
        rows[0]["ayes_count"] = 4
        rows[0]["noes_count"] = 0
        rows[0]["abstain_count"] = 0
        rows[0]["absent_count"] = 1
        rows[0]["ayes_members"] = ["Solis", "Mitchell", "Horvath", "Hahn"]
        rows[0]["absent_members"] = ["Barger"]
        summaries = build_document_summaries(rows, "la_county_board_agendas", self.index_path.parent)
        self.connection = sqlite3.connect(":memory:")
        self.connection.executescript(STRUCTURED_TABLES_SQL)
        upsert_structured_documents(self.connection, summaries)
        upsert_structured_items(self.connection, rows, "la_county_board_agendas")
        replace_structured_topics(self.connection, rows)
        self.connection.commit()

    def tearDown(self) -> None:
        self.connection.close()

    def test_fetch_items_with_topic_filter(self) -> None:
        items = fetch_items_from_connection(self.connection, QueryFilters(topic="probation", limit=20))
        self.assertTrue(items)
        self.assertTrue(all("probation" in item.topic_tags for item in items))

    def test_summary_helpers(self) -> None:
        items = fetch_items_from_connection(self.connection, QueryFilters(limit=100))
        topic_summary = summarize_by_topic(items)
        cluster_summary = summarize_by_cluster(items)
        self.assertTrue(topic_summary)
        self.assertTrue(cluster_summary)

    def test_fetch_items_with_parliamentary_filters(self) -> None:
        items = fetch_items_from_connection(
            self.connection,
            QueryFilters(motion_by="Solis", final_action="approved", limit=20),
        )
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].second_by, "Hahn")
        self.assertEqual(items[0].meeting_id, "meeting_test_1")

    def test_summarize_parliamentary(self) -> None:
        items = fetch_items_from_connection(self.connection, QueryFilters(limit=100))
        summary = summarize_parliamentary(items)
        self.assertEqual(summary["items_with_motion_by"], 1)
        self.assertEqual(summary["items_with_second_by"], 1)
        self.assertEqual(summary["items_with_final_action"], 1)
        self.assertEqual(summary["unanimous_votes"], 1)
        self.assertEqual(summary["motions_by_member"][0]["member"], "Solis")
        self.assertEqual(summary["final_actions"][0]["final_action"], "approved")

    def test_weekly_digest_output(self) -> None:
        items = fetch_items_from_connection(self.connection, QueryFilters(limit=100))
        digest = build_weekly_digest(items)
        markdown = render_weekly_digest_markdown(digest)
        self.assertIn("Weekly Digest", markdown)
        self.assertGreaterEqual(digest["item_count"], 1)


if __name__ == "__main__":
    unittest.main()
