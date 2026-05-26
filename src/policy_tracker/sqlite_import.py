from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from policy_tracker.date_utils import normalize_meeting_date_iso
from policy_tracker.runtime_config import load_runtime_config


STRUCTURED_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS structured_documents (
    document_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    source_path TEXT NOT NULL,
    source_document_id TEXT,
    meeting_id TEXT,
    document_role TEXT,
    cluster_name TEXT,
    meeting_date TEXT,
    meeting_date_iso TEXT,
    item_count INTEGER NOT NULL,
    structured_json_path TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS structured_agenda_items (
    agenda_item_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_path TEXT NOT NULL,
    source_document_id TEXT,
    meeting_id TEXT,
    document_role TEXT,
    cluster_name TEXT,
    meeting_date TEXT,
    meeting_date_iso TEXT,
    section_number TEXT,
    section_title TEXT,
    item_label TEXT,
    item_type TEXT,
    title TEXT NOT NULL,
    speakers_json TEXT NOT NULL,
    text_block TEXT NOT NULL,
    action_text_raw TEXT,
    vote_text_raw TEXT,
    final_action TEXT,
    motion_by TEXT,
    second_by TEXT,
    ayes_count INTEGER,
    noes_count INTEGER,
    abstain_count INTEGER,
    absent_count INTEGER,
    ayes_members_json TEXT,
    noes_members_json TEXT,
    abstain_members_json TEXT,
    absent_members_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES structured_documents(document_id)
);

CREATE TABLE IF NOT EXISTS meetings (
    meeting_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    body_name TEXT,
    meeting_date TEXT,
    meeting_date_iso TEXT,
    meeting_title TEXT,
    meeting_type TEXT,
    meeting_status TEXT,
    jurisdiction TEXT,
    location_text TEXT,
    start_time_text TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS structured_item_topics (
    agenda_item_id TEXT NOT NULL,
    topic_tag TEXT NOT NULL,
    PRIMARY KEY (agenda_item_id, topic_tag),
    FOREIGN KEY (agenda_item_id) REFERENCES structured_agenda_items(agenda_item_id)
);

CREATE INDEX IF NOT EXISTS idx_structured_documents_meeting_date
    ON structured_documents(meeting_date);
CREATE INDEX IF NOT EXISTS idx_structured_items_document_id
    ON structured_agenda_items(document_id);
CREATE INDEX IF NOT EXISTS idx_structured_items_cluster
    ON structured_agenda_items(cluster_name);
CREATE INDEX IF NOT EXISTS idx_structured_items_meeting_date
    ON structured_agenda_items(meeting_date);
CREATE INDEX IF NOT EXISTS idx_meetings_source_date
    ON meetings(source_id, meeting_date_iso);
"""


def get_database_path(path: Path | None = None) -> Path:
    return path or load_runtime_config().database_path


def ensure_structured_tables(connection: sqlite3.Connection) -> None:
    connection.executescript(STRUCTURED_TABLES_SQL)
    ensure_column(connection, "structured_documents", "meeting_date_iso", "TEXT")
    ensure_column(connection, "structured_documents", "source_document_id", "TEXT")
    ensure_column(connection, "structured_documents", "meeting_id", "TEXT")
    ensure_column(connection, "structured_documents", "document_role", "TEXT")
    ensure_column(connection, "structured_agenda_items", "meeting_date_iso", "TEXT")
    ensure_column(connection, "structured_agenda_items", "source_document_id", "TEXT")
    ensure_column(connection, "structured_agenda_items", "meeting_id", "TEXT")
    ensure_column(connection, "structured_agenda_items", "document_role", "TEXT")
    ensure_column(connection, "structured_agenda_items", "action_text_raw", "TEXT")
    ensure_column(connection, "structured_agenda_items", "vote_text_raw", "TEXT")
    ensure_column(connection, "structured_agenda_items", "final_action", "TEXT")
    ensure_column(connection, "structured_agenda_items", "motion_by", "TEXT")
    ensure_column(connection, "structured_agenda_items", "second_by", "TEXT")
    ensure_column(connection, "structured_agenda_items", "ayes_count", "INTEGER")
    ensure_column(connection, "structured_agenda_items", "noes_count", "INTEGER")
    ensure_column(connection, "structured_agenda_items", "abstain_count", "INTEGER")
    ensure_column(connection, "structured_agenda_items", "absent_count", "INTEGER")
    ensure_column(connection, "structured_agenda_items", "ayes_members_json", "TEXT")
    ensure_column(connection, "structured_agenda_items", "noes_members_json", "TEXT")
    ensure_column(connection, "structured_agenda_items", "abstain_members_json", "TEXT")
    ensure_column(connection, "structured_agenda_items", "absent_members_json", "TEXT")
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_structured_documents_meeting_date_iso
            ON structured_documents(meeting_date_iso)
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_structured_items_meeting_date_iso
            ON structured_agenda_items(meeting_date_iso)
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_structured_documents_meeting_id
            ON structured_documents(meeting_id)
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_structured_items_meeting_id
            ON structured_agenda_items(meeting_id)
        """
    )


def ensure_column(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_type: str,
) -> None:
    columns = {
        row[1]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name not in columns:
        connection.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
        )


def load_items_index(index_path: Path) -> list[dict[str, Any]]:
    return json.loads(index_path.read_text(encoding="utf-8"))


def import_items_index(
    index_path: Path,
    db_path: Path | None = None,
    source_id: str = "la_county_board_agendas",
) -> dict[str, int]:
    rows = load_items_index(index_path)
    database_path = get_database_path(db_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    document_summaries = build_document_summaries(rows, source_id, index_path.parent)

    with sqlite3.connect(database_path) as connection:
        ensure_structured_tables(connection)
        upsert_meetings(connection, build_meeting_summaries(rows, source_id))
        upsert_structured_documents(connection, document_summaries)
        remove_stale_structured_items_for_documents(connection, rows)
        upsert_structured_items(connection, rows, source_id)
        replace_structured_topics(connection, rows)
        connection.commit()

    return {
        "documents_imported": len(document_summaries),
        "items_imported": len(rows),
        "topics_imported": sum(len(row.get("topic_tags", [])) for row in rows),
    }


def backfill_structured_date_metadata(db_path: Path | None = None) -> dict[str, int]:
    database_path = get_database_path(db_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(database_path) as connection:
        ensure_structured_tables(connection)
        documents_updated = backfill_table_meeting_date_iso(
            connection,
            table_name="structured_documents",
            id_column="document_id",
        )
        items_updated = backfill_table_meeting_date_iso(
            connection,
            table_name="structured_agenda_items",
            id_column="agenda_item_id",
        )
        connection.commit()

        documents_total = connection.execute(
            "SELECT COUNT(*) FROM structured_documents"
        ).fetchone()[0]
        items_total = connection.execute(
            "SELECT COUNT(*) FROM structured_agenda_items"
        ).fetchone()[0]
        documents_populated = connection.execute(
            "SELECT COUNT(*) FROM structured_documents WHERE meeting_date_iso IS NOT NULL AND TRIM(meeting_date_iso) <> ''"
        ).fetchone()[0]
        items_populated = connection.execute(
            "SELECT COUNT(*) FROM structured_agenda_items WHERE meeting_date_iso IS NOT NULL AND TRIM(meeting_date_iso) <> ''"
        ).fetchone()[0]

    return {
        "documents_total": documents_total,
        "documents_updated": documents_updated,
        "documents_with_meeting_date_iso": documents_populated,
        "items_total": items_total,
        "items_updated": items_updated,
        "items_with_meeting_date_iso": items_populated,
    }


def build_document_summaries(
    rows: list[dict[str, Any]], source_id: str, structured_dir: Path
) -> list[dict[str, Any]]:
    summaries: dict[str, dict[str, Any]] = {}
    for row in rows:
        document_id = row["document_id"]
        summary = summaries.setdefault(
            document_id,
            {
                "document_id": document_id,
                "source_id": source_id,
                "source_path": row["source_path"],
                "source_document_id": row.get("source_document_id"),
                "meeting_id": row_meeting_id(row, source_id),
                "document_role": row.get("document_role") or "agenda",
                "cluster_name": row.get("cluster_name"),
                "meeting_date": row.get("meeting_date"),
                "meeting_date_iso": row_meeting_date_iso(row),
                "item_count": 0,
                "structured_json_path": infer_structured_document_path(row["source_path"], structured_dir),
            },
        )
        summary["item_count"] += 1
    return list(summaries.values())


def build_meeting_summaries(rows: list[dict[str, Any]], source_id: str) -> list[dict[str, Any]]:
    meetings: dict[str, dict[str, Any]] = {}
    for row in rows:
        meeting_id = row_meeting_id(row, source_id)
        meetings.setdefault(
            meeting_id,
            {
                "meeting_id": meeting_id,
                "source_id": source_id,
                "body_name": row.get("cluster_name"),
                "meeting_date": row.get("meeting_date"),
                "meeting_date_iso": row_meeting_date_iso(row),
                "meeting_title": None,
                "meeting_type": None,
                "meeting_status": None,
                "jurisdiction": None,
                "location_text": None,
                "start_time_text": None,
            },
        )
    return list(meetings.values())


def upsert_meetings(connection: sqlite3.Connection, meetings: list[dict[str, Any]]) -> None:
    if not meetings:
        return
    connection.executemany(
        """
        INSERT INTO meetings (
            meeting_id, source_id, body_name, meeting_date, meeting_date_iso, meeting_title,
            meeting_type, meeting_status, jurisdiction, location_text, start_time_text
        ) VALUES (
            :meeting_id, :source_id, :body_name, :meeting_date, :meeting_date_iso, :meeting_title,
            :meeting_type, :meeting_status, :jurisdiction, :location_text, :start_time_text
        )
        ON CONFLICT(meeting_id) DO UPDATE SET
            source_id = excluded.source_id,
            body_name = excluded.body_name,
            meeting_date = excluded.meeting_date,
            meeting_date_iso = excluded.meeting_date_iso,
            updated_at = CURRENT_TIMESTAMP
        """,
        meetings,
    )


def infer_structured_document_path(source_path: str, structured_dir: Path) -> str:
    source_name = Path(source_path).stem
    return str((structured_dir / f"{source_name}.structured.json").resolve())


def upsert_structured_documents(
    connection: sqlite3.Connection, documents: list[dict[str, Any]]
) -> None:
    connection.executemany(
        """
        INSERT INTO structured_documents (
            document_id, source_id, source_path, source_document_id, meeting_id, document_role,
            cluster_name, meeting_date, meeting_date_iso,
            item_count, structured_json_path
        ) VALUES (
            :document_id, :source_id, :source_path, :source_document_id, :meeting_id, :document_role,
            :cluster_name, :meeting_date, :meeting_date_iso,
            :item_count, :structured_json_path
        )
        ON CONFLICT(document_id) DO UPDATE SET
            source_id = excluded.source_id,
            source_path = excluded.source_path,
            source_document_id = excluded.source_document_id,
            meeting_id = excluded.meeting_id,
            document_role = excluded.document_role,
            cluster_name = excluded.cluster_name,
            meeting_date = excluded.meeting_date,
            meeting_date_iso = excluded.meeting_date_iso,
            item_count = excluded.item_count,
            structured_json_path = excluded.structured_json_path,
            updated_at = CURRENT_TIMESTAMP
        """,
        documents,
    )


def upsert_structured_items(
    connection: sqlite3.Connection, rows: list[dict[str, Any]], source_id: str
) -> None:
    payload = [
        {
            "agenda_item_id": row["agenda_item_id"],
            "document_id": row["document_id"],
            "source_id": source_id,
            "source_path": row["source_path"],
            "source_document_id": row.get("source_document_id"),
            "meeting_id": row_meeting_id(row, source_id),
            "document_role": row.get("document_role") or "agenda",
            "cluster_name": row.get("cluster_name"),
            "meeting_date": row.get("meeting_date"),
            "meeting_date_iso": row_meeting_date_iso(row),
            "section_number": row.get("section_number"),
            "section_title": row.get("section_title"),
            "item_label": row.get("item_label"),
            "item_type": row.get("item_type"),
            "title": row.get("title"),
            "speakers_json": json.dumps(row.get("speakers", [])),
            "text_block": row.get("text_block", ""),
            "action_text_raw": row.get("action_text_raw"),
            "vote_text_raw": row.get("vote_text_raw"),
            "final_action": row.get("final_action"),
            "motion_by": row.get("motion_by"),
            "second_by": row.get("second_by"),
            "ayes_count": row.get("ayes_count"),
            "noes_count": row.get("noes_count"),
            "abstain_count": row.get("abstain_count"),
            "absent_count": row.get("absent_count"),
            "ayes_members_json": json.dumps(row.get("ayes_members", [])),
            "noes_members_json": json.dumps(row.get("noes_members", [])),
            "abstain_members_json": json.dumps(row.get("abstain_members", [])),
            "absent_members_json": json.dumps(row.get("absent_members", [])),
        }
        for row in rows
    ]
    connection.executemany(
        """
        INSERT INTO structured_agenda_items (
            agenda_item_id, document_id, source_id, source_path, source_document_id, meeting_id, document_role,
            cluster_name, meeting_date, meeting_date_iso, section_number, section_title, item_label, item_type,
            title, speakers_json, text_block, action_text_raw, vote_text_raw, final_action, motion_by, second_by,
            ayes_count, noes_count, abstain_count, absent_count, ayes_members_json, noes_members_json,
            abstain_members_json, absent_members_json
        ) VALUES (
            :agenda_item_id, :document_id, :source_id, :source_path, :source_document_id, :meeting_id, :document_role,
            :cluster_name, :meeting_date, :meeting_date_iso, :section_number, :section_title, :item_label, :item_type,
            :title, :speakers_json, :text_block, :action_text_raw, :vote_text_raw, :final_action, :motion_by, :second_by,
            :ayes_count, :noes_count, :abstain_count, :absent_count, :ayes_members_json, :noes_members_json,
            :abstain_members_json, :absent_members_json
        )
        ON CONFLICT(agenda_item_id) DO UPDATE SET
            document_id = excluded.document_id,
            source_id = excluded.source_id,
            source_path = excluded.source_path,
            source_document_id = excluded.source_document_id,
            meeting_id = excluded.meeting_id,
            document_role = excluded.document_role,
            cluster_name = excluded.cluster_name,
            meeting_date = excluded.meeting_date,
            meeting_date_iso = excluded.meeting_date_iso,
            section_number = excluded.section_number,
            section_title = excluded.section_title,
            item_label = excluded.item_label,
            item_type = excluded.item_type,
            title = excluded.title,
            speakers_json = excluded.speakers_json,
            text_block = excluded.text_block,
            action_text_raw = excluded.action_text_raw,
            vote_text_raw = excluded.vote_text_raw,
            final_action = excluded.final_action,
            motion_by = excluded.motion_by,
            second_by = excluded.second_by,
            ayes_count = excluded.ayes_count,
            noes_count = excluded.noes_count,
            abstain_count = excluded.abstain_count,
            absent_count = excluded.absent_count,
            ayes_members_json = excluded.ayes_members_json,
            noes_members_json = excluded.noes_members_json,
            abstain_members_json = excluded.abstain_members_json,
            absent_members_json = excluded.absent_members_json,
            updated_at = CURRENT_TIMESTAMP
        """,
        payload,
    )


def row_meeting_date_iso(row: dict[str, Any]) -> str | None:
    return row.get("meeting_date_iso") or normalize_meeting_date_iso(row.get("meeting_date"))


def row_meeting_id(row: dict[str, Any], source_id: str) -> str:
    existing = row.get("meeting_id")
    if existing:
        return existing
    base = "|".join(
        [
            source_id,
            row.get("cluster_name") or "",
            row_meeting_date_iso(row) or "",
            row.get("source_path") or "",
        ]
    )
    digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]
    return f"meeting_{digest}"


def remove_stale_structured_items_for_documents(
    connection: sqlite3.Connection,
    rows: list[dict[str, Any]],
) -> None:
    if not rows:
        return

    expected_item_ids_by_document: dict[str, set[str]] = {}
    for row in rows:
        expected_item_ids_by_document.setdefault(row["document_id"], set()).add(row["agenda_item_id"])

    stale_item_ids: list[str] = []
    for document_id, expected_item_ids in expected_item_ids_by_document.items():
        existing_item_ids = {
            item_id
            for (item_id,) in connection.execute(
                "SELECT agenda_item_id FROM structured_agenda_items WHERE document_id = ?",
                (document_id,),
            ).fetchall()
        }
        stale_item_ids.extend(sorted(existing_item_ids - expected_item_ids))

    if not stale_item_ids:
        return

    placeholders = ",".join("?" for _ in stale_item_ids)
    connection.execute(
        f"DELETE FROM structured_item_topics WHERE agenda_item_id IN ({placeholders})",
        stale_item_ids,
    )
    if table_exists(connection, "structured_finding_topics"):
        connection.execute(
            f"""
            DELETE FROM structured_finding_topics
            WHERE finding_id IN (
                SELECT finding_id FROM structured_findings WHERE agenda_item_id IN ({placeholders})
            )
            """,
            stale_item_ids,
        )
    if table_exists(connection, "structured_findings"):
        connection.execute(
            f"DELETE FROM structured_findings WHERE agenda_item_id IN ({placeholders})",
            stale_item_ids,
        )
    connection.execute(
        f"DELETE FROM structured_agenda_items WHERE agenda_item_id IN ({placeholders})",
        stale_item_ids,
    )


def backfill_table_meeting_date_iso(
    connection: sqlite3.Connection,
    table_name: str,
    id_column: str,
) -> int:
    rows = connection.execute(
        f"SELECT {id_column}, meeting_date, meeting_date_iso FROM {table_name}"
    ).fetchall()
    updates: list[tuple[str | None, Any]] = []
    for row_id, meeting_date, existing_iso in rows:
        normalized = normalize_meeting_date_iso(meeting_date)
        if (existing_iso or None) == normalized:
            continue
        updates.append((normalized, row_id))
    if not updates:
        return 0
    connection.executemany(
        f"UPDATE {table_name} SET meeting_date_iso = ? WHERE {id_column} = ?",
        updates,
    )
    return len(updates)


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def replace_structured_topics(connection: sqlite3.Connection, rows: list[dict[str, Any]]) -> None:
    agenda_item_ids = [row["agenda_item_id"] for row in rows]
    if agenda_item_ids:
        placeholders = ",".join("?" for _ in agenda_item_ids)
        connection.execute(
            f"DELETE FROM structured_item_topics WHERE agenda_item_id IN ({placeholders})",
            agenda_item_ids,
        )

    topic_rows = [
        (row["agenda_item_id"], topic)
        for row in rows
        for topic in row.get("topic_tags", [])
    ]
    connection.executemany(
        """
        INSERT INTO structured_item_topics (agenda_item_id, topic_tag)
        VALUES (?, ?)
        """,
        topic_rows,
    )
