from __future__ import annotations

import argparse
import json
from pathlib import Path

from policy_tracker.la_county_bos_sop_import import import_bos_sop_manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import downloaded LA County BOS Statement of Proceedings PDFs into SQLite."
    )
    parser.add_argument(
        "manifest_path",
        type=Path,
        help="Path to the JSON manifest produced by download_la_county_bos_sop.ps1.",
    )
    parser.add_argument(
        "--source-id",
        default="la_county_bos_sop",
        help="Source id from the source registry.",
    )
    parser.add_argument(
        "--config-dir",
        default=Path("configs/sources"),
        type=Path,
        help="Path to source config directory.",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=None,
        help="Optional SQLite path. Defaults to the runtime-configured database path.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = import_bos_sop_manifest(
        manifest_path=args.manifest_path,
        source_id=args.source_id,
        config_dir=args.config_dir,
        db_path=args.db_path,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
