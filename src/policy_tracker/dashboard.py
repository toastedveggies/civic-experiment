from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from policy_tracker.query_layer import get_database_path
from policy_tracker.source_loader import load_source_configs


@dataclass(slots=True)
class SourceHealthRecord:
    source_id: str
    source_name: str
    status: str
    priority_level: str
    download_root: str | None
    structured_output_dir: str | None
    raw_documents: int
    structured_documents: int
    structured_items: int
    findings: int
    high_priority_findings: int
    latest_document_date: str | None
    latest_structured_date: str | None
    latest_refresh_recorded_at: str | None
    retry_queue_items: int
    manual_review_items: int
    has_parser_config_warning: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_dashboard_summary(
    db_path: Path | None = None,
    config_dir: Path = Path("configs/sources"),
    state_dir: Path = Path("local/state"),
) -> dict[str, Any]:
    database_path = get_database_path(db_path)
    sources = load_source_configs(config_dir)
    with sqlite3.connect(database_path) as connection:
        return build_dashboard_summary_from_connection(
            connection=connection,
            sources=sources,
            state_dir=state_dir,
            database_path=database_path,
        )


def build_dashboard_summary_from_connection(
    connection: sqlite3.Connection,
    sources: list[Any],
    state_dir: Path = Path("local/state"),
    database_path: Path | None = None,
) -> dict[str, Any]:
    table_names = list_table_names(connection)
    source_rows = [
        build_source_health(connection, table_names, source, state_dir)
        for source in sources
    ]
    recent_agendas = fetch_recent_agendas(connection, table_names)
    top_findings = fetch_top_findings(connection, table_names)
    return {
        "database_path": str(database_path) if database_path else None,
        "source_count": len(source_rows),
        "active_source_count": len([row for row in source_rows if row.status == "active"]),
        "raw_documents": sum(row.raw_documents for row in source_rows),
        "structured_documents": sum(row.structured_documents for row in source_rows),
        "structured_items": sum(row.structured_items for row in source_rows),
        "findings": sum(row.findings for row in source_rows),
        "high_priority_findings": sum(row.high_priority_findings for row in source_rows),
        "retry_queue_items": sum(row.retry_queue_items for row in source_rows),
        "manual_review_items": sum(row.manual_review_items for row in source_rows),
        "sources_with_parser_config_warnings": len(
            [row for row in source_rows if row.has_parser_config_warning]
        ),
        "sources": [row.to_dict() for row in source_rows],
        "recent_agendas": recent_agendas,
        "top_findings": top_findings,
    }


