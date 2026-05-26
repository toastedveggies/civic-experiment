from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from policy_tracker.sqlite_import import (
    STRUCTURED_TABLES_SQL,
    backfill_structured_date_metadata,
    build_document_summaries,
    build_meeting_summaries,
    load_items_index,
    replace_structured_topics,
    upsert_meetings,
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
        upsert_meetings(connection, build_meeting_summaries(rows, "la_county_board_agendas"))
        upsert_structured_documents(connection, summaries)
        upsert_structured_items(connection, rows, "la_county_board_agendas")
        replace_structured_topics(connection, rows)

        document_count = connection.execute("SELECT COUNT(*) FROM structured_documents").fetchone()[0]
        item_count = connection.execute("SELECT COUNT(*) FROM structured_agenda_items").fetchone()[0]
        topic_count = connection.execute("SELECT COUNT(*) FROM structured_item_topics").fetchone()[0]

        self.assertEqual(document_count, 3)
        self.assertEqual(item_count, len(rows))
        self.assertGreater(topic_count, 0)
        meeting_count = connection.execute("SELECT COUNT(*) FROM meetings").fetchone()[0]
        self.assertGreater(meeting_count, 0)

        meeting_date_iso = connection.execute(
            "SELECT meeting_date_iso FROM structured_documents ORDER BY document_id LIMIT 1"
        ).fetchone()[0]
        self.assertEqual(meeting_date_iso, "2026-05-20")
        document_role = connection.execute(
            "SELECT document_role FROM structured_documents ORDER BY document_id LIMIT 1"
        ).fetchone()[0]
        self.assertEqual(document_role, "agenda")

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
        self.assertIn("meeting_id", document_columns)
        self.assertIn("document_role", document_columns)
        self.assertIn("motion_by", item_columns)
        self.assertIn("ayes_members_json", item_columns)

        document_iso = connection.execute(
            "SELECT meeting_date_iso FROM structured_documents ORDER BY document_id LIMIT 1"
        ).fetchone()[0]
        item_iso = connection.execute(
            "SELECT meeting_date_iso FROM structured_agenda_items ORDER BY agenda_item_id LIMIT 1"
        ).fetchone()[0]
        self.assertEqual(document_iso, "2026-05-20")
        self.assertEqual(item_iso, "2026-05-20")

    def test_backfill_structured_date_metadata_updates_existing_rows(self) -> None:
        tmp_handle = tempfile.NamedTemporaryFile(prefix="policy_tracker_backfill_dates_", suffix=".sqlite", delete=False)
        tmp_handle.close()
        tmp_db = Path(tmp_handle.name)
        connection = None
        try:
            connection = sqlite3.connect(str(tmp_db))
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
                """
            )
            connection.execute(
                """
                INSERT INTO structured_documents (
                    document_id, source_id, source_path, cluster_name, meeting_date, item_count, structured_json_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("doc_1", "test_source", "sample.txt", "Community Services Cluster", "May 20, 2026", 1, "sample.json"),
            )
            connection.execute(
                """
                INSERT INTO structured_agenda_items (
                    agenda_item_id, document_id, source_id, source_path, cluster_name, meeting_date,
                    section_number, section_title, item_label, item_type, title, speakers_json, text_block
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "item_1",
                    "doc_1",
                    "test_source",
                    "sample.txt",
                    "Community Services Cluster",
                    "Wednesday, May 21, 2025",
                    "1",
                    "ITEM(S)",
                    "A",
                    "other",
                    "Sample Title",
                    "[]",
                    "Sample text",
                ),
            )
            connection.commit()
            connection.close()

            summary = backfill_structured_date_metadata(tmp_db)

            self.assertEqual(summary["documents_updated"], 1)
            self.assertEqual(summary["items_updated"], 1)

            connection = sqlite3.connect(str(tmp_db))
            document_iso = connection.execute(
                "SELECT meeting_date_iso FROM structured_documents WHERE document_id = 'doc_1'"
            ).fetchone()[0]
            item_iso = connection.execute(
                "SELECT meeting_date_iso FROM structured_agenda_items WHERE agenda_item_id = 'item_1'"
            ).fetchone()[0]
            connection.close()
            connection = None

            self.assertEqual(document_iso, "2026-05-20")
            self.assertEqual(item_iso, "2025-05-21")
        finally:
            if connection is not None:
                connection.close()
            if tmp_db.exists():
                try:
                    tmp_db.unlink()
                except PermissionError:
                    pass

    def test_import_helpers_remove_stale_items_for_reimported_documents(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.executescript(STRUCTURED_TABLES_SQL)

        original_rows = [
            {
                "agenda_item_id": "item_old",
                "document_id": "doc_1",
                "source_path": "sample.txt",
                "cluster_name": "Community Services Cluster",
                "meeting_date": "May 20, 2026",
                "section_number": "1",
                "section_title": "ITEM(S)",
                "item_label": "A",
                "item_type": "other",
                "title": "Old Title",
                "speakers": [],
                "text_block": "Old text",
                "topic_tags": ["governance"],
            }
        ]
        updated_rows = [
            {
                "agenda_item_id": "item_new",
                "document_id": "doc_1",
                "source_path": "sample.txt",
                "cluster_name": "Community Services Cluster",
                "meeting_date": "May 20, 2026",
                "section_number": "1",
                "section_title": "ITEM(S)",
                "item_label": "A",
                "item_type": "other",
                "title": "New Title",
                "speakers": [],
                "text_block": "New text",
                "topic_tags": ["governance"],
            }
        ]

        original_summaries = build_document_summaries(original_rows, "test_source", self.index_path.parent)
        upsert_structured_documents(connection, original_summaries)
        upsert_structured_items(connection, original_rows, "test_source")
        replace_structured_topics(connection, original_rows)

        updated_summaries = build_document_summaries(updated_rows, "test_source", self.index_path.parent)
        upsert_structured_documents(connection, updated_summaries)
        from policy_tracker.sqlite_import import remove_stale_structured_items_for_documents

        remove_stale_structured_items_for_documents(connection, updated_rows)
        upsert_structured_items(connection, updated_rows, "test_source")
        replace_structured_topics(connection, updated_rows)

        item_ids = {
            row[0]
            for row in connection.execute("SELECT agenda_item_id FROM structured_agenda_items").fetchall()
        }
        self.assertEqual(item_ids, {"item_new"})


if __name__ == "__main__":
    unittest.main()
