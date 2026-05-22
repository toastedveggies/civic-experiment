from __future__ import annotations

import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from policy_tracker.sqlite_import import (
    STRUCTURED_TABLES_SQL,
    build_document_summaries,
    load_items_index,
    replace_structured_topics,
    upsert_structured_documents,
    upsert_structured_items,
)


class SqliteImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.index_path = self.repo_root / "local" / "structured" / "live_test" / "agenda_items.index.json"

    def test_document_summary_builder_groups_rows(self) -> None:
        rows = load_items_index(self.index_path)
        summaries = build_document_summaries(rows, "la_county_board_agendas", self.index_path.parent)

        self.assertEqual(len(summaries), 3)
        self.assertEqual(sum(summary["item_count"] for summary in summaries), len(rows))

    def test_import_helpers_write_rows(self) -> None:
        rows = load_items_index(self.index_path)
        summaries = build_document_summaries(rows, "la_county_board_agendas", self.index_path.parent)

        connection = sqlite3.connect(":memory:")
        connection.executescript(STRUCTURED_TABLES_SQL)
        upsert_structured_documents(connection, summaries)
        upsert_structured_items(connection, rows, "la_county_board_agendas")
        replace_structured_topics(connection, rows)

        document_count = connection.execute("SELECT COUNT(*) FROM structured_documents").fetchone()[0]
        item_count = connection.execute("SELECT COUNT(*) FROM structured_agenda_items").fetchone()[0]
        topic_count = connection.execute("SELECT COUNT(*) FROM structured_item_topics").fetchone()[0]

        self.assertEqual(document_count, 3)
        self.assertEqual(item_count, len(rows))
        self.assertGreater(topic_count, 0)


if __name__ == "__main__":
    unittest.main()
