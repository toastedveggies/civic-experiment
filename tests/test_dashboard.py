from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from policy_tracker.dashboard import build_dashboard_summary
from policy_tracker.dashboard import build_dashboard_summary_from_connection
from policy_tracker.findings import (
    generate_findings_from_connection,
)
from policy_tracker.query_layer import QueryFilters
from policy_tracker.source_loader import load_source_configs
from policy_tracker.sqlite_import import (
    STRUCTURED_TABLES_SQL,
    build_document_summaries,
    load_items_index,
    replace_structured_topics,
    upsert_structured_documents,
    upsert_structured_items,
)


class DashboardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.temp_path = self.repo_root / "local" / "dashboard_test_workspace"
        if self.temp_path.exists():
            shutil.rmtree(self.temp_path, ignore_errors=True)
        self.temp_path.mkdir(parents=True, exist_ok=True)
        self.db_path = self.temp_path / "dashboard.sqlite"
        self.config_dir = self.temp_path / "configs"
        self.state_dir = self.temp_path / "state"
        self.download_root = self.temp_path / "downloads" / "sample"
        self.structured_dir = self.temp_path / "structured" / "sample"
        self.config_dir.mkdir(exist_ok=True)
        self.state_dir.mkdir(exist_ok=True)
        self.download_root.mkdir(parents=True, exist_ok=True)
        self.structured_dir.mkdir(parents=True, exist_ok=True)

        (self.config_dir / "sample_source.yaml").write_text(
            "\n".join(
                [
                    "source_id: sample_source",
                    "source_name: Sample Source",
                    "jurisdiction: Test",
                    "government_level: city",
                    "body_name: Sample Body",
                    "source_type: test",
                    "collection_method: test",
                    "priority_level: high",
                    "status: active",
                    "parser: la_county_cluster_text",
                    f"download_root: {self.download_root.as_posix()}",
                    f"structured_output_dir: {self.structured_dir.as_posix()}",
                ]
            ),
            encoding="utf-8",
        )

        rows = load_items_index(
            self.repo_root / "local" / "structured" / "live_test" / "agenda_items.index.json"
        )
        rows = rows[:3]
        self.connection = sqlite3.connect(":memory:")
        self.connection.executescript(STRUCTURED_TABLES_SQL)
        upsert_structured_documents(
            self.connection,
            build_document_summaries(rows, "sample_source", self.structured_dir),
        )
        upsert_structured_items(self.connection, rows, "sample_source")
        replace_structured_topics(self.connection, rows)
        generate_findings_from_connection(self.connection, QueryFilters(source_id="sample_source", limit=10))
        self.connection.commit()

        (self.download_root / "retry_queue.json").write_text(
            json.dumps([{"target": "one"}]),
            encoding="utf-8",
        )
        (self.download_root / "manual_review_queue.json").write_text(
            json.dumps([{"target": "two"}, {"target": "three"}]),
            encoding="utf-8",
        )
        (self.state_dir / "sample_source.refresh_state.json").write_text(
            json.dumps(
                {
                    "files": {
                        "one": {
                            "recorded_at": "2026-06-01T12:00:00+00:00",
                            "path": "one",
                            "modified_time_ns": 1,
                            "size_bytes": 1,
                        }
                    }
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.connection.close()
        shutil.rmtree(self.temp_path, ignore_errors=True)

    def test_dashboard_summary_reports_source_health(self) -> None:
        summary = build_dashboard_summary_from_connection(
            connection=self.connection,
            sources=load_source_configs(self.config_dir),
            state_dir=self.state_dir,
            database_path=self.db_path,
        )

        self.assertEqual(summary["source_count"], 1)
        self.assertEqual(summary["active_source_count"], 1)
        self.assertEqual(summary["structured_items"], 3)
        self.assertEqual(summary["retry_queue_items"], 1)
        self.assertEqual(summary["manual_review_items"], 2)
        self.assertEqual(len(summary["recent_agendas"]), 1)
        self.assertEqual(summary["sources"][0]["latest_refresh_recorded_at"], "2026-06-01T12:00:00+00:00")
        self.assertGreaterEqual(summary["findings"], 1)


if __name__ == "__main__":
    unittest.main()
