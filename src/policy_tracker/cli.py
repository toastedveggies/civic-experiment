from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from policy_tracker.downloader import download_assessed_message_targets, write_manifest
from policy_tracker.findings import (
    FindingFilters,
    fetch_findings,
    generate_findings,
)
from policy_tracker.ingestion import assess_gmail_message_file, ingest_gmail_message_file
from policy_tracker.item_extraction import extract_agenda_items_from_text_path, list_parsers, write_structured_items
from policy_tracker.query_layer import (
    QueryFilters,
    build_weekly_digest,
    fetch_items,
    render_weekly_digest_markdown,
    summarize_by_cluster,
    summarize_by_topic,
)
from policy_tracker.refresh import refresh_source
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
    subparsers.add_parser("list-parsers", help="List registered agenda parser families.")

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

    ingest_email_parser = subparsers.add_parser(
        "ingest-gmail-message",
        help="Run a source-specific Gmail intake flow from a saved Gmail message JSON file.",
    )
    ingest_email_parser.add_argument("source_id", help="Source id from the source registry.")
    ingest_email_parser.add_argument("message_json", type=Path, help="Path to Gmail message JSON.")
    ingest_email_parser.add_argument(
        "--config-dir",
        default=Path("configs/sources"),
        type=Path,
        help="Path to source config directory.",
    )
    ingest_email_parser.add_argument(
        "--db-path",
        type=Path,
        default=None,
        help="Optional SQLite path. Defaults to the runtime-configured database path.",
    )
    ingest_email_parser.add_argument(
        "--download-root",
        type=Path,
        default=None,
        help="Optional source-specific download root override.",
    )
    ingest_email_parser.add_argument(
        "--structured-output-dir",
        type=Path,
        default=None,
        help="Optional source-specific structured output directory override.",
    )

    extract_parser = subparsers.add_parser(
        "extract-items",
        help="Extract structured agenda items from an extracted text file.",
    )
    extract_parser.add_argument("text_path", type=Path, help="Path to extracted agenda text file.")
    extract_parser.add_argument(
        "--parser",
        default=None,
        help="Optional parser name. Defaults to auto-detection.",
    )
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
    batch_parser.add_argument(
        "--parser",
        default=None,
        help="Optional parser name to use for every supplied text file.",
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

    list_parser = subparsers.add_parser(
        "list-items",
        help="Query structured agenda items from SQLite in a UI-friendly JSON format.",
    )
    list_parser.add_argument("--db-path", type=Path, default=None, help="Optional SQLite path.")
    list_parser.add_argument("--source-id", default=None, help="Filter by source id.")
    list_parser.add_argument("--topic", default=None, help="Filter by topic tag.")
    list_parser.add_argument("--cluster", default=None, help="Filter by exact cluster name.")
    list_parser.add_argument("--meeting-date", default=None, help="Filter by meeting date text.")
    list_parser.add_argument("--search", default=None, help="Filter by title/text search.")
    list_parser.add_argument("--limit", type=int, default=50, help="Maximum rows to return.")

    digest_parser = subparsers.add_parser(
        "weekly-digest",
        help="Generate a first weekly digest from structured agenda items.",
    )
    digest_parser.add_argument("--db-path", type=Path, default=None, help="Optional SQLite path.")
    digest_parser.add_argument("--source-id", default=None, help="Optional source id filter.")
    digest_parser.add_argument("--topic", default=None, help="Optional topic filter.")
    digest_parser.add_argument("--cluster", default=None, help="Optional cluster filter.")
    digest_parser.add_argument("--meeting-date", default=None, help="Optional meeting date filter.")
    digest_parser.add_argument("--search", default=None, help="Optional title/text search filter.")
    digest_parser.add_argument("--limit", type=int, default=100, help="Maximum rows to consider.")
    digest_parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="markdown",
        help="Digest output format.",
    )

    findings_parser = subparsers.add_parser(
        "generate-findings",
        help="Generate first-pass findings from structured agenda items already in SQLite.",
    )
    findings_parser.add_argument("--db-path", type=Path, default=None, help="Optional SQLite path.")
    findings_parser.add_argument("--source-id", default=None, help="Optional source id filter.")
    findings_parser.add_argument("--topic", default=None, help="Optional topic filter.")
    findings_parser.add_argument("--cluster", default=None, help="Optional cluster filter.")
    findings_parser.add_argument("--meeting-date", default=None, help="Optional meeting date filter.")
    findings_parser.add_argument("--search", default=None, help="Optional title/text search filter.")
    findings_parser.add_argument("--limit", type=int, default=100, help="Maximum rows to consider.")

    list_findings_parser = subparsers.add_parser(
        "list-findings",
        help="Query generated findings in a UI-friendly JSON format.",
    )
    list_findings_parser.add_argument("--db-path", type=Path, default=None, help="Optional SQLite path.")
    list_findings_parser.add_argument("--source-id", default=None, help="Filter by source id.")
    list_findings_parser.add_argument("--topic", default=None, help="Filter by topic tag.")
    list_findings_parser.add_argument("--cluster", default=None, help="Filter by exact cluster name.")
    list_findings_parser.add_argument("--meeting-date", default=None, help="Filter by meeting date text.")
    list_findings_parser.add_argument("--priority", default=None, help="Filter by priority level.")
    list_findings_parser.add_argument("--search", default=None, help="Filter by title/summary search.")
    list_findings_parser.add_argument("--limit", type=int, default=50, help="Maximum rows to return.")

    refresh_parser = subparsers.add_parser(
        "refresh-source",
        help="Scan a source-specific download root for new text artifacts, then import and analyze them.",
    )
    refresh_parser.add_argument("source_id", help="Source id from the source registry.")
    refresh_parser.add_argument(
        "--config-dir",
        default=Path("configs/sources"),
        type=Path,
        help="Path to source config directory.",
    )
    refresh_parser.add_argument(
        "--state-dir",
        default=Path("local/state"),
        type=Path,
        help="Directory for refresh-state tracking files.",
    )
    refresh_parser.add_argument("--db-path", type=Path, default=None, help="Optional SQLite path.")
    refresh_parser.add_argument(
        "--skip-findings",
        action="store_true",
        help="Import new items without regenerating source findings.",
    )
    refresh_parser.add_argument(
        "--findings-limit",
        type=int,
        default=10000,
        help="Maximum number of source rows to consider when regenerating findings.",
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

    if args.command == "list-parsers":
        print(json.dumps({"parsers": list_parsers()}, indent=2))
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

    if args.command == "ingest-gmail-message":
        summary = ingest_gmail_message_file(
            source_id=args.source_id,
            message_path=args.message_json,
            config_dir=args.config_dir,
            db_path=args.db_path,
            download_root=args.download_root,
            structured_output_dir=args.structured_output_dir,
        )
        print(json.dumps(summary, indent=2))
        return 0

    if args.command == "extract-items":
        document = extract_agenda_items_from_text_path(args.text_path, parser_name=args.parser)
        if args.output_path is not None:
            write_structured_items(document, args.output_path)
        print(json.dumps(document.to_dict(), indent=2))
        return 0

    if args.command == "persist-items":
        documents = [materialize_structured_document(path, parser_name=args.parser) for path in args.text_paths]
        documents = [document for document in documents if document.item_count > 0]
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
                    "parser": args.parser,
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

    if args.command == "list-items":
        filters = QueryFilters(
            source_id=args.source_id,
            topic=args.topic,
            cluster=args.cluster,
            meeting_date=args.meeting_date,
            search=args.search,
            limit=args.limit,
        )
        items = fetch_items(db_path=args.db_path, filters=filters)
        print(
            json.dumps(
                {
                    "filters": asdict(filters),
                    "count": len(items),
                    "cluster_summary": summarize_by_cluster(items),
                    "topic_summary": summarize_by_topic(items),
                    "items": [item.to_dict() for item in items],
                },
                indent=2,
            )
        )
        return 0

    if args.command == "weekly-digest":
        filters = QueryFilters(
            source_id=args.source_id,
            topic=args.topic,
            cluster=args.cluster,
            meeting_date=args.meeting_date,
            search=args.search,
            limit=args.limit,
        )
        items = fetch_items(db_path=args.db_path, filters=filters)
        digest = build_weekly_digest(items)
        if args.format == "json":
            print(json.dumps(digest, indent=2))
        else:
            print(render_weekly_digest_markdown(digest))
        return 0

    if args.command == "generate-findings":
        filters = QueryFilters(
            source_id=args.source_id,
            topic=args.topic,
            cluster=args.cluster,
            meeting_date=args.meeting_date,
            search=args.search,
            limit=args.limit,
        )
        summary = generate_findings(db_path=args.db_path, filters=filters)
        print(json.dumps(summary, indent=2))
        return 0

    if args.command == "list-findings":
        filters = FindingFilters(
            source_id=args.source_id,
            topic=args.topic,
            cluster=args.cluster,
            meeting_date=args.meeting_date,
            priority=args.priority,
            search=args.search,
            limit=args.limit,
        )
        findings = fetch_findings(db_path=args.db_path, filters=filters)
        print(
            json.dumps(
                {
                    "filters": asdict(filters),
                    "count": len(findings),
                    "findings": [finding.to_dict() for finding in findings],
                },
                indent=2,
            )
        )
        return 0

    if args.command == "refresh-source":
        summary = refresh_source(
            source_id=args.source_id,
            config_dir=args.config_dir,
            state_dir=args.state_dir,
            db_path=args.db_path,
            skip_findings=args.skip_findings,
            findings_limit=args.findings_limit,
        )
        print(json.dumps(summary, indent=2))
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
