from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


SECTION_HEADER_RE = re.compile(r"^\s*((?:\d+|[IVXLC]+))\.\s+(.+?)(?::\s*.*)?\s*$", re.IGNORECASE)
ITEM_LETTER_RE = re.compile(r"^\s*([A-Z])[\.\)]\s+(.*\S)\s*$", re.IGNORECASE)
SPEAKER_RE = re.compile(
    r"^\s*(?:Speaker(?:s|\(s\))?|Presenter(?:s|\(s\))?):\s*(.*\S)?\s*$",
    re.IGNORECASE,
)
SPEAKER_BULLET_RE = re.compile(r"^\s*(?:[\u2022-])\s*(.*\S)\s*$")
DATE_RE = re.compile(r"DATE:\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})")
CLUSTER_RE = re.compile(r"([A-Za-z &]+) Cluster", re.IGNORECASE)
STOP_LINE_RE = re.compile(
    r"^\s*(IF YOU WOULD LIKE TO EMAIL A COMMENT|PUBLIC COMMENTS?|CLOSED SESSION ITEMS?|UPCOMING ITEM\(S\))",
    re.IGNORECASE,
)

TOPIC_RULES = {
    "housing": ["housing", "homekey", "multifamily", "supportive housing", "homelessness"],
    "homelessness": ["homeless", "homekey", "supportive housing"],
    "public_safety": ["fire", "security", "sheriff", "crime", "probation", "public safety"],
    "probation": ["probation", "halls", "camps"],
    "jails": ["jail", "incarcerated", "cremation"],
    "behavioral_health": ["mental health", "behavioral health", "health"],
    "governance": ["agreement", "authority", "delegated authority", "policy", "equity framework", "oversight"],
    "contracting": ["contract", "sole source", "agreement", "amendment", "master agreements"],
    "budget": ["budget", "fund", "appropriation", "parcel tax", "assessment rate"],
    "labor": ["workers", "compensation"],
    "data_systems": ["systems", "laboratory", "maintenance", "engineering", "data integration", "dashboard", "hmis"],
}


@dataclass(slots=True)
class ExtractedAgendaItem:
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
class ExtractedAgendaDocument:
    source_path: str
    cluster_name: str | None
    meeting_date: str | None
    item_count: int
    items: list[ExtractedAgendaItem]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "cluster_name": self.cluster_name,
            "meeting_date": self.meeting_date,
            "item_count": self.item_count,
            "items": [item.to_dict() for item in self.items],
        }


def extract_agenda_items_from_text_path(path: Path) -> ExtractedAgendaDocument:
    text = path.read_text(encoding="utf-8")
    return extract_agenda_items_from_text(text, path)


def extract_agenda_items_from_text(text: str, source_path: Path | None = None) -> ExtractedAgendaDocument:
    normalized = normalize_text(text)
    lines = [line.rstrip() for line in normalized.splitlines()]
    cluster_name = detect_cluster_name(normalized)
    meeting_date = detect_meeting_date(normalized)

    items: list[ExtractedAgendaItem] = []
    current_section_number: str | None = None
    current_section_title: str | None = None
    index = 0

    while index < len(lines):
        line = lines[index]
        section_match = SECTION_HEADER_RE.match(line)
        if section_match:
            current_section_number = section_match.group(1)
            current_section_title = clean_text(section_match.group(2))
            index += 1
            continue

        item_match = ITEM_LETTER_RE.match(line)
        if item_match and current_section_number and current_section_title:
            item_label = item_match.group(1).upper()
            collected_lines = [item_match.group(2)]
            index += 1
            while index < len(lines):
                next_line = lines[index]
                if (
                    SECTION_HEADER_RE.match(next_line)
                    or ITEM_LETTER_RE.match(next_line)
                    or STOP_LINE_RE.match(next_line)
                ):
                    break
                if next_line.strip():
                    collected_lines.append(next_line.strip())
                index += 1

            title, speakers, item_type = parse_item_block(collected_lines)
            text_block = clean_text(" ".join(collected_lines))
            if title.lower() in {"none", "none."}:
                continue

            items.append(
                ExtractedAgendaItem(
                    cluster_name=cluster_name,
                    meeting_date=meeting_date,
                    section_number=current_section_number,
                    section_title=current_section_title,
                    item_label=item_label,
                    item_type=item_type,
                    title=title,
                    speakers=speakers,
                    text_block=text_block,
                    topic_tags=infer_topic_tags(text_block),
                )
            )
            continue

        index += 1

    return ExtractedAgendaDocument(
        source_path=str(source_path) if source_path else "<memory>",
        cluster_name=cluster_name,
        meeting_date=meeting_date,
        item_count=len(items),
        items=items,
    )