def list_table_names(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    return {row[0] for row in rows}


def build_source_health(
    connection: sqlite3.Connection,
    table_names: set[str],
    source,
    state_dir: Path,
) -> SourceHealthRecord:
    raw_documents = count_where(
        connection,
        table_names,
        "documents",
        "source_id = ?",
        [source.source_id],
    )
    structured_documents = count_where(
        connection,
        table_names,
        "structured_documents",
        "source_id = ?",
        [source.source_id],
    )
    structured_items = count_where(
        connection,
        table_names,
        "structured_agenda_items",
        "source_id = ?",
        [source.source_id],
    )
    findings = count_where(
        connection,
        table_names,
        "structured_findings",
        "source_id = ?",
        [source.source_id],
    )
    high_priority_findings = count_where(
        connection,
        table_names,
        "structured_findings",
        "source_id = ? AND priority_level = ?",
        [source.source_id, "high"],
    )
    latest_document_date = max_text_value(
        connection,
        table_names,
        "documents",
        "meeting_date",
        "source_id = ? AND meeting_date IS NOT NULL AND TRIM(meeting_date) <> ''",
        [source.source_id],
    )
    latest_structured_date = latest_structured_meeting_date(
        connection,
        table_names,
        source.source_id,
    )
    retry_queue_items, manual_review_items = count_review_queues(source.download_root)

    return SourceHealthRecord(
        source_id=source.source_id,
        source_name=source.source_name,
        status=source.status,
        priority_level=source.priority_level,
        download_root=source.download_root,
        structured_output_dir=source.structured_output_dir,
        raw_documents=raw_documents,
        structured_documents=structured_documents,
        structured_items=structured_items,
        findings=findings,
        high_priority_findings=high_priority_findings,
        latest_document_date=latest_document_date,
        latest_structured_date=latest_structured_date,
        latest_refresh_recorded_at=latest_refresh_recorded_at(state_dir, source.source_id),
        retry_queue_items=retry_queue_items,
        manual_review_items=manual_review_items,
        has_parser_config_warning=has_parser_config_warning(source.parser),
    )


def count_where(
    connection: sqlite3.Connection,
    table_names: set[str],
    table_name: str,
    where_clause: str | None = None,
    params: list[Any] | None = None,
) -> int:
    if table_name not in table_names:
        return 0
    sql = f"SELECT COUNT(*) FROM {table_name}"
    if where_clause:
        sql += f" WHERE {where_clause}"
    return int(connection.execute(sql, params or []).fetchone()[0])


def max_text_value(
    connection: sqlite3.Connection,
    table_names: set[str],
    table_name: str,
    expression: str,
    where_clause: str,
    params: list[Any],
) -> str | None:
    if table_name not in table_names:
        return None
    row = connection.execute(
        f"SELECT MAX({expression}) FROM {table_name} WHERE {where_clause}",
        params,
    ).fetchone()
    return row[0] if row and row[0] else None


def latest_structured_meeting_date(
    connection: sqlite3.Connection,
    table_names: set[str],
    source_id: str,
) -> str | None:
    if "structured_documents" not in table_names:
        return None
    row = connection.execute(
        """
        SELECT meeting_date_iso
        FROM structured_documents
        WHERE source_id = ?
          AND meeting_date_iso IS NOT NULL
          AND TRIM(meeting_date_iso) <> ''
        ORDER BY meeting_date_iso DESC
        LIMIT 1
        """,
        (source_id,),
    ).fetchone()
    if row and row[0]:
        return row[0]
    return max_text_value(
        connection,
        table_names,
        "structured_documents",
        "meeting_date",
        "source_id = ? AND meeting_date IS NOT NULL AND TRIM(meeting_date) <> ''",
        [source_id],
    )


def latest_refresh_recorded_at(state_dir: Path, source_id: str) -> str | None:
    state_path = state_dir / f"{source_id}.refresh_state.json"
    if not state_path.exists():
        return None
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    files = payload.get("files")
    if not isinstance(files, dict):
        return None
    recorded_values = [
        entry.get("recorded_at")
        for entry in files.values()
        if isinstance(entry, dict) and isinstance(entry.get("recorded_at"), str)
    ]
    return max(recorded_values) if recorded_values else None


def count_review_queues(download_root: str | None) -> tuple[int, int]:
    if not download_root:
        return 0, 0
    root = Path(download_root)
    if not root.exists():
        return 0, 0
    retry_count = sum_json_array_lengths(root.rglob("retry_queue.json"))
    manual_count = sum_json_array_lengths(root.rglob("manual_review_queue.json"))
    return retry_count, manual_count


def sum_json_array_lengths(paths) -> int:
    total = 0
    for path in paths:
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, list):
            total += len(payload)
    return total


def has_parser_config_warning(parser_name: str | None) -> bool:
    if not parser_name:
        return False
    known_non_item_parser_configs = {"lacounty_govdelivery_email"}
    return parser_name in known_non_item_parser_configs


def fetch_recent_agendas(
    connection: sqlite3.Connection,
    table_names: set[str],
    limit: int = 10,
) -> list[dict[str, Any]]:
    if "structured_documents" not in table_names:
        return []
    rows = connection.execute(
        """
        SELECT
            source_id,
            cluster_name,
            meeting_date,
            meeting_date_iso,
            document_role,
            item_count,
            source_path,
            structured_json_path
        FROM structured_documents
        ORDER BY
            CASE
                WHEN meeting_date_iso IS NOT NULL AND TRIM(meeting_date_iso) <> '' THEN 0
                ELSE 1
            END ASC,
            meeting_date_iso DESC,
            meeting_date DESC,
            source_id ASC,
            cluster_name ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [
        {
            "source_id": row[0],
            "body_name": row[1],
            "meeting_date": row[2],
            "meeting_date_iso": row[3],
            "document_role": row[4],
            "item_count": row[5],
            "source_path": row[6],
            "structured_json_path": row[7],
        }
        for row in rows
    ]


def fetch_top_findings(
    connection: sqlite3.Connection,
    table_names: set[str],
    limit: int = 10,
) -> list[dict[str, Any]]:
    if "structured_findings" not in table_names:
        return []
    rows = connection.execute(
        """
        SELECT
            finding_id,
            source_id,
            cluster_name,
            meeting_date,
            title,
            summary_plain,
            priority_level,
            trend_signal
        FROM structured_findings
        ORDER BY
            CASE priority_level
                WHEN 'high' THEN 0
                WHEN 'medium' THEN 1
                ELSE 2
            END,
            meeting_date DESC,
            source_id ASC,
            title ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [
        {
            "finding_id": row[0],
            "source_id": row[1],
            "body_name": row[2],
            "meeting_date": row[3],
            "title": row[4],
            "summary_plain": row[5],
            "priority_level": row[6],
            "trend_signal": row[7],
        }
        for row in rows
    ]
