from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from policy_tracker.la_city_email_ingestion import ingest_la_city_gmail_message_file


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingest a saved LA City Gmail agenda notice into local downloads and SQLite."
    )
    parser.add_argument("message_json", type=Path, help="Path to saved Gmail message JSON.")
    parser.add_argument("--config-dir", type=Path, default=REPO_ROOT / "configs" / "sources")
    parser.add_argument("--db-path", type=Path, default=None)
    parser.add_argument("--download-root", type=Path, default=None)
    parser.add_argument("--structured-output-dir", type=Path, default=None)
    args = parser.parse_args()

    summary = ingest_la_city_gmail_message_file(
        message_path=args.message_json,
        config_dir=args.config_dir,
        db_path=args.db_path,
        download_root=args.download_root,
        structured_output_dir=args.structured_output_dir,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
