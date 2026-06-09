from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from policy_tracker.dashboard_server import ASSET_DIR, create_dashboard_server


class DashboardServerTests(unittest.TestCase):
    def test_server_keeps_dashboard_paths(self) -> None:
        server = create_dashboard_server(port=0, quiet=True)
        try:
            self.assertIsNone(server.db_path)
            self.assertEqual(server.config_dir, Path("configs/sources"))
            self.assertEqual(server.state_dir, Path("local/state"))
        finally:
            server.server_close()

    def test_static_dashboard_assets_exist(self) -> None:
        self.assertTrue((ASSET_DIR / "index.html").exists())
        self.assertTrue((ASSET_DIR / "styles.css").exists())
        self.assertTrue((ASSET_DIR / "app.js").exists())


if __name__ == "__main__":
    unittest.main()
