from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from policy_tracker.query_layer import AgendaItemRecord, QueryFilters, fetch_items_from_connection
from policy_tracker.runtime_config import load_runtime_config


STRUCTURED_FINDINGS_SQL = """
CREATE TABLE IF NOT EXISTS structured_findings (
    finding_id TEXT PRIMARY KEY,
    agenda_item_id TEXT NOT NULL UNIQUE,
    document_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    cluster_name TEXT,
    meeting_date TEXT,
    title TEXT NOT NULL,
    summary_plain TEXT NOT NULL,
    why_it_matters TEXT NOT NULL,
    priority_level TEXT NOT NULL,
    action_classification TEXT NOT NULL,
    trend_signal TEXT NOT NULL,
    evidence_text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (agenda_item_id) REFERENCES structured_agenda_items(agenda_item_id),
    FOREIGN KEY (document_id) REFERENCES structured_documents(document_id)
);

CREATE TABLE IF NOT EXISTS structured_finding_topics (
    finding_id TEXT NOT NULL,
    topic_tag TEXT NOT NULL,
    PRIMARY KEY (finding_id, topic_tag),
    FOREIGN KEY (finding_id) REFERENCES structured_findings(finding_id)
);

CREATE INDEX IF NOT EXISTS idx_structured_findings_cluster
    ON structured_findings(cluster_name);
CREATE INDEX IF NOT EXISTS idx_structured_findings_meeting_date
    ON structured_findings(meeting_date);
CREATE INDEX IF NOT EXISTS idx_structured_findings_priority
    ON structured_findings(priority_level);
"""


TOPIC_EXPLANATIONS = {
    "behavioral_health": "it touches behavioral-health services or delivery capacity",
    "budget": "it affects spending plans, revenues, or fiscal commitments",
    "contracting": "it changes vendor relationships or procurement commitments",
    "data_systems": "it affects infrastructure, operations, or technical systems",
    "governance": "it changes oversight, authority, or formal operating rules",
    "homelessness": "it affects homelessness-response policy or service delivery",
    "housing": "it affects housing supply, siting, or supportive housing delivery",
    "jails": "it touches jail operations, detention conditions, or custodial services",
    "labor": "it may affect workforce conditions or staffing",
    "probation": "it affects probation operations or youth justice systems",
    "public_safety": "it affects emergency response, law enforcement, or public safety operations",
}

HIGH_PRIORITY_TOPICS = {"behavioral_health", "homelessness", "housing", "probation", "public_safety"}
HIGH_PRIORITY_KEYWORDS = (
    "amendment",
    "approve",
    "award",
    "budget",
    "contract",
    "expenditure plan",
    "master agreement",
    "retroactive",
    "sole source",
    "special parcel tax",
)


@dataclass(slots=True)
class FindingFilters:
    source_id: str | None = None
    topic: str | None = None
    cluster: str | None = None
    meeting_date: str | None = None
    priority: str | None = None
    search: str | None = None
    limit: int = 50


@dataclass(slots=True)
class StructuredFindingRecord:
    finding_id: str
    agenda_item_id: str
    document_id: str
    source_id: str
    cluster_name: str | None
    meeting_date: str | None
    title: str
    summary_plain: str
    why_it_matters: str
    priority_level: str
    action_classification: str
    trend_signal: str
    evidence_text: str
    topic_tags: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def get_database_path(path: Path | None = None) -> Path:
    return path or load_runtime_config().database_path


def ensure_structured_findings_tables(connection: sqlite3.Connection) -> None:
    connection.executescript(STRUCTURED_FINDINGS_SQL)


def build_finding_id(agenda_item_id: str) -> str:
    digest = hashlib.sha1(agenda_item_id.encode("utf-8")).hexdigest()[:16]
    return f"finding_{digest}"


def classify_action(item: AgendaItemRecord) -> str:
    lowered = f"{item.title} {item.text_block}".lower()
    if "sole source" in lowered:
        return "sole_source_contract"
    if "amendment" in lowered or "extend" in lowered:
        return "contract_amendment"
    if "award" in lowered:
        return "contract_award"
    if "adopt" in lowered:
        return "policy_adoption"
    if "approve" in lowered or "approval" in lowered:
        return "board_approval"
    if item.section_title and "presentation" in item.section_title.lower():
        return "discussion_item"
    return "informational_item"


def score_priority(item: AgendaItemRecord, action_classification: str) -> str:
    lowered = f"{item.title} {item.text_block}".lower()
    score = 0
    score += sum(2 for tag in item.topic_tags if tag in HIGH_PRIORITY_TOPICS)
    score += sum(1 for keyword in HIGH_PRIORITY_KEYWORDS if keyword in lowered)
    if action_classification in {"contract_amendment", "contract_award", "sole_source_contract"}:
        score += 1

    if score >= 5:
        return "high"
    if score >= 2:
        return "medium"
    return "low"


