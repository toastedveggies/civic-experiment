from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from policy_tracker.runtime_config import load_runtime_config


@dataclass(slots=True)
class QueryFilters:
    source_id: str | None = None
    topic: str | None = None
    cluster: str | None = None
    meeting_date: str | None = None
    search: str | None = None
    limit: int = 50


@dataclass(slots=True)
class AgendaItemRecord:
    agenda_item_id: str
    document_id: str
    source_id: str
    source_path: str
    cluster_name: str | None
    meeting_date: str | None
    section_number: str | None
    section_title: str | None
    item_label: str | None
    item_type: str | None
    title: str
    speakers: list[str]
    text_block: str
    topic_tags: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def get_database_path(path: Path | None = None) -> Path:
    return path or load_runtime_config().database_path


def fetch_items(db_path: Path | None = None, filters: QueryFilters | None = None) -> list[AgendaItemRecord]:
    query_filters = filters or QueryFilters()
    database_path = get_database_path(db_path)
    with sqlite3.connect(database_path) as connection:
        return fetch_items_from_connection(connection, query_filters)


def fetch_items_from_connection(
    connection: sqlite3.Connection, query_filters: QueryFilters
) -> list[AgendaItemRecord]:
    sql = """
        SELECT
            i.agenda_item_id,
            i.document_id,
            i.source_id,
            i.source_path,
            i.cluster_name,
            i.meeting_date,
            i.section_number,
            i.section_title,
            i.item_label,
            i.item_type,
            i.title,
            i.speakers_json,
            i.text_block,
            COALESCE(json_group_array(t.topic_tag), '[]') AS topic_tags_json
        FROM structured_agenda_items i
        LEFT JOIN structured_item_topics t ON t.agenda_item_id = i.agenda_item_id
    """
    where_clauses: list[str] = []
    params: list[Any] = []

    if query_filters.topic:
        where_clauses.append(
            "EXISTS (SELECT 1 FROM structured_item_topics tt WHERE tt.agenda_item_id = i.agenda_item_id AND tt.topic_tag = ?)"
        )
        params.append(query_filters.topic)
    if query_filters.source_id:
        where_clauses.append("i.source_id = ?")
        params.append(query_filters.source_id)
    if query_filters.cluster:
        where_clauses.append("i.cluster_name = ?")
        params.append(query_filters.cluster)
    if query_filters.meeting_date:
        where_clauses.append("i.meeting_date = ?")
        params.append(query_filters.meeting_date)
    if query_filters.search:
        where_clauses.append("(i.title LIKE ? OR i.text_block LIKE ?)")
        needle = f"%{query_filters.search}%"
        params.extend([needle, needle])

    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)

    sql += """
        GROUP BY
            i.agenda_item_id,
            i.document_id,
            i.source_id,
            i.source_path,
            i.cluster_name,
            i.meeting_date,
            i.section_number,
            i.section_title,
            i.item_label,
            i.item_type,
            i.title,
            i.speakers_json,
            i.text_block
        ORDER BY i.meeting_date DESC, i.cluster_name ASC, i.section_number ASC, i.item_label ASC
        LIMIT ?
    """
    params.append(query_filters.limit)

    rows = connection.execute(sql, params).fetchall()

    records: list[AgendaItemRecord] = []
    for row in rows:
        topic_tags = [tag for tag in json.loads(row[13]) if tag is not None]
        speakers = json.loads(row[11])
        records.append(
            AgendaItemRecord(
                agenda_item_id=row[0],
                document_id=row[1],
                source_id=row[2],
                source_path=row[3],
                cluster_name=row[4],
                meeting_date=row[5],
                section_number=row[6],
                section_title=row[7],
                item_label=row[8],
                item_type=row[9],
                title=row[10],
                speakers=speakers,
                text_block=row[12],
                topic_tags=sorted(set(topic_tags)),
            )
        )
    return records


def summarize_by_topic(items: list[AgendaItemRecord]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for item in items:
        for tag in item.topic_tags:
            counts[tag] = counts.get(tag, 0) + 1
    return [
        {"topic": topic, "count": count}
        for topic, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    ]


def summarize_by_cluster(items: list[AgendaItemRecord]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for item in items:
        key = item.cluster_name or "Unknown Cluster"
        counts[key] = counts.get(key, 0) + 1
    return [
        {"cluster": cluster, "count": count}
        for cluster, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    ]


def build_weekly_digest(items: list[AgendaItemRecord]) -> dict[str, Any]:
    return {
        "item_count": len(items),
        "clusters": summarize_by_cluster(items),
        "topics": summarize_by_topic(items),
        "high_signal_items": [
            item.to_dict()
            for item in items
            if {"housing", "homelessness", "probation", "public_safety", "behavioral_health"} & set(item.topic_tags)
        ][:10],
    }


def render_weekly_digest_markdown(digest: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Weekly Digest")
    lines.append("")
    lines.append(f"- Items reviewed: {digest['item_count']}")
    lines.append("")
    lines.append("## Clusters")
    for entry in digest["clusters"]:
        lines.append(f"- {entry['cluster']}: {entry['count']}")
    lines.append("")
    lines.append("## Topics")
    for entry in digest["topics"]:
        lines.append(f"- {entry['topic']}: {entry['count']}")
    lines.append("")
    lines.append("## High-Signal Items")
    for item in digest["high_signal_items"]:
        lines.append(
            f"- {item['meeting_date']} | {item['cluster_name']} | {item['title']}"
        )
    return "\n".join(lines)
