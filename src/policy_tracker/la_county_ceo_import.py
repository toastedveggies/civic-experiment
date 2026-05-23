from __future__ import annotations

import hashlib
import html
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from policy_tracker.document_context import extract_pdf_text
from policy_tracker.primegov_import import ensure_base_schema, upsert_source
from policy_tracker.runtime_config import load_runtime_config
from policy_tracker.source_loader import get_source_config

CEO_AGENDAS_URL = "https://ceo.lacounty.gov/agendas/"
USER_AGENT = "policy-tracker/0.1"
DEFAULT_SOURCE_ID = "la_county_ceo_agendas"

REQUESTED_BODY_NAME_MAP = {
    "Community Services Cluster": "Community Services Cluster",
    "Operations Cluster": "Operations Cluster",
    "Family and Social Services Cluster": "Family and Social Services Cluster",
    "Health and Mental Health Services Cluster": "Health and Mental Health Services Cluster",
    "Public Safety Cluster": "Public Safety Cluster",
    "Homelessness and Housing Cluster": "Homelessness and Housing Cluster",
    "Affordable Housing": "Affordable Housing",
    "Community Care and Justice": "Community Care & Justice",
    "Executive Committee for Regional Homeless Alignment": "Executive Committee for Regional Homeless Alignment",
    "LACTA Board Deputies": "LACDA Board Deputies",
    "Leadership Table for Regional Homeless Alignment": "Leadership Table for Regional Homeless Alignment",
    "Real Estate Management Commission": "Real Estate Management Commission",
}

DATE_PREFIX_RE = re.compile(
    r"(?P<month>January|February|March|April|May|June|July|August|September|October|November|December)\s+"
    r"(?P<day>\d{1,2}),\s+(?P<year>\d{4})",
    re.IGNORECASE,
)
H4_RE = re.compile(r"<h4[^>]*>(.*?)</h4>", re.IGNORECASE | re.DOTALL)
ANCHOR_RE = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)


@dataclass(slots=True)
class CEOAgendaLink:
    requested_name: str
    body_name: str
    label: str
    agenda_date: date
    url: str

    def to_dict(self) -> dict[str, str]:
        return {
            "requested_name": self.requested_name,
            "body_name": self.body_name,
            "label": self.label,
            "agenda_date": self.agenda_date.isoformat(),
            "url": self.url,
        }


@dataclass(slots=True)
class DownloadedCEOAgenda:
    requested_name: str
    body_name: str
    label: str
    agenda_date: str
    url: str
    file_path: str
    text_path: str | None
    sha256: str
    bytes_downloaded: int
    status: str
    document_id: str
    external_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "requested_name": self.requested_name,
            "body_name": self.body_name,
            "label": self.label,
            "agenda_date": self.agenda_date,
            "url": self.url,
            "file_path": self.file_path,
            "text_path": self.text_path,
            "sha256": self.sha256,
            "bytes_downloaded": self.bytes_downloaded,
            "status": self.status,
            "document_id": self.document_id,
            "external_id": self.external_id,
        }


def download_county_ceo_agendas(
    requested_bodies: list[str],
    from_date: date,
    to_date: date,
    source_id: str = DEFAULT_SOURCE_ID,
    config_dir: Path = Path("configs/sources"),
    db_path: Path | None = None,
    download_root: Path | None = None,
) -> dict[str, Any]:
    source = get_source_config(config_dir, source_id)
    runtime = load_runtime_config()
    target_download_root = download_root or Path(source.download_root or "local/downloads")
    database_path = db_path or runtime.database_path
    target_download_root.mkdir(parents=True, exist_ok=True)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    html_text = fetch_text(CEO_AGENDAS_URL)
    sections = parse_ceo_agenda_sections(html_text)
    selected_links = select_requested_links(
        sections=sections,
        requested_bodies=requested_bodies,
        from_date=from_date,
        to_date=to_date,
    )

    downloaded: list[DownloadedCEOAgenda] = []
    with sqlite3.connect(database_path) as connection:
        ensure_base_schema(connection)
        upsert_source(connection, source)
        for link in selected_links:
            agenda = download_agenda(link, target_download_root)
            upsert_document_record(connection, source_id, agenda)
            downloaded.append(agenda)
        connection.commit()

    manifest_path = target_download_root / "ceo_last_12_months_manifest.json"
    manifest_payload = {
        "source_id": source_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "requested_bodies": requested_bodies,
        "site_body_name_map": {name: REQUESTED_BODY_NAME_MAP.get(name, name) for name in requested_bodies},
        "agendas_downloaded": len(downloaded),
        "by_body": summarize_by_body(downloaded),
        "documents": [agenda.to_dict() for agenda in downloaded],
    }
    manifest_path.write_text(json.dumps(manifest_payload, indent=2), encoding="utf-8")
    return {
        "source_id": source_id,
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "requested_bodies": requested_bodies,
        "agendas_downloaded": len(downloaded),
        "by_body": summarize_by_body(downloaded),
        "download_root": str(target_download_root.resolve()),
        "database_path": str(database_path.resolve()),
        "manifest_path": str(manifest_path.resolve()),
    }


def fetch_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request) as response:
        return response.read().decode("utf-8", errors="ignore")


def fetch_binary(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request) as response:
        return response.read()