def classify_trend_signal(item: AgendaItemRecord, action_classification: str) -> str:
    lowered = f"{item.title} {item.text_block}".lower()
    if any(keyword in lowered for keyword in ("retroactive", "extend", "master agreement", "on-call", "sole source")):
        return "recurring_vendor_or_contract_pattern"
    if any(tag in item.topic_tags for tag in HIGH_PRIORITY_TOPICS):
        return "policy_watch"
    if action_classification in {"board_approval", "contract_award", "policy_adoption"}:
        return "board_decision"
    return "routine_monitoring"


def build_summary(item: AgendaItemRecord, action_classification: str) -> str:
    cluster = item.cluster_name or "Unknown cluster"
    label = item.item_label or "?"
    action_text = action_classification.replace("_", " ")
    return f"{cluster} item {label} is a {action_text} covering {item.title}."


def build_why_it_matters(item: AgendaItemRecord, priority_level: str) -> str:
    explanations = [TOPIC_EXPLANATIONS[tag] for tag in item.topic_tags if tag in TOPIC_EXPLANATIONS]
    if explanations:
        topic_sentence = "This matters because " + " and ".join(explanations[:2]) + "."
    else:
        topic_sentence = "This matters because it could signal an operational or policy decision that merits follow-up."

    if priority_level == "high":
        return topic_sentence + " It likely deserves closer review in the next digest."
    if priority_level == "medium":
        return topic_sentence + " It is worth monitoring as part of the current agenda batch."
    return topic_sentence + " It can stay in the routine monitoring queue unless related items accumulate."


def generate_finding(item: AgendaItemRecord) -> StructuredFindingRecord:
    action_classification = classify_action(item)
    priority_level = score_priority(item, action_classification)
    return StructuredFindingRecord(
        finding_id=build_finding_id(item.agenda_item_id),
        agenda_item_id=item.agenda_item_id,
        document_id=item.document_id,
        source_id=item.source_id,
        cluster_name=item.cluster_name,
        meeting_date=item.meeting_date,
        title=item.title,
        summary_plain=build_summary(item, action_classification),
        why_it_matters=build_why_it_matters(item, priority_level),
        priority_level=priority_level,
        action_classification=action_classification,
        trend_signal=classify_trend_signal(item, action_classification),
        evidence_text=item.text_block,
        topic_tags=sorted(set(item.topic_tags)),
    )


def generate_findings(
    db_path: Path | None = None,
    filters: QueryFilters | None = None,
) -> dict[str, int]:
    database_path = get_database_path(db_path)
    with sqlite3.connect(database_path) as connection:
        return generate_findings_from_connection(connection, filters or QueryFilters())


def generate_findings_from_connection(
    connection: sqlite3.Connection,
    query_filters: QueryFilters,
) -> dict[str, int]:
    ensure_structured_findings_tables(connection)
    items = fetch_items_from_connection(connection, query_filters)
    findings = [generate_finding(item) for item in items]
    upsert_structured_findings(connection, findings)
    replace_structured_finding_topics(connection, findings)
    connection.commit()
    return {
        "items_considered": len(items),
        "findings_written": len(findings),
        "high_priority_findings": len([finding for finding in findings if finding.priority_level == "high"]),
    }


def upsert_structured_findings(
    connection: sqlite3.Connection,
    findings: list[StructuredFindingRecord],
) -> None:
    payload = [
        {
            "finding_id": finding.finding_id,
            "agenda_item_id": finding.agenda_item_id,
            "document_id": finding.document_id,
            "source_id": finding.source_id,
            "cluster_name": finding.cluster_name,
            "meeting_date": finding.meeting_date,
            "title": finding.title,
            "summary_plain": finding.summary_plain,
            "why_it_matters": finding.why_it_matters,
            "priority_level": finding.priority_level,
            "action_classification": finding.action_classification,
            "trend_signal": finding.trend_signal,
            "evidence_text": finding.evidence_text,
        }
        for finding in findings
    ]
    connection.executemany(
        """
        INSERT INTO structured_findings (
            finding_id, agenda_item_id, document_id, source_id, cluster_name, meeting_date,
            title, summary_plain, why_it_matters, priority_level, action_classification,
            trend_signal, evidence_text
        ) VALUES (
            :finding_id, :agenda_item_id, :document_id, :source_id, :cluster_name, :meeting_date,
            :title, :summary_plain, :why_it_matters, :priority_level, :action_classification,
            :trend_signal, :evidence_text
        )
        ON CONFLICT(finding_id) DO UPDATE SET
            agenda_item_id = excluded.agenda_item_id,
            document_id = excluded.document_id,
            source_id = excluded.source_id,
            cluster_name = excluded.cluster_name,
            meeting_date = excluded.meeting_date,
            title = excluded.title,
            summary_plain = excluded.summary_plain,
            why_it_matters = excluded.why_it_matters,
            priority_level = excluded.priority_level,
            action_classification = excluded.action_classification,
            trend_signal = excluded.trend_signal,
            evidence_text = excluded.evidence_text,
            updated_at = CURRENT_TIMESTAMP
        """,
        payload,
    )


