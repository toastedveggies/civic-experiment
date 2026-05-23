from __future__ import annotations

import html
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable


DEFAULT_PARSER_NAME = "la_county_cluster_text"
LA_CITY_PRIMEGOV_HTML_PARSER = "la_city_primegov_html"

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

PRIMEGOV_HTML_MARKER_RE = re.compile(
    r"class=['\"]meeting-item['\"]|data-sectionid=|id=['\"]MeetingContents['\"]",
    re.IGNORECASE,
)
PRIMEGOV_SECTION_START_RE = re.compile(
    r"<div[^>]*class=['\"][^'\"]*section-with-items[^'\"]*['\"][^>]*>",
    re.IGNORECASE,
)
PRIMEGOV_SECTION_TITLE_RE = re.compile(
    r"<tr class=['\"]section-row['\"]>.*?<p[^>]*>(.*?)</p>.*?</tr>",
    re.IGNORECASE | re.DOTALL,
)
PRIMEGOV_ITEM_START_RE = re.compile(
    r"<div[^>]*class=['\"][^'\"]*meeting-item[^'\"]*['\"][^>]*>",
    re.IGNORECASE,
)
PRIMEGOV_ITEM_LABEL_RE = re.compile(r"<td class=['\"]number-cell['\"].*?\((\d+)\)", re.IGNORECASE | re.DOTALL)
PRIMEGOV_COUNCIL_FILE_RE = re.compile(
    r"<td colspan=['\"]2['\"][^>]*>(.*?)</td>",
    re.IGNORECASE | re.DOTALL,
)
PRIMEGOV_DESCRIPTION_RE = re.compile(
    r"<tr>\s*<td[^>]*></td>\s*<td[^>]*>(.*?)</td>\s*</tr>",
    re.IGNORECASE | re.DOTALL,
)
PRIMEGOV_TITLE_RE = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)
PRIMEGOV_BODY_HEADING_RE = re.compile(
    r"text-transform:uppercase[^>]*>([^<]+)</span></p>"
    r".*?text-transform:uppercase[^>]*>([A-Za-z]+,\s+[A-Za-z]+\s+\d{1,2},\s+\d{4})\s*-\s*[^<]+</span>",
    re.IGNORECASE | re.DOTALL,
)
PRIMEGOV_FISCAL_RE = re.compile(
    r"Fiscal Impact Statement:\s*(.*?)(?:Community Impact Statement:|TIME LIMIT FILE|LAST DAY FOR COUNCIL ACTION|$)",
    re.IGNORECASE | re.DOTALL,
)
PRIMEGOV_COMMUNITY_RE = re.compile(
    r"Community Impact Statement:\s*(.*?)(?:TIME LIMIT FILE|LAST DAY FOR COUNCIL ACTION|$)",
    re.IGNORECASE | re.DOTALL,
)

