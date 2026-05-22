from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from policy_tracker.item_extraction import ExtractedAgendaDocument, extract_agenda_items_from_text_path


@dataclass(slots=True)
class StoredAgendaItem:
    agenda_item_id: str
    document_id: str
    source_path: str
    cluster_name: str | None
    meeting_date: str | None
    section_number: str
    section_title: str
    item_label: str
    item_type: str
    title: str
    speakers: list[str]
    text_block: str
    topic_tags: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class StoredAgendaDocument:
    document_id: str
    source_path: str
    cluster_name: str | None
    meeting_date: str | None
    item_count: int
    items: list[StoredAgendaItem]

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "source_path": self.source_path,
            "cluster_name": self.cluster_name,
            "meeting_date": self.meeting_date,
            "item_count": self.item_count,
            "items": [item.to_dict() for item in self.items],
        }


def build_document_id(source_path: Path) -> str:
    digest = hashlib.sha1(str(source_path.resolve()).encode("utf-8")).hexdigest()[:16]
    return f"doc_{digest}"


def build_agenda_item_id(document_id: str, item_label: str, title: str) -> str:
    digest = hashlib.sha1(f"{document_id}|{item_label}|{title}".encode("utf-8")).hexdigest()[:16]
    return f"item_{digest}"


def materialize_structured_document(source_path: Path) -> StoredAgendaDocument:
    extracted = extract_agenda_items_from_text_path(source_path)
    document_id = build_document_id(source_path)
    items = [
        StoredAgendaItem(
            agenda_item_id=build_agenda_item_id(document_id, item.item_label, item.title),
            document_id=document_id,
            source_path=extracted.source_path,
            cluster_name=item.cluster_name,
            meeting_date=item.meeting_date,
            section_number=item.section_number,
            section_title=item.section_title,
            item_label=item.item_label,
            item_type=item.item_type,
            title=item.title,
            speakers=item.speakers,
            text_block=item.text_block,
            topic_tags=item.topic_tags,
        )
        for item in extracted.items
    ]
    return StoredAgendaDocument(
        document_id=document_id,
        source_path=extracted.source_path,
        cluster_name=extracted.cluster_name,
        meeting_date=extracted.meeting_date,
        item_count=len(items),
        items=items,
    )


def write_structured_document(document: StoredAgendaDocument, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(document.to_dict(), indent=2), encoding="utf-8")


def build_items_index(documents: list[StoredAgendaDocument]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for document in documents:
        for item in document.items:
            rows.append(item.to_dict())
    return rows


def write_items_index(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
