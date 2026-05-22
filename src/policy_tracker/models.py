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
        )


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

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["links"] = [link.to_dict() for link in self.links]
        return data
