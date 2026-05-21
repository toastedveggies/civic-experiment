from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import unquote, urlparse

from policy_tracker.models import ExtractedLink, GmailMessage, MessageAssessment, SourceConfig

MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(((?:https?|file)://[^)]+)\)")
SUBJECT_DATE_RE = re.compile(
    r"(?P<month>[A-Za-z]+)\s+(?P<day>\d{1,2}),\s+(?P<year>\d{4})"
)


def assess_message(source: SourceConfig, message: GmailMessage) -> MessageAssessment:
    links = [
        ExtractedLink(
            text=text.strip(),
            original_url=url,
            resolved_url=resolve_govdelivery_url(url),
            category=categorize_url(resolve_govdelivery_url(url)),
        )
        for text, url in MARKDOWN_LINK_RE.findall(message.body)
    ]

    return MessageAssessment(
        source_id=source.source_id,
        message_id=message.message_id,
        message_type=classify_message_type(message.subject),
        subject=message.subject,
        sender=message.from_,
        recipients=message.to,
        meeting_date=extract_meeting_date(message.subject),
        relevant=is_relevant_sender(source, message.from_),
        links=links,
    )


def classify_message_type(subject: str) -> str:
    lowered = subject.lower()
    if "cluster meeting agendas" in lowered:
        return "cluster_meeting_agendas"
    if "supplemental agenda" in lowered:
        return "supplemental_board_agenda"
    if "agenda spotlight" in lowered:
        return "agenda_spotlight"
    if "agenda for the board meeting" in lowered or "agendas for the board meetings" in lowered:
        return "board_agenda"
    return "unknown"


def extract_meeting_date(subject: str) -> str | None:
    match = SUBJECT_DATE_RE.search(subject)
    if not match:
        return None
    dt = datetime.strptime(match.group(0), "%B %d, %Y")
    return dt.date().isoformat()


def is_relevant_sender(source: SourceConfig, sender: str) -> bool:
    sender_lower = sender.lower()
    return any(pattern.lower() in sender_lower for pattern in source.email_sender_patterns)


def resolve_govdelivery_url(url: str) -> str:
    parsed = urlparse(url)
    if "govdelivery.com" not in parsed.netloc:
        return url

    parts = [part for part in parsed.path.split("/") if part]
    for part in parts:
        if part.startswith("https:%2F%2F") or part.startswith("http:%2F%2F"):
            return unquote(part)
    return url


def categorize_url(url: str) -> str:
    parsed = urlparse(url)
    netloc = parsed.netloc.lower()
    path = parsed.path.lower()

    if path.endswith(".pdf"):
        return "direct_pdf"
    if netloc == "bos.lacounty.gov" and "live-broadcast" in path:
        return "live_board_page"
    if netloc == "file.lacounty.gov" and path.endswith(".pdf"):
        return "direct_pdf"
    if netloc == "bos.lacounty.gov" and "board-meeting-agendas" in path:
        return "board_agenda_page"
    if "publiccomment.bos.lacounty.gov" in netloc:
        return "public_comment_page"
    if netloc.endswith("lacounty.gov"):
        return "lacounty_page"
    return "external_page"
