from __future__ import annotations

import shutil
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from policy_tracker.source_log import (
    activate_source,
    check_online_source,
    list_source_log,
    load_source_log,
    sync_source_config_from_log,
    validate_source_log,
)


class SourceLogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.source_log_path = self.repo_root / "configs" / "source_log.yaml"
        self.config_dir = self.repo_root / "configs" / "sources"
        self.tmp_dir = self.repo_root / "tests" / "tmp_source_log"
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir, ignore_errors=True)
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_source_log_loads_and_validates(self) -> None:
        payload = load_source_log(self.source_log_path)
        self.assertGreaterEqual(len(payload["sources"]), 4)

        summary = validate_source_log(self.source_log_path)

        self.assertTrue(summary.valid, summary.errors)
        self.assertEqual(summary.body_count, 4)
        self.assertEqual(summary.activation_queue_count, 3)

    def test_list_source_log_filters_by_activation_stage(self) -> None:
        result = list_source_log(self.source_log_path, activation_stage="sampled")

        self.assertEqual(result["count"], 1)
        self.assertEqual(result["sources"][0]["source_ref"], "la_county_bos_live_agenda_page")

    def test_sync_source_config_reports_base_url_change(self) -> None:
        tmp_config_dir = self.tmp_dir / "configs"
        shutil.copytree(self.config_dir, tmp_config_dir, dirs_exist_ok=True)
        city_config = tmp_config_dir / "la_city_agendas.yaml"
        text = city_config.read_text(encoding="utf-8")
        city_config.write_text(text.replace("base_url: https://lacity.primegov.com/", "base_url: null"), encoding="utf-8")

        dry_run = sync_source_config_from_log(
            "la_city_primegov_archive",
            path=self.source_log_path,
            config_dir=tmp_config_dir,
            write=False,
        )
        self.assertTrue(dry_run["changed"])
        self.assertEqual(dry_run["changes"]["base_url"]["new"], "https://lacity.primegov.com/")

        written = sync_source_config_from_log(
            "la_city_primegov_archive",
            path=self.source_log_path,
            config_dir=tmp_config_dir,
            write=True,
        )
        self.assertTrue(written["changed"])
        self.assertIn("base_url: https://lacity.primegov.com/", city_config.read_text(encoding="utf-8"))

    def test_activate_source_can_create_download_root(self) -> None:
        source_log_copy = self.tmp_dir / "source_log.yaml"
        text = self.source_log_path.read_text(encoding="utf-8")
        text = text.replace("local/downloads/la_city_agendas", str(self.tmp_dir / "downloads" / "la_city_agendas"))
        source_log_copy.write_text(text, encoding="utf-8")

        summary = activate_source(
            "la_city_primegov_archive",
            path=source_log_copy,
            config_dir=self.config_dir,
            write=True,
        )

        self.assertTrue(summary["activated"])
        self.assertTrue((self.tmp_dir / "downloads" / "la_city_agendas").exists())

    def test_check_online_source_uses_log_schedule_and_refreshes(self) -> None:
        with patch(
            "policy_tracker.source_log.download_la_city_agendas_last_12_months",
            return_value={"documents_downloaded": 1},
        ) as download_mock, patch(
            "policy_tracker.source_log.refresh_source",
            return_value={"items_written": 2},
        ) as refresh_mock:
            summary = check_online_source(
                "la_city_primegov_archive",
                path=self.source_log_path,
                config_dir=self.config_dir,
                state_dir=Path("local/state_test"),
                db_path=Path("local/test.sqlite"),
                today=date(2026, 6, 2),
                skip_findings=True,
            )

        self.assertEqual(summary["from_date"], "2026-05-19")
        self.assertEqual(summary["to_date"], "2026-06-02")
        download_mock.assert_called_once()
        self.assertEqual(download_mock.call_args.kwargs["from_date"], "05-19-2026")
        self.assertEqual(download_mock.call_args.kwargs["to_date"], "06-02-2026")
        refresh_mock.assert_called_once()

    def test_check_online_source_supports_county_ceo_archive(self) -> None:
        with patch(
            "policy_tracker.source_log.download_county_ceo_agendas",
            return_value={"agendas_downloaded": 3},
        ) as download_mock, patch(
            "policy_tracker.source_log.refresh_source",
            return_value={"items_written": 5},
        ) as refresh_mock:
            summary = check_online_source(
                "la_county_ceo_agendas_archive",
                path=self.source_log_path,
                config_dir=self.config_dir,
                state_dir=Path("local/state_test"),
                db_path=Path("local/test.sqlite"),
                today=date(2026, 6, 2),
                skip_findings=True,
            )

        self.assertEqual(summary["from_date"], "2026-05-03")
        self.assertEqual(summary["to_date"], "2026-06-16")
        download_mock.assert_called_once()
        self.assertEqual(download_mock.call_args.kwargs["manifest_filename"], "ceo_incremental_manifest.json")
        self.assertFalse(download_mock.call_args.kwargs["include_supporting_documents"])
        self.assertIn("Community Services Cluster", download_mock.call_args.kwargs["requested_bodies"])
        refresh_mock.assert_called_once()

    def test_check_online_source_supports_bos_live_page(self) -> None:
        with patch(
            "policy_tracker.source_log.download_bos_current_agendas",
            return_value={"documents_downloaded": 4},
        ) as download_mock, patch(
            "policy_tracker.source_log.refresh_source",
            return_value={"items_written": 0},
        ) as refresh_mock:
            summary = check_online_source(
                "la_county_bos_live_agenda_page",
                path=self.source_log_path,
                config_dir=self.config_dir,
                state_dir=Path("local/state_test"),
                db_path=Path("local/test.sqlite"),
                today=date(2026, 6, 2),
                skip_findings=True,
            )

        self.assertEqual(summary["from_date"], "2026-02-02")
        self.assertEqual(summary["to_date"], "2026-06-02")
        download_mock.assert_called_once()
        self.assertEqual(download_mock.call_args.kwargs["from_date"], date(2026, 2, 2))
        self.assertEqual(download_mock.call_args.kwargs["to_date"], date(2026, 6, 2))
        self.assertEqual(download_mock.call_args.kwargs["manifest_filename"], "bos_current_manifest.json")
        refresh_mock.assert_called_once()

    def test_check_online_source_can_skip_refresh_for_download_only(self) -> None:
        with patch(
            "policy_tracker.source_log.download_bos_current_agendas",
            return_value={"documents_downloaded": 4},
        ) as download_mock, patch("policy_tracker.source_log.refresh_source") as refresh_mock:
            summary = check_online_source(
                "la_county_bos_live_agenda_page",
                path=self.source_log_path,
                config_dir=self.config_dir,
                state_dir=Path("local/state_test"),
                db_path=Path("local/test.sqlite"),
                today=date(2026, 6, 2),
                download_only=True,
            )

        self.assertTrue(summary["download_only"])
        self.assertIsNone(summary["refresh_summary"])
        download_mock.assert_called_once()
        refresh_mock.assert_not_called()

    def test_check_online_source_supports_lahsa_document_library(self) -> None:
        with patch(
            "policy_tracker.source_log.download_lahsa_documents",
            return_value={"documents_downloaded": 2},
        ) as download_mock, patch("policy_tracker.source_log.refresh_source") as refresh_mock:
            summary = check_online_source(
                "lahsa_document_library",
                path=self.source_log_path,
                config_dir=self.config_dir,
                state_dir=Path("local/state_test"),
                db_path=Path("local/test.sqlite"),
                today=date(2026, 6, 3),
                download_only=True,
            )

        self.assertEqual(summary["source_id"], "lahsa_documents")
        self.assertTrue(summary["download_only"])
        download_mock.assert_called_once()
        self.assertEqual(download_mock.call_args.kwargs["scope_ids"], ["106", "107"])
        self.assertIn("budget", download_mock.call_args.kwargs["keywords"])
        self.assertEqual(download_mock.call_args.kwargs["manifest_filename"], "lahsa_documents_manifest.json")
        refresh_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
