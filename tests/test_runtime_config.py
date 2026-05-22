from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from policy_tracker.runtime_config import load_runtime_config


class RuntimeConfigTests(unittest.TestCase):
    def test_load_runtime_config(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        config = load_runtime_config(repo_root / "configs" / "runtime.json")

        self.assertEqual(config.database_path.name, "policy_tracker.sqlite")
        self.assertIn("policy-tracker", str(config.data_root))


if __name__ == "__main__":
    unittest.main()
