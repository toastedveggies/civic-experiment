from __future__ import annotations

import shutil
import sys
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from policy_tracker.refresh import refresh_source


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


if __name__ == "__main__":
    unittest.main()
