from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from policy_tracker.storage import (
    build_items_index,
    materialize_structured_document,
    write_items_index,
    write_structured_document,
)


class StorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_materialize_structured_document_builds_ids(self) -> None:
        path = self.repo_root / "tests" / "fixtures" / "public_safety_sample.txt"
        document = materialize_structured_document(path)

        self.assertTrue(document.document_id.startswith("doc_"))
        self.assertEqual(document.item_count, 3)
        self.assertTrue(all(item.document_id == document.document_id for item in document.items))
        self.assertTrue(all(item.agenda_item_id.startswith("item_") for item in document.items))

    def test_materialized_documents_and_index_include_meeting_date_iso(self) -> None:
        path = self.repo_root / "tests" / "fixtures" / "community_services_sample.txt"
        document = materialize_structured_document(path)

        self.assertEqual(document.meeting_date, "May 20, 2026")
        self.assertEqual(document.meeting_date_iso, "2026-05-20")

        rows = build_items_index([document])
        self.assertEqual(rows[0]["meeting_date"], "May 20, 2026")
        self.assertEqual(rows[0]["meeting_date_iso"], "2026-05-20")

    def test_write_structured_document_and_index(self) -> None:
        path_a = self.repo_root / "tests" / "fixtures" / "community_services_sample.txt"
        path_b = self.repo_root / "tests" / "fixtures" / "public_safety_sample.txt"
        doc_a = materialize_structured_document(path_a)
        doc_b = materialize_structured_document(path_b)
        output_dir = self.repo_root / "tests" / "tmp_structured"
        output_dir.mkdir(parents=True, exist_ok=True)

        doc_path = output_dir / "community_services_sample.structured.json"
        index_path = output_dir / "agenda_items.index.json"
        write_structured_document(doc_a, doc_path)
        write_items_index(build_items_index([doc_a, doc_b]), index_path)

        self.assertTrue(doc_path.exists())
        self.assertTrue(index_path.exists())

        stored_doc = json.loads(doc_path.read_text(encoding="utf-8"))
        stored_index = json.loads(index_path.read_text(encoding="utf-8"))
        self.assertEqual(stored_doc["item_count"], 3)
        self.assertEqual(stored_doc["meeting_date_iso"], "2026-05-20")
        self.assertEqual(len(stored_index), 6)
        self.assertEqual(stored_index[0]["meeting_date_iso"], "2026-05-20")


if __name__ == "__main__":
    unittest.main()