def replace_structured_finding_topics(
    connection: sqlite3.Connection,
    findings: list[StructuredFindingRecord],
) -> None:
    finding_ids = [finding.finding_id for finding in findings]
    if finding_ids:
        placeholders = ",".join("?" for _ in finding_ids)
        connection.execute(
            f"DELETE FROM structured_finding_topics WHERE finding_id IN ({placeholders})",
            finding_ids,
        )

    topic_rows = [
        (finding.finding_id, topic)
        for finding in findings
        for topic in finding.topic_tags
    ]
    connection.executemany(
        """
        INSERT INTO structured_finding_topics (finding_id, topic_tag)
        VALUES (?, ?)
        """,
        topic_rows,
    )


def fetch_findings(
    db_path: Path | None = None,
    filters: FindingFilters | None = None,
) -> list[StructuredFindingRecord]:
    database_path = get_database_path(db_path)
    with sqlite3.connect(database_path) as connection:
        return fetch_findings_from_connection(connection, filters or FindingFilters())


def fetch_findings_from_connection(
    connection: sqlite3.Connection,
    filters: FindingFilters,
) -> list[StructuredFindingRecord]:
    ensure_structured_findings_tables(connection)
    sql = """
        SELECT
            f.finding_id,
            f.agenda_item_id,
            f.document_id,
            f.source_id,
            f.cluster_name,
            f.meeting_date,
            f.title,
            f.summary_plain,
            f.why_it_matters,
            f.priority_level,
            f.action_classification,
            f.trend_signal,
            f.evidence_text,
            COALESCE(json_group_array(t.topic_tag), '[]') AS topic_tags_json
        FROM structured_findings f
        LEFT JOIN structured_finding_topics t ON t.finding_id = f.finding_id
    """
    where_clauses: list[str] = []
    params: list[Any] = []

    if filters.topic:
        where_clauses.append(
            "EXISTS (SELECT 1 FROM structured_finding_topics tt WHERE tt.finding_id = f.finding_id AND tt.topic_tag = ?)"
        )
        params.append(filters.topic)
    if filters.source_id:
        where_clauses.append("f.source_id = ?")
        params.append(filters.source_id)
    if filters.cluster:
        where_clauses.append("f.cluster_name = ?")
        params.append(filters.cluster)
    if filters.meeting_date:
        where_clauses.append("f.meeting_date = ?")
        params.append(filters.meeting_date)
    if filters.priority:
        where_clauses.append("f.priority_level = ?")
        params.append(filters.priority)
    if filters.search:
        where_clauses.append("(f.title LIKE ? OR f.summary_plain LIKE ? OR f.why_it_matters LIKE ?)")
        needle = f"%{filters.search}%"
        params.extend([needle, needle, needle])

    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)

    sql += """
        GROUP BY
            f.finding_id,
            f.agenda_item_id,
            f.document_id,
            f.source_id,
            f.cluster_name,
            f.meeting_date,
            f.title,
            f.summary_plain,
            f.why_it_matters,
            f.priority_level,
            f.action_classification,
            f.trend_signal,
            f.evidence_text
        ORDER BY
            CASE f.priority_level
                WHEN 'high' THEN 0
                WHEN 'medium' THEN 1
                ELSE 2
            END,
            f.meeting_date DESC,
            f.cluster_name ASC,
            f.title ASC
        LIMIT ?
    """
    params.append(filters.limit)

    rows = connection.execute(sql, params).fetchall()
    return [
        StructuredFindingRecord(
            finding_id=row[0],
            agenda_item_id=row[1],
            document_id=row[2],
            source_id=row[3],
            cluster_name=row[4],
            meeting_date=row[5],
            title=row[6],
            summary_plain=row[7],
            why_it_matters=row[8],
            priority_level=row[9],
            action_classification=row[10],
            trend_signal=row[11],
            evidence_text=row[12],
            topic_tags=sorted(set(tag for tag in json.loads(row[13]) if tag is not None)),
        )
        for row in rows
    ]
