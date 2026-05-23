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

        meeting_date_iso = connection.execute(
            "SELECT meeting_date_iso FROM structured_documents ORDER BY document_id LIMIT 1"
        ).fetchone()[0]
        self.assertEqual(meeting_date_iso, "2026-05-20")

    def test_import_helpers_backfill_meeting_date_iso_from_legacy_rows(self) -> None:
        rows = load_items_index(self.index_path)
        legacy_rows = []
        for row in rows:
            legacy_row = dict(row)
            legacy_row.pop("meeting_date_iso", None)
            legacy_rows.append(legacy_row)
        summaries = build_document_summaries(legacy_rows, "la_county_board_agendas", self.index_path.parent)

        connection = sqlite3.connect(":memory:")
        connection.executescript(
            """
            CREATE TABLE structured_documents (
                document_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                source_path TEXT NOT NULL,
                cluster_name TEXT,
                meeting_date TEXT,
                item_count INTEGER NOT NULL,
                structured_json_path TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE structured_agenda_items (
                agenda_item_id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                source_path TEXT NOT NULL,
                cluster_name TEXT,
                meeting_date TEXT,
                section_number TEXT,
                section_title TEXT,
                item_label TEXT,
                item_type TEXT,
                title TEXT NOT NULL,
                speakers_json TEXT NOT NULL,
                text_block TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE structured_item_topics (
                agenda_item_id TEXT NOT NULL,
                topic_tag TEXT NOT NULL,
                PRIMARY KEY (agenda_item_id, topic_tag)
            );
            """
        )
        from policy_tracker.sqlite_import import ensure_structured_tables

        ensure_structured_tables(connection)
        upsert_structured_documents(connection, summaries)
        upsert_structured_items(connection, legacy_rows, "la_county_board_agendas")

        document_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(structured_documents)").fetchall()
        }
        item_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(structured_agenda_items)").fetchall()
        }
        self.assertIn("meeting_date_iso", document_columns)
        self.assertIn("meeting_date_iso", item_columns)

        document_iso = connection.execute(
            "SELECT meeting_date_iso FROM structured_documents ORDER BY document_id LIMIT 1"
        ).fetchone()[0]
        item_iso = connection.execute(
            "SELECT meeting_date_iso FROM structured_agenda_items ORDER BY agenda_item_id LIMIT 1"
        ).fetchone()[0]
        self.assertEqual(document_iso, "2026-05-20")
        self.assertEqual(item_iso, "2026-05-20")


if __name__ == "__main__":
    unittest.main()
