from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from policy_tracker.cli import build_parser


class CliTests(unittest.TestCase):
    def test_about_command_is_registered(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["about"])
        self.assertEqual(args.command, "about")

    def test_list_sources_accepts_config_dir(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["list-sources", "--config-dir", str(Path("configs"))])
        self.assertEqual(args.command, "list-sources")

    def test_validate_source_log_command_is_registered(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["validate-source-log"])
        self.assertEqual(args.command, "validate-source-log")

    def test_list_source_log_command_accepts_filters(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["list-source-log", "--activation-stage", "active"])
        self.assertEqual(args.command, "list-source-log")
        self.assertEqual(args.activation_stage, "active")

    def test_sync_source_config_command_is_registered(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["sync-source-config", "la_city_primegov_archive", "--write"])
        self.assertEqual(args.command, "sync-source-config")
        self.assertTrue(args.write)

    def test_activate_source_command_is_registered(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["activate-source", "la_city_primegov_archive"])
        self.assertEqual(args.command, "activate-source")

    def test_check_online_source_command_is_registered(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["check-online-source", "la_city_primegov_archive", "--skip-findings", "--download-only"])
        self.assertEqual(args.command, "check-online-source")
        self.assertTrue(args.skip_findings)
        self.assertTrue(args.download_only)

    def test_list_parsers_command_is_registered(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["list-parsers"])
        self.assertEqual(args.command, "list-parsers")

    def test_dashboard_summary_command_is_registered(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["dashboard-summary", "--db-path", "local/policy_tracker.sqlite"])
        self.assertEqual(args.command, "dashboard-summary")

    def test_serve_dashboard_command_is_registered(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["serve-dashboard", "--port", "8766", "--quiet"])
        self.assertEqual(args.command, "serve-dashboard")
        self.assertEqual(args.port, 8766)
        self.assertTrue(args.quiet)

    def test_inspect_gmail_message_command_is_registered(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "inspect-gmail-message",
                "la_county_board_agendas",
                str(Path("tests/fixtures/gmail_board_agenda.json")),
            ]
        )
        self.assertEqual(args.command, "inspect-gmail-message")

    def test_download_message_links_command_is_registered(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "download-message-links",
                "la_county_board_agendas",
                str(Path("tests/fixtures/gmail_board_agenda.json")),
            ]
        )
        self.assertEqual(args.command, "download-message-links")

    def test_extract_items_command_is_registered(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "extract-items",
                str(Path("tests/fixtures/community_services_sample.txt")),
            ]
        )
        self.assertEqual(args.command, "extract-items")

    def test_persist_items_command_is_registered(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "persist-items",
                str(Path("tests/fixtures/community_services_sample.txt")),
            ]
        )
        self.assertEqual(args.command, "persist-items")

    def test_import_structured_items_command_is_registered(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "import-structured-items",
                str(Path("local/structured/live_test/agenda_items.index.json")),
            ]
        )
        self.assertEqual(args.command, "import-structured-items")

    def test_backfill_ceo_supporting_docs_command_is_registered(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["backfill-ceo-supporting-docs", "--inventory-only"])
        self.assertEqual(args.command, "backfill-ceo-supporting-docs")
        self.assertTrue(args.inventory_only)

    def test_list_items_command_is_registered(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["list-items", "--source-id", "la_county_board_agendas", "--topic", "housing"])
        self.assertEqual(args.command, "list-items")

    def test_weekly_digest_command_is_registered(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["weekly-digest", "--format", "json"])
        self.assertEqual(args.command, "weekly-digest")

    def test_generate_findings_command_is_registered(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["generate-findings", "--cluster", "Public Safety Cluster"])
        self.assertEqual(args.command, "generate-findings")

    def test_list_findings_command_is_registered(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["list-findings", "--priority", "high"])
        self.assertEqual(args.command, "list-findings")

    def test_refresh_source_command_is_registered(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["refresh-source", "la_county_board_agendas"])
        self.assertEqual(args.command, "refresh-source")

    def test_refresh_supporting_docs_command_is_registered(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["refresh-supporting-docs", "la_county_ceo_agendas"])
        self.assertEqual(args.command, "refresh-supporting-docs")


if __name__ == "__main__":
    unittest.main()
