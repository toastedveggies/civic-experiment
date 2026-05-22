from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from policy_tracker.runtime_config import load_runtime_config


STRUCTURED_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS structured_documents (
    document_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    source_path TEXT NOT NULL,
    cluster_name TEXT,
    meeting_date TEXT,
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
    cluster_name TEXT,
    meeting_date TEXT,
    section_number TEXT,
    section_title TEXT,
    item_label TEXT,
    item_type TEXT,
    title TEXT NOT NULL,
    speakers_json TEXT NOT NULL,
    text_block TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES structured_documents(document_id)
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
"""


def get_database_path(path: Path | None = None) -> Path:
    return path or load_runtime_config().database_path


def ensure_structured_tables(connection: sqlite3.Connection) -> None:
    connection.executescript(STRUCTURED_TABLES_SQL)


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
        upsert_structured_documents(connection, document_summaries)
        upsert_structured_items(connection, rows, source_id)
        replace_structured_topics(connection, rows)
        connection.commit()

    return {
        "documents_imported": len(document_summaries),
        "items_imported": len(rows),
        "topics_imported": sum(len(row.get("topic_tags", [])) for row in rows),
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
                "cluster_name": row.get("cluster_name"),
                "meeting_date": row.get("meeting_date"),
                "item_count": 0,
                "structured_json_path": infer_structured_document_path(row["source_path"], structured_dir),
            },
        )
        summary["item_count"] += 1
    return list(summaries.values())


def infer_structured_document_path(source_path: str, structured_dir: Path) -> str:
    source_name = Path(source_path).stem
    return str((structured_dir / f"{source_name}.structured.json").resolve())


def upsert_structured_documents(
    connection: sqlite3.Connection, documents: list[dict[str, Any]]
) -> None:
    connection.executemany(
        """
        INSERT INTO structured_documents (
            document_id, source_id, source_path, cluster_name, meeting_date, item_count, structured_json_path
        ) VALUES (
            :document_id, :source_id, :source_path, :cluster_name, :meeting_date, :item_count, :structured_json_path
        )
        ON CONFLICT(document_id) DO UPDATE SET
            source_id = excluded.source_id,
            source_path = excluded.source_path,
            cluster_name = excluded.cluster_name,
            meeting_date = excluded.meeting_date,
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
            "cluster_name": row.get("cluster_name"),
            "meeting_date": row.get("meeting_date"),
            "section_number": row.get("section_number"),
            "section_title": row.get("section_title"),
            "item_label": row.get("item_label"),
            "item_type": row.get("item_type"),
            "title": row.get("title"),
            "speakers_json": json.dumps(row.get("speakers", [])),
            "text_block": row.get("text_block", ""),
        }
        for row in rows
    ]
    connection.executemany(
        """
        INSERT INTO structured_agenda_items (
            agenda_item_id, document_id, source_id, source_path, cluster_name, meeting_date,
            section_number, section_title, item_label, item_type, title, speakers_json, text_block
        ) VALUES (
            :agenda_item_id, :document_id, :source_id, :source_path, :cluster_name, :meeting_date,
            :section_number, :section_title, :item_label, :item_type, :title, :speakers_json, :text_block
        )
        ON CONFLICT(agenda_item_id) DO UPDATE SET
            document_id = excluded.document_id,
            source_id = excluded.source_id,
            source_path = excluded.source_path,
            cluster_name = excluded.cluster_name,
            meeting_date = excluded.meeting_date,
            section_number = excluded.section_number,
            section_title = excluded.section_title,
            item_label = excluded.item_label,
            item_type = excluded.item_type,
            title = excluded.title,
            speakers_json = excluded.speakers_json,
            text_block = excluded.text_block,
            updated_at = CURRENT_TIMESTAMP
        """,
        payload,
    )


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
