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


if __name__ == "__main__":
    unittest.main()