def normalize_text(text: str) -> str:
    replacements = {
        "Ã¢â‚¬â€œ": "-",
        "Ã¢â‚¬â€": "-",
        "Ã¢â‚¬â„¢": "'",
        "Ã¢â‚¬Å“": '"',
        "Ã¢â‚¬\x9d": '"',
        "\u00a0": " ",
    }
    normalized = text
    for old, new in replacements.items():
        normalized = normalized.replace(old, new)
    normalized = re.sub(r"([A-Z])\n([A-Z])", r"\1\2", normalized)
    normalized = re.sub(r"([a-z])\n([a-z])", r"\1\2", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized


def detect_cluster_name(text: str) -> str | None:
    lines = [clean_text(line) for line in text.splitlines() if clean_text(line)]
    for idx, line in enumerate(lines):
        if "Board of Supervisors" in line:
            for candidate in lines[idx : idx + 6]:
                if "Cluster" in candidate and "address" not in candidate.lower():
                    match = CLUSTER_RE.search(candidate)
                    if match:
                        return clean_text(match.group(1) + " Cluster")
    match = CLUSTER_RE.search(text)
    if not match:
        return None
    return clean_text(match.group(1) + " Cluster")


def detect_meeting_date(text: str) -> str | None:
    match = DATE_RE.search(text)
    if not match:
        return None
    return match.group(1)


def parse_item_block(lines: list[str]) -> tuple[str, list[str], str]:
    speakers: list[str] = []
    body_lines: list[str] = []
    item_type = "other"
    collecting_speakers = False

    for line in lines:
        speaker_match = SPEAKER_RE.match(line)
        if speaker_match:
            collecting_speakers = True
            speaker_value = speaker_match.group(1)
            if speaker_value:
                speakers.extend(split_speakers(speaker_value))
            continue
        if collecting_speakers:
            bullet_match = SPEAKER_BULLET_RE.match(line)
            if bullet_match:
                speakers.append(clean_text(bullet_match.group(1)))
                continue
            if not line.strip():
                continue
            collecting_speakers = False
        body_lines.append(line)

    cleaned_body = [clean_text(line) for line in body_lines if clean_text(line)]
    if cleaned_body and cleaned_body[0].upper().startswith("BOARD LETTER"):
        item_type = "board_letter"
        cleaned_body = cleaned_body[1:]
    elif cleaned_body and cleaned_body[0].upper().startswith("BOARD BRIEFING"):
        item_type = "board_briefing"
        cleaned_body = cleaned_body[1:]
    elif cleaned_body and cleaned_body[0].upper().startswith("MOTION"):
        item_type = "board_motion"
        cleaned_body = cleaned_body[1:]

    title = clean_text(" ".join(cleaned_body))
    return title, speakers, item_type


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def infer_topic_tags(text: str) -> list[str]:
    lowered = text.lower()
    tags = [tag for tag, keywords in TOPIC_RULES.items() if any(keyword in lowered for keyword in keywords)]
    return sorted(set(tags))


def split_speakers(value: str) -> list[str]:
    normalized = value.replace(" and ", ", ")
    return [clean_text(part) for part in normalized.split(",") if clean_text(part)]


def write_structured_items(document: ExtractedAgendaDocument, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(document.to_dict(), indent=2), encoding="utf-8")