def parse_ceo_agenda_sections(html_text: str) -> dict[str, list[CEOAgendaLink]]:
    headings = list(H4_RE.finditer(html_text))
    sections: dict[str, list[CEOAgendaLink]] = {}
    for index, match in enumerate(headings):
        body_name = clean_html_fragment(match.group(1))
        start = match.end()
        end = headings[index + 1].start() if index + 1 < len(headings) else len(html_text)
        block = html_text[start:end]
        links: list[CEOAgendaLink] = []
        for href, raw_label in ANCHOR_RE.findall(block):
            label = clean_html_fragment(raw_label)
            agenda_date = parse_label_date(label)
            if agenda_date is None or not href.lower().endswith(".pdf"):
                continue
            links.append(
                CEOAgendaLink(
                    requested_name=body_name,
                    body_name=body_name,
                    label=label,
                    agenda_date=agenda_date,
                    url=href,
                )
            )
        if links:
            sections[body_name] = links
    return sections


def select_requested_links(
    sections: dict[str, list[CEOAgendaLink]],
    requested_bodies: list[str],
    from_date: date,
    to_date: date,
) -> list[CEOAgendaLink]:
    selected: list[CEOAgendaLink] = []
    seen_urls: set[str] = set()
    for requested_name in requested_bodies:
        site_name = REQUESTED_BODY_NAME_MAP.get(requested_name, requested_name)
        for link in sections.get(site_name, []):
            if not (from_date <= link.agenda_date <= to_date):
                continue
            if link.url in seen_urls:
                continue
            seen_urls.add(link.url)
            selected.append(
                CEOAgendaLink(
                    requested_name=requested_name,
                    body_name=link.body_name,
                    label=link.label,
                    agenda_date=link.agenda_date,
                    url=link.url,
                )
            )
    selected.sort(key=lambda item: (item.agenda_date, item.body_name, item.label))
    return selected


def download_agenda(link: CEOAgendaLink, download_root: Path) -> DownloadedCEOAgenda:
    meeting_dir = download_root / "ceo" / link.agenda_date.isoformat() / slugify(link.body_name)
    meeting_dir.mkdir(parents=True, exist_ok=True)
    file_name = f"{link.agenda_date.isoformat()}_{slugify(link.body_name)}_{slugify(link.label)}.pdf"
    file_path = meeting_dir / file_name
    binary = fetch_binary(link.url)
    file_path.write_bytes(binary)
    extraction = extract_pdf_text(file_path, meeting_dir)
    external_id = link.url
    document_id = build_document_id(external_id)
    return DownloadedCEOAgenda(
        requested_name=link.requested_name,
        body_name=link.body_name,
        label=link.label,
        agenda_date=link.agenda_date.isoformat(),
        url=link.url,
        file_path=str(file_path.resolve()),
        text_path=extraction.text_path,
        sha256=hashlib.sha256(binary).hexdigest(),
        bytes_downloaded=len(binary),
        status=extraction.status if extraction.status != "not_applicable" else "downloaded",
        document_id=document_id,
        external_id=external_id,
    )


def upsert_document_record(
    connection: sqlite3.Connection,
    source_id: str,
    agenda: DownloadedCEOAgenda,
) -> None:
    connection.execute(
        """
        INSERT INTO documents (
            document_id, source_id, external_id, title, document_type, meeting_date,
            body_name, jurisdiction, file_path, text_path, sha256, mime_type, collected_at
        ) VALUES (
            :document_id, :source_id, :external_id, :title, :document_type, :meeting_date,
            :body_name, :jurisdiction, :file_path, :text_path, :sha256, :mime_type, :collected_at
        )
        ON CONFLICT(document_id) DO UPDATE SET
            source_id = excluded.source_id,
            external_id = excluded.external_id,
            title = excluded.title,
            document_type = excluded.document_type,
            meeting_date = excluded.meeting_date,
            body_name = excluded.body_name,
            jurisdiction = excluded.jurisdiction,
            file_path = excluded.file_path,
            text_path = excluded.text_path,
            sha256 = excluded.sha256,
            mime_type = excluded.mime_type,
            collected_at = excluded.collected_at,
            updated_at = CURRENT_TIMESTAMP
        """,
        {
            "document_id": agenda.document_id,
            "source_id": source_id,
            "external_id": agenda.external_id,
            "title": f"{agenda.body_name} - {agenda.label}",
            "document_type": "ceo_agenda_pdf",
            "meeting_date": agenda.agenda_date,
            "body_name": agenda.body_name,
            "jurisdiction": "Los Angeles County",
            "file_path": agenda.file_path,
            "text_path": agenda.text_path,
            "sha256": agenda.sha256,
            "mime_type": "application/pdf",
            "collected_at": datetime.now(timezone.utc).isoformat(),
        },
    )


def parse_label_date(label: str) -> date | None:
    match = DATE_PREFIX_RE.search(label)
    if not match:
        return None
    return datetime.strptime(match.group(0), "%B %d, %Y").date()


def clean_html_fragment(value: str) -> str:
    stripped = re.sub(r"<[^>]+>", " ", value)
    return " ".join(html.unescape(stripped).split())


def build_document_id(external_id: str) -> str:
    return f"doc_{hashlib.sha1(external_id.encode('utf-8')).hexdigest()[:16]}"


def slugify(value: str) -> str:
    chars = []
    for char in value.lower():
        chars.append(char if char.isalnum() else "-")
    slug = "".join(chars)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "agenda"


def summarize_by_body(downloaded: list[DownloadedCEOAgenda]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for agenda in downloaded:
        counts[agenda.requested_name] = counts.get(agenda.requested_name, 0) + 1
    return dict(sorted(counts.items()))
