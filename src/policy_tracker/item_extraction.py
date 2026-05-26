from __future__ import annotations

import html
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from policy_tracker.date_utils import normalize_meeting_date_iso


DEFAULT_PARSER_NAME = "la_county_cluster_text"
LA_CITY_PRIMEGOV_HTML_PARSER = "la_city_primegov_html"
LA_COUNTY_BOS_SOP_PARSER = "la_county_bos_sop_text"
HOMELESSNESS_HOUSING_CLUSTER_PARSER = "la_county_homelessness_housing_cluster"

SECTION_HEADER_RE = re.compile(r"^\s*((?:\d+|[IVXLC]+))\.\s+(.+?)(?::\s*.*)?\s*$", re.IGNORECASE)
ITEM_LETTER_RE = re.compile(r"^\s*([A-Z])[\.\)]\s+(.*\S)\s*$", re.IGNORECASE)
MOTION_LINE_RE = re.compile(
    r"^\s*((?:SD[-/]?\d+(?:/SD?[-/]?\d+)*))\s*(?::|[•\-\u2022])\s*(.*\S)?\s*$",
    re.IGNORECASE,
)
MOTION_DISTRICT_ONLY_RE = re.compile(r"^\s*(SD[-/]?\d+(?:/SD?[-/]?\d+)*)\s*$", re.IGNORECASE)
SPEAKER_RE = re.compile(
    r"^\s*(?:Speaker(?:s|\(s\))?|Presenter(?:s|\(s\))?):\s*(.*\S)?\s*$",
    re.IGNORECASE,
)
SPEAKER_BULLET_RE = re.compile(r"^\s*(?:[\u2022-])\s*(.*\S)\s*$")
DATE_RE = re.compile(
    r"DATE:\s*((?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+)?([A-Za-z]+\s+\d{1,2},\s+\d{4})",
    re.IGNORECASE,
)
CLUSTER_RE = re.compile(r"([A-Za-z &]+) Cluster", re.IGNORECASE)
STOP_LINE_RE = re.compile(
    r"^\s*(IF YOU WOULD LIKE TO EMAIL A COMMENT|PUBLIC COMMENTS?|CLOSED SESSION ITEMS?|UPCOMING ITEM\(S\))",
    re.IGNORECASE,
)
SECTION_NUMBER_ONLY_RE = re.compile(r"^\s*\d+\.\s*$")
MEETING_BOILERPLATE_RE = re.compile(
    r"^\s*("
    r"Agenda Posted:|"
    r"Accommodations:|"
    r"Supporting Documentation:|"
    r"Participate Via|"
    r"Listen Via Telephone:|"
    r"Event Number:|"
    r"Password:|"
    r"Chair:|"
    r"Members:|"
    r"Para Informaci|"
    r"Please Telephone|"
    r"Agendas In Braille|"
    r"Click On .*Qr Code|"
    r"Call \(|"
    r"Access Code:"
    r")",
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
BOS_SOP_MARKER_RE = re.compile(r"STATEMENT OF PROCEEDINGS FOR THE", re.IGNORECASE)
BOS_SOP_SECTION_RE = re.compile(r"^\s*([IVXLC]+)\.\s+(.+?)\s*$", re.IGNORECASE)
BOS_SOP_SECTION_NUMBER_ONLY_RE = re.compile(r"^\s*([IVXLC]+)\.\s*$", re.IGNORECASE)
BOS_SOP_ITEM_RE = re.compile(r"^\s*(\d{1,3})\.\s+(.*\S)\s*$")
BOS_SOP_SET_MATTER_RE = re.compile(
    r"^\s*(?:SET MATTERS?)?\s*Set Matter\s*-?\s*(\d+)\.\s*(.*\S)?\s*$",
    re.IGNORECASE,
)
BOS_SOP_MOTION_RE = re.compile(
    r"On motion of\s+(.+?),\s+seconded by\s+(.+?),\s+(?:this item was\s+|the Board\s+)(.+?)(?:\.\s*|$)",
    re.IGNORECASE,
)
BOS_SOP_ACTION_RE = re.compile(
    r"\b(received and filed|continued(?:\s+\w+)*|duly carried|adopted|approved|rejected|denied)\b",
    re.IGNORECASE,
)
BOS_SOP_VOTE_LINE_RE = re.compile(
    r"^(Ayes|Noes|Absent|Abstain|Abstentions):\s*(.*)$",
    re.IGNORECASE,
)
BOS_SOP_ROLE_PREFIX_RE = re.compile(r"^(Supervisors?|Chair Pro Tem|Chair)\s+", re.IGNORECASE)
BOS_SOP_FILE_ID_RE = re.compile(r"\(\d{2}\s*-\s*\d{4}\)")
BOS_SOP_DATE_LINE_RE = re.compile(
    r"\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})",
    re.IGNORECASE,
)
BOS_SOP_STOP_RE = re.compile(
    r"^\s*(The foregoing is a fair statement of the proceedings|Edward Yen, Executive Officer|Closing\s+\d+)",
    re.IGNORECASE,
)
BOS_SOP_RANGE_ONLY_RE = re.compile(r"^[A-Z][A-Z\s/&.\-]+\s+\d+\s*-\s*\d+\s*$")
BOS_SOP_NOISE_RE = re.compile(
    r"^\s*(Page\s+\d+County of Los Angeles|[A-Za-z]+\s+\d{1,2},\s+\d{4}Board of Supervisors Statement Of Proceedings|BOARD OF SUPERVISORS\s+\d+\s*-\s*\d+|[0-9]+\s*-\s*)",
    re.IGNORECASE,
)
BOS_SOP_BODY_START_RE = re.compile(
    r"^\s*(Report by|Hearing on the proposed|The Department|All persons wishing to testify|Opportunity was given|Interested person|On motion of|After discussion|After hearing|Correspondence was received|No interested persons|Fesia Davenport|The Chief Executive Officer|The Director of|The Auditor-Controller)",
    re.IGNORECASE,
)
REGIONAL_ALIGNMENT_MARKER_RE = re.compile(r"Regional Homeless Alignment", re.IGNORECASE)
REGIONAL_ALIGNMENT_ITEM_RE = re.compile(r"^\s*(\d+)\.\s+(.*\S)\s*$")
REGIONAL_ALIGNMENT_BODY_RE = re.compile(
    r"AGENDA FOR THE REGULAR MEETING OF THE\s+(.*?)\s+(?:Kenneth Hahn Hall|The California Community Foundation|500 W\. Temple Street|500 West Temple Street)",
    re.IGNORECASE | re.DOTALL,
)
REGIONAL_ALIGNMENT_DATE_RE = re.compile(
    r"\b(MONDAY|TUESDAY|WEDNESDAY|THURSDAY|FRIDAY|SATURDAY|SUNDAY),\s+([A-Z][a-z]+\s+\d{1,2},\s+\d{4})",
    re.IGNORECASE,
)
REGIONAL_ALIGNMENT_ATTACHMENTS_ONLY_RE = re.compile(
    r"^(Supporting Document|Public Comment/Written Correspondence|Attachments:|Public Comment)$",
    re.IGNORECASE,
)
REGIONAL_ALIGNMENT_BODY_STOP_RE = re.compile(
    r"^\s*("
    r"Kenneth Hahn Hall|"
    r"The California Community Foundation|"
    r"500 W\. Temple Street|"
    r"500 West Temple Street|"
    r"Thursday,|Friday,|Saturday,|Sunday,|Monday,|Tuesday,|Wednesday,|"
    r"Participate Via|"
    r"Listen Via Telephone:|"
    r"Event Number:|"
    r"Password:|"
    r"Chair:|"
    r"Members:|"
    r"Agenda Posted:|"
    r"Accommodations:|"
    r"Supporting Documentation:|"
    r"Para Informaci|"
    r"Please Telephone"
    r")",
    re.IGNORECASE,
)
HOMELESSNESS_HOUSING_MARKER_RE = re.compile(
    r"(HOMELESS POLICY DEPUTIES MEETING AGENDA|Homelessness\s*&\s*Housing Cluster)",
    re.IGNORECASE,
)
HOMELESSNESS_HOUSING_SECTION_RE = re.compile(
    r"^\s*([IVXLC]+)\.\s*(.*?)(?::\s*[\d:apmAPM\-\u2013 ]+)?\s*$",
    re.IGNORECASE,
)
HOMELESSNESS_HOUSING_2025_HEADER_RE = re.compile(
    r"HOMELESS POLICY DEPUTIES MEETING AGENDA",
    re.IGNORECASE,
)
HOMELESSNESS_HOUSING_STOP_RE = re.compile(
    r"^\s*(NEXT MEETING:|AGN\. NO\.|MOTION BY SUPERVISOR|LA COUNTY DEPARTMENT OF HOMELESS SERVICES AND HOUSING|1\s+LA COUNTY DEPARTMENT OF HOMELESS SERVICES AND HOUSING)\b",
    re.IGNORECASE,
)
HOMELESSNESS_HOUSING_BOILERPLATE_RE = re.compile(
    r"^\s*("
    r"BOARD OF$|BOARD OF SUPERVISORS$|"
    r"First District$|Second District$|Third District$|Fourth District$|Fifth District$|"
    r"Kathryn Barger$|Janice Hahn$|Hilda L\. Solis$|Holly J\. Mitchell$|Lindsey P\. Horvath$|"
    r"MEETING CHAIR:|MEETING FACILITATORS:|"
    r"THIS MEETING IS HELD UNDER THE GUIDELINES OF BOARD POLICY|"
    r"To participate in the meeting|To subscribe to|For members of the public who wish to join|For Spanish Interpretation|For Spanish interpretation|"
    r"Teleconference Number:|Microsoft Teams Link:|"
    r"Members of the public may address the Homelessness\s*&\s*Housing Cluster|"
    r"This teleconference will be muted|"
    r"homelessness_and_housing_comment@|"
    r"Room \d|Los Angeles, California \d{5}|Los Angeles, CA \d{5}|"
    r"Kenneth Hahn Hall of Administration|500 West Temple Street|500 West Temple St\.|"
    r"Location:|"
    r"Date:|Time:|DATE:|TIME:"
    r")",
    re.IGNORECASE,
)
HOMELESSNESS_HOUSING_NAME_RE = re.compile(
    r"^[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'&/-]+){1,5}$"
)
HOMELESSNESS_HOUSING_ITEM_RE = re.compile(r"^\s*([a-z])[\.\)]\s+(.*\S)\s*$")

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
    meeting_date_iso: str | None
    section_number: str
    section_title: str
    item_label: str
    item_type: str
    title: str
    speakers: list[str]
    text_block: str
    topic_tags: list[str]
    source_document_id: str | None = None
    meeting_id: str | None = None
    document_role: str | None = None
    action_text_raw: str | None = None
    vote_text_raw: str | None = None
    final_action: str | None = None
    motion_by: str | None = None
    second_by: str | None = None
    ayes_count: int | None = None
    noes_count: int | None = None
    abstain_count: int | None = None
    absent_count: int | None = None
    ayes_members: list[str] | None = None
    noes_members: list[str] | None = None
    abstain_members: list[str] | None = None
    absent_members: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ExtractedAgendaDocument:
    source_path: str
    cluster_name: str | None
    meeting_date: str | None
    meeting_date_iso: str | None
    item_count: int
    items: list[ExtractedAgendaItem]
    source_document_id: str | None = None
    meeting_id: str | None = None
    document_role: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "cluster_name": self.cluster_name,
            "meeting_date": self.meeting_date,
            "meeting_date_iso": self.meeting_date_iso,
            "item_count": self.item_count,
            "source_document_id": self.source_document_id,
            "meeting_id": self.meeting_id,
            "document_role": self.document_role,
            "items": [item.to_dict() for item in self.items],
        }


