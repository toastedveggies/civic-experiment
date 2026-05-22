from __future__ import annotations

import argparse
import json
from pathlib import Path

from policy_tracker.downloader import download_assessed_message_targets, write_manifest
from policy_tracker.ingestion import assess_gmail_message_file
from policy_tracker.item_extraction import extract_agenda_items_from_text_path, write_structured_items
from policy_tracker.storage import (
    build_items_index,
    materialize_structured_document,
    write_items_index,
    write_structured_document,
)
from policy_tracker.sqlite_import import import_items_index
from policy_tracker.source_loader import load_source_configs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="policy-tracker",
        description="Utilities for the Policy Tracker project.",
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("about", help="Show a short project description.")

    sources_parser = subparsers.add_parser(
        "list-sources",
        help="List source registry files currently checked into the repo.",
    )
    sources_parser.add_argument(
        "--config-dir",
        default=Path("configs/sources"),
        type=Path,
        help="Path to source config directory.",
    )

    inspect_parser = subparsers.add_parser(
        "inspect-gmail-message",
        help="Normalize a saved Gmail message JSON file using a configured source adapter.",
    )
    inspect_parser.add_argument("source_id", help="Source id from the source registry.")
    inspect_parser.add_argument("message_json", type=Path, help="Path to Gmail message JSON.")
    inspect_parser.add_argument(
        "--config-dir",
        default=Path("configs/sources"),
        type=Path,
        help="Path to source config directory.",
    )

    download_parser = subparsers.add_parser(
        "download-message-links",
        help="Download categorized agenda-linked documents from a saved Gmail message JSON file.",
    )
    download_parser.add_argument("source_id", help="Source id from the source registry.")
    download_parser.add_argument("message_json", type=Path, help="Path to Gmail message JSON.")
    download_parser.add_argument(
        "--config-dir",
        default=Path("configs/sources"),
        type=Path,
        help="Path to source config directory.",
    )
    download_parser.add_argument(
        "--output-dir",
        default=Path("local/downloads"),
        type=Path,
        help="Base directory for downloaded files and metadata.",
    )
    download_parser.add_argument(
        "--max-fetch-attempts",
        default=2,
        type=int,
        help="Maximum number of fetch attempts per target before queuing retry or failure.",
    )

    extract_parser = subparsers.add_parser(
        "extract-items",
        help="Extract structured agenda items from an extracted text file.",
    )
    extract_parser.add_argument("text_path", type=Path, help="Path to extracted agenda text file.")
    extract_parser.add_argument(
        "--output-path",
        type=Path,
        default=None,
        help="Optional path for structured JSON output.",
    )

    batch_parser = subparsers.add_parser(
        "persist-items",
        help="Build structured document JSON and a flat item index from extracted text files.",
    )
    batch_parser.add_argument(
        "text_paths",
        nargs="+",
        type=Path,
        help="One or more extracted text files.",
    )
    batch_parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("local/structured"),
        help="Directory where structured document JSON files and item index will be written.",
    )

    import_parser = subparsers.add_parser(
        "import-structured-items",
        help="Import a structured agenda item index into the configured SQLite database.",
    )
    import_parser.add_argument("index_path", type=Path, help="Path to agenda_items.index.json.")
    import_parser.add_argument(
        "--db-path",
        type=Path,
        default=None,
        help="Optional SQLite path. Defaults to the runtime-configured database path.",
    )
    import_parser.add_argument(
        "--source-id",
        default="la_county_board_agendas",
        help="Source id to stamp onto imported structured documents and items.",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "about":
        print(
            "Policy Tracker is a local-first pipeline for collecting, "
            "analyzing, and tracking public-sector policy documents over time."
        )
        return 0

    if args.command == "list-sources":
        for config in load_source_configs(args.config_dir):
            print(config.source_id)
        return 0

    if args.command == "inspect-gmail-message":
        assessment = assess_gmail_message_file(
            source_id=args.source_id,
            message_path=args.message_json,
            config_dir=args.config_dir,
        )
        print(json.dumps(assessment.to_dict(), indent=2))
        return 0

    if args.command == "download-message-links":
        results = download_assessed_message_targets(
            source_id=args.source_id,
            message_path=args.message_json,
            config_dir=args.config_dir,
            output_dir=args.output_dir,
            max_fetch_attempts=args.max_fetch_attempts,
        )
        manifest_path = args.output_dir / "manifest.json"
        write_manifest(results, manifest_path)
        print(
            json.dumps(
                {
                    "summary": {
                        "total": len(results),
                        "ready": len([item for item in results if item.processing_status == "ready"]),
                        "needs_retry": len([item for item in results if item.processing_status == "needs_retry"]),
                        "needs_manual_review": len(
                            [item for item in results if item.review_status == "needs_manual_review"]
                        ),
                    },
                    "manifest_path": str(manifest_path),
                    "documents": [result.to_dict() for result in results],
                },
                indent=2,
            )
        )
        return 0

    if args.command == "extract-items":
        document = extract_agenda_items_from_text_path(args.text_path)
        if args.output_path is not None:
            write_structured_items(document, args.output_path)
        print(json.dumps(document.to_dict(), indent=2))
        return 0

    if args.command == "persist-items":
        documents = [materialize_structured_document(path) for path in args.text_paths]
        output_dir = args.output_dir
        for document in documents:
            source_name = Path(document.source_path).stem
            output_path = output_dir / f"{source_name}.structured.json"
            write_structured_document(document, output_path)
        index_rows = build_items_index(documents)
        index_path = output_dir / "agenda_items.index.json"
        write_items_index(index_rows, index_path)
        print(
            json.dumps(
                {
                    "documents_written": len(documents),
                    "items_written": len(index_rows),
                    "output_dir": str(output_dir),
                    "index_path": str(index_path),
                },
                indent=2,
            )
        )
        return 0

    if args.command == "import-structured-items":
        summary = import_items_index(
            index_path=args.index_path,
            db_path=args.db_path,
            source_id=args.source_id,
        )
        print(json.dumps(summary, indent=2))
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
