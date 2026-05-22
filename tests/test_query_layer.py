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

    def test_weekly_digest_output(self) -> None:
        items = fetch_items_from_connection(self.connection, QueryFilters(limit=100))
        digest = build_weekly_digest(items)
        markdown = render_weekly_digest_markdown(digest)
        self.assertIn("Weekly Digest", markdown)
        self.assertGreaterEqual(digest["item_count"], 1)


if __name__ == "__main__":
    unittest.main()
