from __future__ import annotations

import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from policy_tracker.findings import (
    FindingFilters,
    classify_action,
    fetch_findings_from_connection,
    generate_findings_from_connection,
)
from policy_tracker.query_layer import QueryFilters, fetch_items_from_connection
from policy_tracker.sqlite_import import (
    STRUCTURED_TABLES_SQL,
    build_document_summaries,
    load_items_index,
    replace_structured_topics,
    upsert_structured_documents,
    upsert_structured_items,
)


class FindingsTests(unittest.TestCase):
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

    def test_generate_findings_writes_rows(self) -> None:
        summary = generate_findings_from_connection(self.connection, QueryFilters(limit=100))
        findings = fetch_findings_from_connection(self.connection, FindingFilters(limit=100))

        self.assertEqual(summary["items_considered"], 22)
        self.assertEqual(summary["findings_written"], 22)
        self.assertEqual(len(findings), 22)

    def test_generated_finding_has_useful_fields(self) -> None:
        generate_findings_from_connection(self.connection, QueryFilters(cluster="Public Safety Cluster", limit=20))
        findings = fetch_findings_from_connection(
            self.connection,
            FindingFilters(cluster="Public Safety Cluster", priority="high", limit=20),
        )

        self.assertTrue(findings)
        self.assertTrue(any("closer review" in finding.why_it_matters for finding in findings))
        self.assertTrue(all(finding.priority_level == "high" for finding in findings))

    def test_classify_action_detects_sole_source_items(self) -> None:
        items = fetch_items_from_connection(self.connection, QueryFilters(search="sole source", limit=5))

        self.assertTrue(items)
        self.assertIn("sole_source_contract", {classify_action(item) for item in items})


if __name__ == "__main__":
    unittest.main()
