from __future__ import annotations

import html
import re
from datetime import datetime

from policy_tracker.item_extraction import html_fragment_to_text
from policy_tracker.models import (
    ExtractedLink,
    GmailAttachment,
    GmailMessage,
    MessageAssessment,
    SourceConfig,
)

PRIMEGOV_URL_RE = re.compile(
    r"https://(?:lacity|portal-lacity)\.primegov\.com/Portal/Meeting\?meetingTemplateId=(\d+)",
    re.IGNORECASE,
)
SUBJECT_PREFIX_RE = re.compile(
    r"^(?P<date>\d{1,2}/\d{1,2}/\d{4})\s+(?P<time>\d{1,2}:\d{2}\s*[AP]M)\s+-\s+",
    re.IGNORECASE,
)
TAG_RE = re.compile(r"<[^>]+>")


def assess_message(source: SourceConfig, message: GmailMessage) -> MessageAssessment:
    attachment_notices = [
        parse_notice_attachment(message.subject, attachment)
        for attachment in message.attachments
        if looks_like_html_notice(attachment)
    ]
    attachment_notices = [notice for notice in attachment_notices if notice is not None]

    links = build_primegov_links(attachment_notices)
    meeting_date = select_meeting_date(message.subject, attachment_notices)

    return MessageAssessment(
        source_id=source.source_id,
        message_id=message.message_id,
        message_type=classify_message_type(message.subject),
        subject=message.subject,
        sender=message.from_,
        recipients=message.to,
        meeting_date=meeting_date,
        relevant=is_relevant_sender(source, message.from_),
        links=links,
        metadata={"attachment_notices": attachment_notices},
    )


def looks_like_html_notice(attachment: GmailAttachment) -> bool:
    lowered_name = attachment.filename.lower()
    lowered_type = (attachment.mime_type or "").lower()
    return lowered_name.endswith((".htm", ".html")) or lowered_type == "text/html"


def parse_notice_attachment(subject: str, attachment: GmailAttachment) -> dict[str, str | bool | None] | None:
    attachment_text = attachment.content or ""
    if not attachment_text.strip():
        return None

    text = clean_notice_text(attachment_text)
    primegov_match = PRIMEGOV_URL_RE.search(attachment_text)
    subject_body_name = extract_body_name_from_subject(subject)

    return {
        "filename": attachment.filename,
        "mime_type": attachment.mime_type,
        "body_name": detect_body_name(text, subject_body_name),
        "meeting_date": extract_subject_date(subject),
        "meeting_time": extract_subject_time(subject),
        "meeting_datetime": extract_subject_datetime(subject),
        "is_cancellation": "cancelled" in subject.lower() or "notice of cancellation" in text.lower(),
        "primegov_url": primegov_match.group(0) if primegov_match else None,
        "primegov_meeting_template_id": primegov_match.group(1) if primegov_match else None,
        "text_excerpt": text[:400],
    }


def build_primegov_links(notices: list[dict[str, str | bool | None]]) -> list[ExtractedLink]:
    seen_urls: set[str] = set()
    links: list[ExtractedLink] = []
    for notice in notices:
        primegov_url = notice.get("primegov_url")
        if not isinstance(primegov_url, str) or not primegov_url or primegov_url in seen_urls:
            continue
        seen_urls.add(primegov_url)
        body_name = str(notice.get("body_name") or "LA City agenda")
        links.append(
            ExtractedLink(
                text=body_name,
                original_url=primegov_url,
                resolved_url=primegov_url,
                category="primegov_meeting_page",
            )
        )
    return links


def classify_message_type(subject: str) -> str:
    lowered = subject.lower()
    if "cancelled" in lowered:
        return "meeting_cancellation_notice"
    if "agenda" in lowered:
        return "agenda_notice"
    return "unknown"


def is_relevant_sender(source: SourceConfig, sender: str) -> bool:
    sender_lower = sender.lower()
    return any(pattern.lower() in sender_lower for pattern in source.email_sender_patterns)


def select_meeting_date(subject: str, notices: list[dict[str, str | bool | None]]) -> str | None:
    subject_date = extract_subject_date(subject)
    if subject_date:
        return subject_date
    for notice in notices:
        meeting_date = notice.get("meeting_date")
        if isinstance(meeting_date, str) and meeting_date:
            return meeting_date
    return None


def extract_subject_date(subject: str) -> str | None:
    match = SUBJECT_PREFIX_RE.match(subject)
    if not match:
        return None
    dt = datetime.strptime(match.group("date"), "%m/%d/%Y")
    return dt.date().isoformat()


def extract_subject_time(subject: str) -> str | None:
    match = SUBJECT_PREFIX_RE.match(subject)
    if not match:
        return None
    return match.group("time").upper().replace("  ", " ")


def extract_subject_datetime(subject: str) -> str | None:
    match = SUBJECT_PREFIX_RE.match(subject)
    if not match:
        return None
    dt = datetime.strptime(
        f"{match.group('date')} {match.group('time').upper().replace(' ', '')}",
        "%m/%d/%Y %I:%M%p",
    )
    return dt.isoformat()


def extract_body_name_from_subject(subject: str) -> str | None:
    normalized = SUBJECT_PREFIX_RE.sub("", subject).strip()
    normalized = normalized.replace(" - CANCELLED - ", " ")
    normalized = normalized.replace(" - CANCELED - ", " ")
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = re.sub(r"\bAgenda\b", "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\bMeeting\b", "", normalized, flags=re.IGNORECASE)
    normalized = normalized.strip(" -")
    return normalized or None


def clean_notice_text(value: str) -> str:
    if "<" in value and ">" in value:
        return html_fragment_to_text(value)
    value = html.unescape(value)
    value = TAG_RE.sub(" ", value)
    return re.sub(r"\s+", " ", value).strip()


def detect_body_name(text: str, fallback: str | None) -> str | None:
    upper_lines = [
        line.strip(" -")
        for line in text.splitlines()
        if line.strip() and any(char.isalpha() for char in line) and line.upper() == line
    ]
    for line in upper_lines:
        lowered = line.lower()
        if "city council" in lowered or "committee" in lowered:
            return line.title().replace("La", "LA")
    return fallback
