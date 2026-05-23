from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class SourceConfig:
    source_id: str
    source_name: str
    jurisdiction: str
    government_level: str
    body_name: str
    source_type: str
    collection_method: str
    priority_level: str
    status: str
    base_url: str | None = None
    meeting_frequency: str | None = None
    email_sender_patterns: list[str] = field(default_factory=list)
    attachment_patterns: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    notes: str | None = None
    adapter: str | None = None
    parser: str | None = None
    gmail_query: str | None = None
    download_root: str | None = None
    structured_output_dir: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class GmailMessage:
    message_id: str
    from_: str
    to: list[str]
    subject: str
    body: str
    email_ts: str | None = None
    snippet: str | None = None
    labels: list[str] = field(default_factory=list)
    attachments: list["GmailAttachment"] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "GmailMessage":
        return cls(
            message_id=payload["id"],
            from_=payload["from_"],
            to=list(payload.get("to", [])),
            subject=payload["subject"],
            body=payload.get("body", ""),
            email_ts=payload.get("email_ts"),
            snippet=payload.get("snippet"),
            labels=list(payload.get("labels", [])),
            attachments=[
                GmailAttachment.from_dict(attachment)
                for attachment in payload.get("attachments", [])
                if isinstance(attachment, dict)
            ],
        )


@dataclass(slots=True)
class GmailAttachment:
    filename: str
    mime_type: str | None = None
    content: str | None = None
    attachment_id: str | None = None
    path: str | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "GmailAttachment":
        return cls(
            filename=str(payload.get("filename") or payload.get("name") or "attachment"),
            mime_type=payload.get("mime_type") or payload.get("mimeType"),
            content=_first_text_value(payload, "content", "body", "text", "content_text"),
            attachment_id=payload.get("attachment_id") or payload.get("attachmentId"),
            path=payload.get("path") or payload.get("file_path"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _first_text_value(payload: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


@dataclass(slots=True)
class ExtractedLink:
    text: str
    original_url: str
    resolved_url: str
    category: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(slots=True)
class MessageAssessment:
    source_id: str
    message_id: str
    message_type: str
    subject: str
    sender: str
    recipients: list[str]
    meeting_date: str | None
    relevant: bool
    links: list[ExtractedLink]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["links"] = [link.to_dict() for link in self.links]
        return data
