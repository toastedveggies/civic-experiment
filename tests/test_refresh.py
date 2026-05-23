from __future__ import annotations

import shutil
import sys
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from policy_tracker.refresh import classify_text_path_for_refresh, refresh_source
from policy_tracker.source_loader import get_source_config


class RefreshSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.fixture_path = self.repo_root / "tests" / "fixtures" / "community_services_sample.txt"

    def test_refresh_source_imports_new_text_and_skips_unchanged_second_run(self) -> None:
        tmp_dir = self.repo_root / "local" / "tmp_refresh_test"
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            tmp_dir.mkdir(parents=True, exist_ok=True)
            download_root = tmp_dir / "downloads"
            structured_root = tmp_dir / "structured"
            state_root = tmp_dir / "state"
            db_path = tmp_dir / "refresh.sqlite"
            config_dir = tmp_dir / "configs"
            config_dir.mkdir(parents=True, exist_ok=True)

            source_dir = download_root / "message_001"
            source_dir.mkdir(parents=True, exist_ok=True)
            copied_text = source_dir / self.fixture_path.name
            copied_text.write_text(self.fixture_path.read_text(encoding="utf-8"), encoding="utf-8")

            config_path = config_dir / "test_source.yaml"
            config_path.write_text(
                textwrap.dedent(
                    f"""
                    source_id: test_source
                    source_name: Test Source
                    jurisdiction: Test
                    government_level: county
                    body_name: Test Body
                    source_type: hybrid
                    collection_method: gmail_attachment_or_link
                    priority_level: high
                    status: active
                    download_root: {download_root}
                    structured_output_dir: {structured_root}
                    """
                ).strip(),
                encoding="utf-8",
            )

            with (
                patch(
                    "policy_tracker.refresh.import_items_index",
                    return_value={"documents_imported": 1, "items_imported": 3, "topics_imported": 3},
                ) as import_mock,
                patch(
                    "policy_tracker.refresh.generate_findings",
                    return_value={"items_considered": 3, "findings_written": 3, "high_priority_findings": 0},
                ) as findings_mock,
            ):
                first_summary = refresh_source(
                    source_id="test_source",
                    config_dir=config_dir,
                    state_dir=state_root,
                    db_path=db_path,
                    findings_limit=100,
                )
                second_summary = refresh_source(
                    source_id="test_source",
                    config_dir=config_dir,
                    state_dir=state_root,
                    db_path=db_path,
                    findings_limit=100,
                )

            self.assertEqual(first_summary["new_or_changed_text_files"], 1)
            self.assertEqual(first_summary["documents_written"], 1)
            self.assertEqual(first_summary["items_written"], 3)
            self.assertEqual(second_summary["new_or_changed_text_files"], 0)
            self.assertEqual(import_mock.call_count, 1)
            self.assertEqual(findings_mock.call_count, 1)
            self.assertTrue((structured_root / "community_services_sample.structured.json").exists())
            self.assertTrue((structured_root / "agenda_items.latest_refresh.index.json").exists())
            self.assertTrue((state_root / "test_source.refresh_state.json").exists())
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_city_companion_pdf_text_is_screened_out_when_html_twin_exists(self) -> None:
        source = get_source_config(self.repo_root / "configs" / "sources", "la_city_agendas")
        path = self.repo_root / "local" / "downloads" / "la_city_agendas" / "primegov" / "2025-05-21" / "city-council-meeting" / "2025-05-21_city-council-meeting_agenda.txt"
        decision = classify_text_path_for_refresh(source, path)
        self.assertFalse(decision.include)
        self.assertEqual(decision.reason, "non_canonical_companion")

    def test_cancellation_notice_is_screened_out(self) -> None:
        source = get_source_config(self.repo_root / "configs" / "sources", "la_county_ceo_agendas")
        path = self.repo_root / "local" / "downloads" / "la_county_ceo_agendas" / "ceo" / "2025-07-16" / "family-and-social-services-cluster" / "2025-07-16_family-and-social-services-cluster_july-16-2025-canceled.txt"
        decision = classify_text_path_for_refresh(source, path)
        self.assertFalse(decision.include)
        self.assertEqual(decision.reason, "cancellation_notice")


if __name__ == "__main__":
    unittest.main()