ParserFn = Callable[[str, Path | None], ExtractedAgendaDocument]


@dataclass(frozen=True, slots=True)
class ParserDefinition:
    name: str
    description: str
    parser: ParserFn


PARSER_REGISTRY: dict[str, ParserDefinition] = {}


def _register_parser(name: str, description: str, parser: ParserFn) -> None:
    PARSER_REGISTRY[name] = ParserDefinition(name=name, description=description, parser=parser)


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
    document = parser(text, source_path)
    return finalize_extracted_document(document, selected_parser)


def detect_parser_name(text: str, source_path: Path | None = None) -> str:
    if looks_like_primegov_html(text):
        return LA_CITY_PRIMEGOV_HTML_PARSER
    if looks_like_bos_sop_text(text):
        return LA_COUNTY_BOS_SOP_PARSER
    if looks_like_homelessness_housing_cluster(text):
        return HOMELESSNESS_HOUSING_CLUSTER_PARSER
    return DEFAULT_PARSER_NAME


def get_parser(parser_name: str) -> ParserFn:
    if parser_name not in PARSER_REGISTRY:
        raise KeyError(f"Unknown parser: {parser_name}")
    return PARSER_REGISTRY[parser_name].parser


def list_parsers() -> list[dict[str, str]]:
    return [
        {"name": definition.name, "description": definition.description}
        for definition in PARSER_REGISTRY.values()
    ]