TOPIC_RULES = {
    "housing": ["housing", "homekey", "multifamily", "supportive housing", "homelessness", "tenant"],
    "homelessness": ["homeless", "homelessness", "outreach", "coordinated entry", "interim housing"],
    "public_safety": ["fire", "security", "sheriff", "crime", "probation", "public safety"],
    "probation": ["probation", "halls", "camps"],
    "jails": ["jail", "incarcerated", "cremation"],
    "behavioral_health": ["mental health", "behavioral health", "health"],
    "governance": ["agreement", "authority", "delegated authority", "policy", "equity framework", "oversight"],
    "contracting": ["contract", "sole source", "agreement", "amendment", "master agreements"],
    "budget": ["budget", "fund", "appropriation", "measure ula"],
    "labor": ["workers", "compensation"],
    "data_systems": ["systems", "system", "maintenance", "engineering", "data integration", "dashboard", "hmis", "coordinated entry"],
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


ParserFn = Callable[[str, Path | None], ExtractedAgendaDocument]


def extract_agenda_items_from_text_path(
    path: Path, parser_name: str | None = None
) -> ExtractedAgendaDocument:
    text = path.read_text(encoding="utf-8")
    return extract_agenda_items_from_text(text, path, parser_name=parser_name)


def extract_agenda_items_from_text(
    text: str,
    source_path: Path | None = None,
    parser_name: str | None = None,
) -> ExtractedAgendaDocument:
    selected_parser = parser_name or detect_parser_name(text, source_path)
    parser = get_parser(selected_parser)
    return parser(text, source_path)


def detect_parser_name(text: str, source_path: Path | None = None) -> str:
    if looks_like_primegov_html(text):
        return LA_CITY_PRIMEGOV_HTML_PARSER
    return DEFAULT_PARSER_NAME


def get_parser(parser_name: str) -> ParserFn:
    registry: dict[str, ParserFn] = {
        DEFAULT_PARSER_NAME: extract_la_county_cluster_text_items,
        LA_CITY_PRIMEGOV_HTML_PARSER: extract_primegov_html_agenda_items,
    }
    if parser_name not in registry:
        raise KeyError(f"Unknown parser: {parser_name}")
    return registry[parser_name]


def is_preferred_text_path_for_parser(path: Path, parser_name: str | None) -> bool:
    if parser_name == LA_CITY_PRIMEGOV_HTML_PARSER:
        return "_html-" in path.name.lower()
    return True


def looks_like_primegov_html(text: str) -> bool:
    return bool(PRIMEGOV_HTML_MARKER_RE.search(text))


def extract_la_county_cluster_text_items(
    text: str, source_path: Path | None = None
) -> ExtractedAgendaDocument:
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


def extract_primegov_html_agenda_items(
    text: str, source_path: Path | None = None
) -> ExtractedAgendaDocument:
    normalized = normalize_text(text)
    body_name, meeting_date = detect_primegov_body_and_date(normalized)
    items: list[ExtractedAgendaItem] = []

    for section_body in split_primegov_section_blocks(normalized):
        section_title_match = PRIMEGOV_SECTION_TITLE_RE.search(section_body)
        if not section_title_match:
            continue
        section_title = clean_text(html_fragment_to_text(section_title_match.group(1)))
        if not section_title:
            continue

        for item_html in split_primegov_item_blocks(section_body):
            item_label_match = PRIMEGOV_ITEM_LABEL_RE.search(item_html)
            council_file_match = PRIMEGOV_COUNCIL_FILE_RE.search(item_html)
            description_match = PRIMEGOV_DESCRIPTION_RE.search(item_html)
            if not item_label_match or not council_file_match or not description_match:
                continue

            item_label = item_label_match.group(1)
            council_file = clean_text(html_fragment_to_text(council_file_match.group(1)))
            description = clean_text(html_fragment_to_text(description_match.group(1)))
            if not description:
                continue

            fiscal_impact = extract_labeled_html_value(item_html, PRIMEGOV_FISCAL_RE)
            community_impact = extract_labeled_html_value(item_html, PRIMEGOV_COMMUNITY_RE)

            text_parts = [f"Council File: {council_file}", description]
            if fiscal_impact:
                text_parts.append(f"Fiscal Impact Statement: {fiscal_impact}")
            if community_impact:
                text_parts.append(f"Community Impact Statement: {community_impact}")
            text_block = clean_text(" ".join(text_parts))

            items.append(
                ExtractedAgendaItem(
                    cluster_name=body_name,
                    meeting_date=meeting_date,
                    section_number=section_title,
                    section_title=section_title,
                    item_label=item_label,
                    item_type="primegov_agenda_item",
                    title=description,
                    speakers=[],
                    text_block=text_block,
                    topic_tags=infer_topic_tags(f"{section_title} {text_block}"),
                )
            )

    return ExtractedAgendaDocument(
        source_path=str(source_path) if source_path else "<memory>",
        cluster_name=body_name,
        meeting_date=meeting_date,
        item_count=len(items),
        items=items,
    )


def split_primegov_item_blocks(section_body: str) -> list[str]:
    starts = list(PRIMEGOV_ITEM_START_RE.finditer(section_body))
    if not starts:
        return []
    blocks: list[str] = []
    for index, match in enumerate(starts):
        start = match.start()
        end = starts[index + 1].start() if index + 1 < len(starts) else len(section_body)
        blocks.append(section_body[start:end])
    return blocks


def split_primegov_section_blocks(text: str) -> list[str]:
    starts = list(PRIMEGOV_SECTION_START_RE.finditer(text))
    if not starts:
        return []
    blocks: list[str] = []
    for index, match in enumerate(starts):
        start = match.start()
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        blocks.append(text[start:end])
    return blocks


def normalize_text(text: str) -> str:
    replacements = {
        "ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“": "-",
        "ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â": "-",
        "ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢": "'",
        "ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œ": '"',
        "ÃƒÂ¢Ã¢â€šÂ¬\x9d": '"',
        "Â ": " ",
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


def detect_primegov_body_and_date(text: str) -> tuple[str | None, str | None]:
    heading_match = PRIMEGOV_BODY_HEADING_RE.search(text)
    if heading_match:
        return clean_text(html.unescape(heading_match.group(1))), clean_text(heading_match.group(2))

    title_matches = [clean_text(html.unescape(match)) for match in PRIMEGOV_TITLE_RE.findall(text)]
    for title_text in reversed(title_matches):
        if not title_text or title_text.lower() == "meeting":
            continue
        parts = [clean_text(part) for part in title_text.split(" - ") if clean_text(part)]
        if not parts:
            continue
        meeting_date = None
        if len(parts) >= 2:
            parsed_date = parse_slash_date(parts[1])
            meeting_date = parsed_date or parts[1]
        return parts[0], meeting_date
    return None, None


def parse_slash_date(value: str) -> str | None:
    match = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", value)
    if not match:
        return None
    month = int(match.group(1))
    day = int(match.group(2))
    year = int(match.group(3))
    month_names = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ]
    return f"{month_names[month - 1]} {day}, {year}"


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


def html_fragment_to_text(value: str) -> str:
    normalized = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
    normalized = re.sub(r"</(?:p|div|tr|li|table|tbody|td|h\d|u|strong|span)>", "\n", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"<[^>]+>", " ", normalized)
    normalized = html.unescape(normalized)
    normalized = normalize_text(normalized)
    lines = [clean_text(line) for line in normalized.splitlines() if clean_text(line)]
    return "\n".join(lines)


def extract_labeled_html_value(item_html: str, pattern: re.Pattern[str]) -> str | None:
    match = pattern.search(item_html)
    if not match:
        return None
    cleaned = clean_text(html_fragment_to_text(match.group(1)))
    return cleaned or None


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