def is_preferred_text_path_for_parser(path: Path, parser_name: str | None) -> bool:
    if parser_name == LA_CITY_PRIMEGOV_HTML_PARSER:
        return "_html-" in path.name.lower()
    return True


def looks_like_primegov_html(text: str) -> bool:
    return bool(PRIMEGOV_HTML_MARKER_RE.search(text))


def looks_like_bos_sop_text(text: str) -> bool:
    return bool(BOS_SOP_MARKER_RE.search(text) and "Board of Supervisors" in text)


def looks_like_regional_homeless_alignment(text: str) -> bool:
    return bool(REGIONAL_ALIGNMENT_MARKER_RE.search(text) and "AGENDA FOR THE REGULAR MEETING OF THE" in text)


def looks_like_homelessness_housing_cluster(text: str) -> bool:
    return bool(HOMELESSNESS_HOUSING_MARKER_RE.search(text))


def extract_la_county_cluster_text_items(
    text: str, source_path: Path | None = None
) -> ExtractedAgendaDocument:
    if looks_like_regional_homeless_alignment(text):
        return extract_regional_homeless_alignment_items(text, source_path)

    normalized = normalize_text(text)
    lines = [line.rstrip() for line in normalized.splitlines()]
    cluster_name = detect_cluster_name(normalized)
    meeting_date = detect_meeting_date(normalized)
    meeting_date_iso = normalize_meeting_date_iso(meeting_date)

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
                    or is_meeting_boilerplate_line(next_line)
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
                    meeting_date_iso=meeting_date_iso,
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

        motion_match = MOTION_LINE_RE.match(line)
        if motion_match and current_section_number and current_section_title:
            item_label = normalize_motion_label(motion_match.group(1))
            collected_lines = []
            inline_title = motion_match.group(2)
            if inline_title:
                collected_lines.append(inline_title)
            index += 1
            while index < len(lines):
                next_line = lines[index]
                next_clean = next_line.strip()
                if (
                    SECTION_HEADER_RE.match(next_line)
                    or ITEM_LETTER_RE.match(next_line)
                    or MOTION_LINE_RE.match(next_line)
                    or STOP_LINE_RE.match(next_line)
                    or is_meeting_boilerplate_line(next_line)
                    or is_cluster_boundary_line(next_line)
                ):
                    break
                if current_section_title.lower().startswith("motions") and MOTION_DISTRICT_ONLY_RE.match(next_line):
                    break
                if next_clean:
                    collected_lines.append(next_clean)
                index += 1

            title, speakers, item_type = parse_motion_block(collected_lines)
            text_block = clean_text(" ".join(collected_lines))
            if title.lower() in {"none", "none."}:
                continue

            items.append(
                ExtractedAgendaItem(
                    cluster_name=cluster_name,
                    meeting_date=meeting_date,
                    meeting_date_iso=meeting_date_iso,
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

        motion_label_only = MOTION_DISTRICT_ONLY_RE.match(line)
        if motion_label_only and current_section_number and current_section_title:
            item_label = normalize_motion_label(motion_label_only.group(1))
            collected_lines: list[str] = []
            index += 1
            while index < len(lines):
                next_line = lines[index]
                next_clean = next_line.strip()
                if (
                    SECTION_HEADER_RE.match(next_line)
                    or ITEM_LETTER_RE.match(next_line)
                    or MOTION_LINE_RE.match(next_line)
                    or MOTION_DISTRICT_ONLY_RE.match(next_line)
                    or STOP_LINE_RE.match(next_line)
                    or is_meeting_boilerplate_line(next_line)
                    or is_cluster_boundary_line(next_line)
                ):
                    break
                if next_clean:
                    collected_lines.append(next_clean)
                index += 1

            title, speakers, item_type = parse_motion_block(collected_lines)
            text_block = clean_text(" ".join(collected_lines))
            if title.lower() in {"none", "none."}:
                continue

            items.append(
                ExtractedAgendaItem(
                    cluster_name=cluster_name,
                    meeting_date=meeting_date,
                    meeting_date_iso=meeting_date_iso,
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
        meeting_date_iso=meeting_date_iso,
        item_count=len(items),
        items=items,
    )


def extract_regional_homeless_alignment_items(
    text: str, source_path: Path | None = None
) -> ExtractedAgendaDocument:
    normalized = normalize_text(text)
    lines = [line.rstrip() for line in normalized.splitlines()]
    body_name = detect_regional_alignment_body_name(text)
    meeting_date = detect_regional_alignment_meeting_date(text)
    meeting_date_iso = normalize_meeting_date_iso(meeting_date)
    items: list[ExtractedAgendaItem] = []
    current_section_number = ""
    current_section_title = ""
    index = 0

    while index < len(lines):
        line = clean_text(lines[index])
        if not line:
            index += 1
            continue

        section_match = SECTION_HEADER_RE.match(line)
        if section_match and not REGIONAL_ALIGNMENT_ITEM_RE.match(line):
            current_section_number = section_match.group(1).upper()
            current_section_title = clean_text(section_match.group(2))
            index += 1
            continue

        item_match = REGIONAL_ALIGNMENT_ITEM_RE.match(line)
        if item_match and current_section_number:
            item_label = item_match.group(1)
            collected_lines = [item_match.group(2)]
            index += 1
            while index < len(lines):
                next_line = clean_text(lines[index])
                if not next_line:
                    index += 1
                    continue
                if SECTION_HEADER_RE.match(next_line) and not REGIONAL_ALIGNMENT_ITEM_RE.match(next_line):
                    break
                if REGIONAL_ALIGNMENT_ITEM_RE.match(next_line):
                    break
                if is_meeting_boilerplate_line(next_line):
                    break
                if next_line.startswith("Page "):
                    index += 1
                    continue
                if "Agenda" == next_line or "Agenda" in next_line[-10:]:
                    index += 1
                    continue
                collected_lines.append(next_line)
                index += 1

            title, text_block = parse_regional_alignment_item_block(collected_lines)
            if title:
                items.append(
                    ExtractedAgendaItem(
                        cluster_name=body_name,
                        meeting_date=meeting_date,
                        meeting_date_iso=meeting_date_iso,
                        section_number=current_section_number,
                        section_title=current_section_title,
                        item_label=item_label,
                        item_type="brown_act_agenda_item",
                        title=title,
                        speakers=[],
                        text_block=text_block,
                        topic_tags=infer_topic_tags(f"{current_section_title} {text_block}"),
                    )
                )
            continue

        index += 1

    return ExtractedAgendaDocument(
        source_path=str(source_path) if source_path else "<memory>",
        cluster_name=body_name,
        meeting_date=meeting_date,
        meeting_date_iso=meeting_date_iso,
        item_count=len(items),
        items=items,
    )


def extract_homelessness_housing_cluster_items(
    text: str, source_path: Path | None = None
) -> ExtractedAgendaDocument:
    normalized = normalize_text(text)
    lines = [line.rstrip() for line in normalized.splitlines()]
    cluster_name = "Homelessness & Housing Cluster"
    meeting_date = detect_meeting_date(normalized)
    meeting_date_iso = normalize_meeting_date_iso(meeting_date)

    if HOMELESSNESS_HOUSING_2025_HEADER_RE.search(normalized):
        items = extract_homelessness_housing_2025_items(lines, cluster_name, meeting_date, meeting_date_iso)
    else:
        items = extract_homelessness_housing_2026_items(lines, cluster_name, meeting_date, meeting_date_iso)

    return ExtractedAgendaDocument(
        source_path=str(source_path) if source_path else "<memory>",
        cluster_name=cluster_name,
        meeting_date=meeting_date,
        meeting_date_iso=meeting_date_iso,
        item_count=len(items),
        items=items,
    )


def extract_homelessness_housing_2025_items(
    lines: list[str],
    cluster_name: str,
    meeting_date: str | None,
    meeting_date_iso: str | None,
) -> list[ExtractedAgendaItem]:
    cleaned_lines = [
        clean_text(line)
        for line in lines
        if clean_text(line)
        and not is_homelessness_housing_boilerplate_line(line)
        and clean_text(line) != "AGENDA ITEM LEAD"
    ]
    items: list[ExtractedAgendaItem] = []
    index = 0

    while index < len(cleaned_lines):
        line = cleaned_lines[index]
        if HOMELESSNESS_HOUSING_STOP_RE.match(line):
            break
        section_match = HOMELESSNESS_HOUSING_SECTION_RE.match(line)
        if not section_match:
            index += 1
            continue

        section_number = section_match.group(1).upper()
        tail = clean_text(section_match.group(2))
        block_lines: list[str] = []
        if tail:
            block_lines.append(tail)
        index += 1
        while index < len(cleaned_lines):
            next_line = cleaned_lines[index]
            if HOMELESSNESS_HOUSING_STOP_RE.match(next_line):
                break
            if HOMELESSNESS_HOUSING_SECTION_RE.match(next_line):
                break
            block_lines.append(next_line)
            index += 1

        title, text_block = parse_homelessness_housing_2025_block(block_lines)
        if not title or is_low_value_homelessness_housing_title(title):
            continue
        items.append(
            ExtractedAgendaItem(
                cluster_name=cluster_name,
                meeting_date=meeting_date,
                meeting_date_iso=meeting_date_iso,
                section_number=section_number,
                section_title=title,
                item_label=section_number,
                item_type="cluster_agenda_item",
                title=title,
                speakers=[],
                text_block=text_block,
                topic_tags=infer_topic_tags(text_block),
            )
        )

    return items


def extract_homelessness_housing_2026_items(
    lines: list[str],
    cluster_name: str,
    meeting_date: str | None,
    meeting_date_iso: str | None,
) -> list[ExtractedAgendaItem]:
    items: list[ExtractedAgendaItem] = []
    current_section_number = ""
    current_section_title = ""
    index = 0

    while index < len(lines):
        line = clean_text(lines[index])
        if not line:
            index += 1
            continue
        if HOMELESSNESS_HOUSING_STOP_RE.match(line):
            break
        if is_homelessness_housing_boilerplate_line(line):
            index += 1
            continue

        section_match = HOMELESSNESS_HOUSING_SECTION_RE.match(line)
        if section_match and not ITEM_LETTER_RE.match(line):
            current_section_number = section_match.group(1).upper()
            current_section_title = clean_homelessness_housing_section_title(section_match.group(2))
            index += 1
            continue

        item_match = HOMELESSNESS_HOUSING_ITEM_RE.match(line)
        if item_match and current_section_number and current_section_title:
            item_label = item_match.group(1).upper()
            collected_lines = [item_match.group(2)]
            index += 1
            while index < len(lines):
                next_line = clean_text(lines[index])
                if not next_line:
                    index += 1
                    continue
                if HOMELESSNESS_HOUSING_STOP_RE.match(next_line):
                    break
                if is_homelessness_housing_boilerplate_line(next_line):
                    index += 1
                    continue
                if HOMELESSNESS_HOUSING_SECTION_RE.match(next_line) and not HOMELESSNESS_HOUSING_ITEM_RE.match(next_line):
                    break
                if HOMELESSNESS_HOUSING_ITEM_RE.match(next_line):
                    break
                collected_lines.append(next_line)
                index += 1

            title, speakers, text_block = parse_homelessness_housing_2026_block(collected_lines)
            if title.lower() in {"none", "none."} or is_low_value_homelessness_housing_title(title):
                continue
            items.append(
                ExtractedAgendaItem(
                    cluster_name=cluster_name,
                    meeting_date=meeting_date,
                    meeting_date_iso=meeting_date_iso,
                    section_number=current_section_number,
                    section_title=current_section_title,
                    item_label=item_label,
                    item_type="cluster_agenda_item",
                    title=title,
                    speakers=speakers,
                    text_block=text_block,
                    topic_tags=infer_topic_tags(f"{current_section_title} {text_block}"),
                )
            )
            continue

        index += 1

    return items


def extract_primegov_html_agenda_items(
    text: str, source_path: Path | None = None
) -> ExtractedAgendaDocument:
    normalized = normalize_text(text)
    body_name, meeting_date = detect_primegov_body_and_date(normalized)
    meeting_date_iso = normalize_meeting_date_iso(meeting_date)
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
                    meeting_date_iso=meeting_date_iso,
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
        meeting_date_iso=meeting_date_iso,
        item_count=len(items),
        items=items,
    )


def extract_la_county_bos_sop_items(
    text: str, source_path: Path | None = None
) -> ExtractedAgendaDocument:
    normalized = normalize_text(text, merge_wrapped_words=False)
    lines = clean_bos_sop_lines(normalized.splitlines())
    meeting_date = detect_bos_sop_meeting_date(text)
    meeting_date_iso = normalize_meeting_date_iso(meeting_date)
    items: list[ExtractedAgendaItem] = []
    current_section_number = ""
    current_section_title = ""
    index = 0

    while index < len(lines):
        line = clean_text(lines[index])
        if not line:
            index += 1
            continue
        if BOS_SOP_STOP_RE.match(line):
            break

        section_match = BOS_SOP_SECTION_RE.match(line)
        if section_match:
            current_section_number = section_match.group(1).upper()
            current_section_title = clean_bos_sop_section_title(section_match.group(2))
            index += 1
            continue
        section_number_only_match = BOS_SOP_SECTION_NUMBER_ONLY_RE.match(line)
        if section_number_only_match:
            current_section_number = section_number_only_match.group(1).upper()
            current_section_title = ""
            index += 1
            continue
        if current_section_number and not current_section_title and line.isupper() and len(line) < 80:
            current_section_title = clean_bos_sop_section_title(line)
            index += 1
            continue

        special_item = parse_bos_sop_special_item(
            lines,
            index,
            current_section_number,
            current_section_title,
            meeting_date,
            meeting_date_iso,
        )
        if special_item is not None:
            item, next_index = special_item
            if item is not None:
                items.append(item)
            index = next_index
            continue

        if is_bos_sop_item_start(lines, index):
            item_match = BOS_SOP_ITEM_RE.match(line)
            assert item_match is not None
            item_label = item_match.group(1)
            title_lines = [item_match.group(2)]
            index += 1

            while index < len(lines):
                next_line = clean_text(lines[index])
                if not next_line:
                    index += 1
                    continue
                if BOS_SOP_NOISE_RE.match(next_line):
                    index += 1
                    continue
                if BOS_SOP_BODY_START_RE.match(next_line):
                    break
                if BOS_SOP_SECTION_RE.match(next_line) or BOS_SOP_STOP_RE.match(next_line):
                    break
                title_lines.append(next_line)
                index += 1
                if BOS_SOP_FILE_ID_RE.search(next_line):
                    break

            body_lines: list[str] = []
            while index < len(lines):
                next_line = clean_text(lines[index])
                if not next_line:
                    index += 1
                    continue
                if BOS_SOP_NOISE_RE.match(next_line):
                    index += 1
                    continue
                if BOS_SOP_STOP_RE.match(next_line):
                    break
                if BOS_SOP_SECTION_RE.match(next_line) or is_bos_sop_item_start(lines, index):
                    break
                body_lines.append(next_line)
                index += 1

            title = clean_bos_sop_title(" ".join(title_lines))
            text_block = clean_text(" ".join([title, *body_lines]))
            if title:
                parliamentary = parse_bos_sop_parliamentary_fields([*title_lines, *body_lines])
                items.append(
                    ExtractedAgendaItem(
                        cluster_name="Los Angeles County Board of Supervisors",
                        meeting_date=meeting_date,
                        meeting_date_iso=meeting_date_iso,
                        section_number=current_section_number or "UNSPECIFIED",
                        section_title=current_section_title or "Unspecified",
                        item_label=item_label,
                        item_type=infer_bos_sop_item_type(title, current_section_title),
                        title=title,
                        speakers=[],
                        text_block=text_block,
                        topic_tags=infer_topic_tags(f"{current_section_title} {text_block}"),
                        action_text_raw=parliamentary["action_text_raw"],
                        vote_text_raw=parliamentary["vote_text_raw"],
                        final_action=parliamentary["final_action"],
                        motion_by=parliamentary["motion_by"],
                        second_by=parliamentary["second_by"],
                        ayes_count=parliamentary["ayes_count"],
                        noes_count=parliamentary["noes_count"],
                        abstain_count=parliamentary["abstain_count"],
                        absent_count=parliamentary["absent_count"],
                        ayes_members=parliamentary["ayes_members"],
                        noes_members=parliamentary["noes_members"],
                        abstain_members=parliamentary["abstain_members"],
                        absent_members=parliamentary["absent_members"],
                    )
                )
            continue

        index += 1

    return ExtractedAgendaDocument(
        source_path=str(source_path) if source_path else "<memory>",
        cluster_name="Los Angeles County Board of Supervisors",
        meeting_date=meeting_date,
        meeting_date_iso=meeting_date_iso,
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


def clean_bos_sop_lines(lines: list[str]) -> list[str]:
    cleaned_lines: list[str] = []
    for raw_line in lines:
        line = clean_text(raw_line)
        if not line:
            cleaned_lines.append("")
            continue
        if BOS_SOP_NOISE_RE.match(line):
            continue
        cleaned_lines.append(line)
    return cleaned_lines


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


def normalize_text(text: str, merge_wrapped_words: bool = True) -> str:
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
    if merge_wrapped_words:
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
                    cluster_name = extract_cluster_name(candidate)
                    if cluster_name:
                        return cluster_name
    for candidate in lines:
        cluster_name = extract_cluster_name(candidate)
        if cluster_name:
            return cluster_name
    return extract_cluster_name(text)


def detect_meeting_date(text: str) -> str | None:
    match = DATE_RE.search(text)
    if not match:
        return None
    weekday = clean_text(match.group(1) or "").rstrip(",")
    date_value = clean_text(match.group(2))
    if weekday:
        return clean_text(f"{weekday}, {date_value}")
    return date_value


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


def detect_bos_sop_meeting_date(text: str) -> str | None:
    for raw_line in text.splitlines():
        line = clean_text(raw_line)
        match = BOS_SOP_DATE_LINE_RE.search(line)
        if match:
            return clean_text(f"{match.group(1)}, {match.group(2)}")
    return None


def detect_regional_alignment_body_name(text: str) -> str | None:
    match = REGIONAL_ALIGNMENT_BODY_RE.search(text)
    if match:
        body = clean_text(match.group(1).replace("\n", " "))
        return clean_regional_alignment_body_name(body)

    lines = [clean_text(line) for line in text.splitlines()]
    for index, line in enumerate(lines):
        if line.upper() == "AGENDA FOR THE REGULAR MEETING OF THE":
            collected: list[str] = []
            probe = index + 1
            while probe < len(lines):
                candidate = lines[probe]
                if not candidate:
                    break
                if candidate.startswith("I. "):
                    break
                if REGIONAL_ALIGNMENT_BODY_STOP_RE.match(candidate):
                    break
                collected.append(candidate)
                probe += 1
            if collected:
                return clean_regional_alignment_body_name(" ".join(collected))
    return None


def detect_regional_alignment_meeting_date(text: str) -> str | None:
    match = REGIONAL_ALIGNMENT_DATE_RE.search(text)
    if not match:
        return None
    return clean_text(f"{match.group(1).title()}, {match.group(2).title()}")


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
        if is_meeting_boilerplate_line(line):
            break
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


def parse_regional_alignment_item_block(lines: list[str]) -> tuple[str, str]:
    cleaned_lines = [clean_text(line) for line in lines if clean_text(line)]
    filtered_lines: list[str] = []
    for line in cleaned_lines:
        if REGIONAL_ALIGNMENT_ATTACHMENTS_ONLY_RE.match(line):
            continue
        if is_meeting_boilerplate_line(line):
            break
        if line.startswith("Page "):
            continue
        filtered_lines.append(line)

    title = clean_text(filtered_lines[0]) if filtered_lines else ""
    title = clean_text(BOS_SOP_FILE_ID_RE.sub("", title)).strip(" -")
    text_block = clean_text(" ".join(filtered_lines))
    return title, text_block


def parse_homelessness_housing_2025_block(lines: list[str]) -> tuple[str, str]:
    filtered_lines = [
        clean_text(line)
        for line in lines
        if clean_text(line)
        and not HOMELESSNESS_HOUSING_STOP_RE.match(clean_text(line))
        and not is_homelessness_housing_boilerplate_line(line)
    ]
    if not filtered_lines:
        return "", ""

    title_parts: list[str] = []
    body_parts: list[str] = []
    collecting_title = True
    for line in filtered_lines:
        if collecting_title and looks_like_person_name(line):
            collecting_title = False
        if collecting_title:
            title_parts.append(line)
        else:
            body_parts.append(line)

    title = clean_text(" ".join(title_parts or filtered_lines[:1]))
    text_block = clean_text(" ".join([title, *body_parts]))
    return title, text_block


def parse_homelessness_housing_2026_block(lines: list[str]) -> tuple[str, list[str], str]:
    cleaned_lines = [
        clean_text(line)
        for line in lines
        if clean_text(line)
        and not HOMELESSNESS_HOUSING_STOP_RE.match(clean_text(line))
        and not is_homelessness_housing_boilerplate_line(line)
    ]
    if not cleaned_lines:
        return "", [], ""

    speakers: list[str] = []
    body_lines: list[str] = []
    collecting_presenters = False

    for line in cleaned_lines:
        if re.match(r"^Presenters?:\s*$", line, re.IGNORECASE):
            collecting_presenters = True
            continue
        bullet_match = SPEAKER_BULLET_RE.match(line)
        if collecting_presenters and bullet_match:
            speaker_value = clean_text(bullet_match.group(1))
            speakers.append(speaker_value)
            body_lines.append(speaker_value)
            continue
        if collecting_presenters and line.startswith("\u2022"):
            speaker_value = clean_text(line.lstrip("\u2022").strip())
            speakers.append(speaker_value)
            body_lines.append(speaker_value)
            continue
        body_lines.append(line)

    title = clean_text(cleaned_lines[0])
    title = re.sub(r"\s*\([\d:.\-apmAPM ]+\)\s*$", "", title).strip()
    text_block = clean_text(" ".join(body_lines))
    return title, speakers, text_block


def parse_motion_block(lines: list[str]) -> tuple[str, list[str], str]:
    cleaned_lines = [clean_text(line) for line in lines if clean_text(line)]
    cleaned_lines = [
        line
        for line in cleaned_lines
        if line.upper() not in {"MOTION", "MOTIONS:", "MOTIONS"}
    ]
    title = clean_text(" ".join(cleaned_lines))
    title = re.sub(r"^[•\-\u2022]\s*", "", title)
    return title, [], "board_motion"


def normalize_motion_label(value: str) -> str:
    return clean_text(value.upper().replace(" ", ""))


def extract_cluster_name(value: str) -> str | None:
    match = CLUSTER_RE.search(value)
    if not match:
        return None
    cluster_name = clean_text(match.group(1) + " Cluster")
    cluster_name = re.sub(r"^(?:Members of the Public may address(?: the)?\s+)", "", cluster_name, flags=re.IGNORECASE)
    cluster_name = re.sub(r"\s*-\s*Agenda.*$", "", cluster_name, flags=re.IGNORECASE)
    cluster_name = re.sub(r"\s+", " ", cluster_name).strip(" -")
    if len(cluster_name) > 120:
        return None
    return cluster_name or None


def clean_regional_alignment_body_name(value: str) -> str | None:
    cleaned = clean_text(value)
    cleaned = re.split(
        r"\b(?:Los Angeles Homeless Services Authority|Kenneth Hahn Hall|The California Community Foundation|637 Wilshire Boulevard|500 W\. Temple Street|500 West Temple Street)\b",
        cleaned,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    cleaned = re.split(
        r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\b",
        cleaned,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    cleaned = re.split(
        r"\b(?:Participate Via|Listen Via Telephone:|Chair:|Members:|Agenda Posted:|Accommodations:|Supporting Documentation:)\b",
        cleaned,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    cleaned = clean_text(cleaned).title()
    return cleaned or None


def clean_homelessness_housing_section_title(value: str) -> str:
    cleaned = clean_text(value)
    cleaned = re.sub(r":\s*[\d:.\-apmAPM ]+$", "", cleaned)
    cleaned = re.sub(r"\s*\([\d:.\-apmAPM ]+\)\s*$", "", cleaned)
    return clean_text(cleaned)


def is_homelessness_housing_boilerplate_line(value: str) -> bool:
    cleaned = clean_text(value)
    if not cleaned:
        return False
    if HOMELESSNESS_HOUSING_BOILERPLATE_RE.match(cleaned):
        return True
    if cleaned.isdigit():
        return True
    if cleaned in {
        "Board of Supervisors",
        "Agenda Review Meeting",
        "HOMELESS POLICY DEPUTIES MEETING AGENDA",
        "MEETING WILL TAKE PLACE 100% VIRTUALLY",
        "MEETING WILL TAKE PLACE IN PERSON WITH A VIRTUAL OPTION",
        "THIS MEETING WILL BE CONDUCTED 100% VIRTUALLY",
        "THIS MEETING WILL BE",
    }:
        return True
    return False


def parse_bos_sop_parliamentary_fields(body_lines: list[str]) -> dict[str, Any]:
    joined_text = clean_text(" ".join(body_lines))
    action_text_raw: str | None = None
    vote_lines: list[str] = []
    motion_by: str | None = None
    second_by: str | None = None
    final_action: str | None = None
    votes: dict[str, list[str]] = {
        "ayes": [],
        "noes": [],
        "abstain": [],
        "absent": [],
    }

    motion_match = BOS_SOP_MOTION_RE.search(joined_text)
    if motion_match:
        motion_by = clean_bos_vote_member_name(motion_match.group(1))
        second_by = clean_bos_vote_member_name(motion_match.group(2))
        action_text_raw = clean_text(motion_match.group(0))
        final_action = normalize_bos_final_action(motion_match.group(3))
    elif joined_text.lower().startswith(("after discussion", "after hearing", "by common consent", "opportunity was given")):
        action_text_raw = joined_text
        final_action = normalize_bos_final_action(joined_text)

    for line in body_lines:
        cleaned = clean_text(line)
        if not cleaned:
            continue
        if action_text_raw is None and (
            cleaned.lower().startswith("after discussion")
            or cleaned.lower().startswith("after hearing")
            or cleaned.lower().startswith("by common consent")
            or cleaned.lower().startswith("opportunity was given")
        ):
            action_text_raw = cleaned
            final_action = normalize_bos_final_action(cleaned)
        vote_match = BOS_SOP_VOTE_LINE_RE.match(cleaned)
        if vote_match:
            label = vote_match.group(1).lower()
            members = parse_bos_vote_members(vote_match.group(2))
            vote_lines.append(cleaned)
            if label.startswith("aye"):
                votes["ayes"] = members
            elif label.startswith("noe"):
                votes["noes"] = members
            elif label.startswith("abstain"):
                votes["abstain"] = members
            elif label.startswith("absent"):
                votes["absent"] = members

    return {
        "action_text_raw": action_text_raw,
        "vote_text_raw": clean_text(" ".join(vote_lines)) or None,
        "final_action": final_action,
        "motion_by": motion_by,
        "second_by": second_by,
        "ayes_count": len(votes["ayes"]) or None,
        "noes_count": len(votes["noes"]) or None,
        "abstain_count": len(votes["abstain"]) or None,
        "absent_count": len(votes["absent"]) or None,
        "ayes_members": votes["ayes"],
        "noes_members": votes["noes"],
        "abstain_members": votes["abstain"],
        "absent_members": votes["absent"],
    }


def parse_bos_vote_members(value: str) -> list[str]:
    cleaned = clean_text(re.sub(r"\b\d+\s*-\s*$", "", value))
    if not cleaned:
        return []
    normalized = cleaned.replace(" and ", ", ")
    parts = [clean_bos_vote_member_name(part) for part in normalized.split(",")]
    return [part for part in parts if part]


def clean_bos_vote_member_name(value: str) -> str:
    cleaned = clean_text(BOS_SOP_ROLE_PREFIX_RE.sub("", value))
    return cleaned.strip(" .;-")


def normalize_bos_final_action(value: str) -> str | None:
    match = BOS_SOP_ACTION_RE.search(value)
    if not match:
        return None
    action = match.group(1).lower()
    if "received and filed" in action:
        return "received_and_filed"
    if action.startswith("continued"):
        return "continued"
    if action == "duly carried":
        return "approved"
    return action.replace(" ", "_")


def looks_like_person_name(value: str) -> bool:
    cleaned = clean_text(value)
    return bool(HOMELESSNESS_HOUSING_NAME_RE.match(cleaned))


def is_low_value_homelessness_housing_title(value: str) -> bool:
    lowered = clean_text(value).lower().rstrip("*")
    exact_matches = {
        "adjournment",
        "call to order",
        "future agenda items",
        "items recommended for future discussion",
    }
    if lowered in exact_matches:
        return True
    return lowered.startswith("public comment") or lowered.startswith("welcome and introductions")


def is_meeting_boilerplate_line(value: str) -> bool:
    cleaned = clean_text(value)
    if not cleaned:
        return False
    return bool(MEETING_BOILERPLATE_RE.match(cleaned))


def is_cluster_boundary_line(value: str) -> bool:
    cleaned = clean_text(value)
    if not cleaned:
        return False
    if SECTION_NUMBER_ONLY_RE.match(cleaned):
        return True
    if cleaned.lower() in {"board of", "supervisors"}:
        return True
    if cleaned.lower().startswith("board of supervisors"):
        return True
    return False


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


def finalize_extracted_document(
    document: ExtractedAgendaDocument,
    parser_name: str,
) -> ExtractedAgendaDocument:
    document_role = document.document_role or default_document_role_for_parser(parser_name)
    for item in document.items:
        if item.document_role is None:
            item.document_role = document_role
        enrich_generic_action_fields(item)
    document.document_role = document_role
    document.item_count = len(document.items)
    return document


def default_document_role_for_parser(parser_name: str) -> str:
    if parser_name == LA_COUNTY_BOS_SOP_PARSER:
        return "proceedings"
    return "agenda"


def enrich_generic_action_fields(item: ExtractedAgendaItem) -> None:
    if item.action_text_raw and item.final_action:
        return

    text = clean_text(item.text_block or "")
    if not text:
        return

    parliamentary = parse_bos_sop_parliamentary_fields([text])
    if item.action_text_raw is None:
        item.action_text_raw = parliamentary["action_text_raw"]
    if item.vote_text_raw is None:
        item.vote_text_raw = parliamentary["vote_text_raw"]
    if item.final_action is None:
        item.final_action = parliamentary["final_action"]
    if item.motion_by is None:
        item.motion_by = parliamentary["motion_by"]
    if item.second_by is None:
        item.second_by = parliamentary["second_by"]
    if item.ayes_count is None:
        item.ayes_count = parliamentary["ayes_count"]
    if item.noes_count is None:
        item.noes_count = parliamentary["noes_count"]
    if item.abstain_count is None:
        item.abstain_count = parliamentary["abstain_count"]
    if item.absent_count is None:
        item.absent_count = parliamentary["absent_count"]
    if item.ayes_members is None:
        item.ayes_members = parliamentary["ayes_members"]
    if item.noes_members is None:
        item.noes_members = parliamentary["noes_members"]
    if item.abstain_members is None:
        item.abstain_members = parliamentary["abstain_members"]
    if item.absent_members is None:
        item.absent_members = parliamentary["absent_members"]


def is_bos_sop_item_start(lines: list[str], index: int) -> bool:
    line = clean_text(lines[index])
    if not line or BOS_SOP_RANGE_ONLY_RE.match(line) or BOS_SOP_NOISE_RE.match(line):
        return False
    match = BOS_SOP_ITEM_RE.match(line)
    if not match:
        return False
    if BOS_SOP_FILE_ID_RE.search(line):
        return True

    lookahead_limit = min(len(lines), index + 6)
    for probe_index in range(index + 1, lookahead_limit):
        probe = clean_text(lines[probe_index])
        if not probe:
            continue
        if BOS_SOP_SECTION_RE.match(probe):
            break
        if BOS_SOP_ITEM_RE.match(probe) and not BOS_SOP_FILE_ID_RE.search(probe):
            break
        if BOS_SOP_FILE_ID_RE.search(probe):
            return True
    return False


def parse_bos_sop_special_item(
    lines: list[str],
    index: int,
    current_section_number: str,
    current_section_title: str,
    meeting_date: str | None,
    meeting_date_iso: str | None,
) -> tuple[ExtractedAgendaItem | None, int] | None:
    line = clean_text(lines[index])
    set_matter_match = BOS_SOP_SET_MATTER_RE.match(line)
    item_match = BOS_SOP_ITEM_RE.match(line)
    if not current_section_title and not set_matter_match:
        return None

    section_title = current_section_title
    if set_matter_match and not section_title:
        section_title = "SET MATTER"
    section_upper = section_title.upper()
    if "SET MATTER" not in section_upper and "PUBLIC HEARING" not in section_upper:
        return None

    if not set_matter_match and not item_match:
        return None

    if set_matter_match:
        item_label = set_matter_match.group(1)
        inline_title = clean_text(set_matter_match.group(2) or "")
    else:
        assert item_match is not None
        item_label = item_match.group(1)
        inline_title = clean_text(item_match.group(2) or "")

    title_lines: list[str] = []
    if inline_title:
        title_lines.append(inline_title)
    probe = index + 1
    while probe < len(lines):
        next_line = clean_text(lines[probe])
        if not next_line:
            probe += 1
            continue
        if BOS_SOP_NOISE_RE.match(next_line):
            probe += 1
            continue
        if BOS_SOP_STOP_RE.match(next_line) or BOS_SOP_SECTION_RE.match(next_line):
            break
        if BOS_SOP_SET_MATTER_RE.match(next_line) or BOS_SOP_ITEM_RE.match(next_line):
            break
        if BOS_SOP_BODY_START_RE.match(next_line):
            break
        if BOS_SOP_FILE_ID_RE.search(next_line):
            break
        title_lines.append(next_line)
        probe += 1

    body_lines: list[str] = []
    while probe < len(lines):
        next_line = clean_text(lines[probe])
        if not next_line:
            probe += 1
            continue
        if BOS_SOP_NOISE_RE.match(next_line):
            probe += 1
            continue
        if BOS_SOP_STOP_RE.match(next_line) or BOS_SOP_SECTION_RE.match(next_line):
            break
        if BOS_SOP_SET_MATTER_RE.match(next_line) or is_bos_sop_item_start(lines, probe):
            break
        body_lines.append(next_line)
        probe += 1

    title = clean_bos_sop_title(" ".join(title_lines))
    text_block = clean_text(" ".join([title, *body_lines]))
    if not title:
        return None, probe

    item = ExtractedAgendaItem(
        cluster_name="Los Angeles County Board of Supervisors",
        meeting_date=meeting_date,
        meeting_date_iso=meeting_date_iso,
        section_number=current_section_number or "UNSPECIFIED",
        section_title=section_title or "Unspecified",
        item_label=item_label,
        item_type=infer_bos_sop_item_type(title, section_title),
        title=title,
        speakers=[],
        text_block=text_block,
        topic_tags=infer_topic_tags(f"{section_title} {text_block}"),
        **parse_bos_sop_parliamentary_fields([*title_lines, *body_lines]),
    )
    return item, probe


def clean_bos_sop_title(value: str) -> str:
    cleaned = clean_text(BOS_SOP_FILE_ID_RE.sub("", value))
    return cleaned.strip(" -")


def clean_bos_sop_section_title(value: str) -> str:
    cleaned = clean_text(value)
    cleaned = re.sub(r"BOARD OF SUPERVISORS\s+\d+\s*-\s*\d+\s*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+\d+\s*-\s*\d+\s*$", "", cleaned)
    cleaned = re.sub(r"\s+\d+\s*$", "", cleaned)
    return clean_text(cleaned)


def infer_bos_sop_item_type(title: str, section_title: str) -> str:
    lowered_title = title.lower()
    lowered_section = section_title.lower()
    if lowered_title.startswith("motion "):
        return "board_motion"
    if "hearing" in lowered_title or "public hearing" in lowered_section:
        return "public_hearing"
    if "ordinance" in lowered_section or lowered_title.startswith("ordinance "):
        return "ordinance"
    if "closed session" in lowered_section:
        return "closed_session"
    return "bos_sop_item"


def split_speakers(value: str) -> list[str]:
    normalized = value.replace(" and ", ", ")
    return [clean_text(part) for part in normalized.split(",") if clean_text(part)]


def write_structured_items(document: ExtractedAgendaDocument, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(document.to_dict(), indent=2), encoding="utf-8")


_register_parser(
    DEFAULT_PARSER_NAME,
    "LA County cluster-style extracted text agendas.",
    extract_la_county_cluster_text_items,
)
_register_parser(
    LA_CITY_PRIMEGOV_HTML_PARSER,
    "LA City PrimeGov HTML agendas and committee pages.",
    extract_primegov_html_agenda_items,
)
_register_parser(
    HOMELESSNESS_HOUSING_CLUSTER_PARSER,
    "LA County Homelessness & Housing cluster agenda families, including policy-deputies and agenda-review formats.",
    extract_homelessness_housing_cluster_items,
)
_register_parser(
    LA_COUNTY_BOS_SOP_PARSER,
    "LA County Board of Supervisors Statement of Proceedings extracted text.",
    extract_la_county_bos_sop_items,
)
