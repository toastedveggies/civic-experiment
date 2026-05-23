from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from policy_tracker.document_context import extract_pdf_text
from policy_tracker.primegov_import import ensure_base_schema, upsert_source
from policy_tracker.runtime_config import load_runtime_config
from policy_tracker.source_loader import get_source_config

WAYBACK_CDX_URL = "https://web.archive.org/cdx/search/cdx"
WAYBACK_SNAPSHOT_URL = "https://web.archive.org/web/{timestamp}id_/https://bos.lacounty.gov/board-meeting-agendas/"
USER_AGENT = "policy-tracker/0.1"
DEFAULT_SOURCE_ID = "la_county_board_agendas"

CARD_SPLIT_RE = re.compile(r'<div data-cms-item-id="[^"]+" class="card upcoming-meeting">', re.IGNORECASE)
TITLE_RE = re.compile(r'<h4[^>]*class="card-title">([^<]+)</h4>', re.IGNORECASE)
TIME_RE = re.compile(r'data-cms-element-codename="date_and_time">([^<]+)</time>', re.IGNORECASE)
LINK_PAIR_RE = re.compile(
    r'<a[^>]+href="(?P<html>https://assets-us-01\.kc-usercontent\.com[^"]+\.htm[^"]*)"[^>]*>'
    r'.*?<span>(?P<label>Agenda|Supplemental)</span>.*?</a>\s*'
    r'<a[^>]+href="(?P<pdf>https://assets-us-01\.kc-usercontent\.com[^"]+\.pdf[^"]*)"[^>]*>'
    r'.*?<span>PDF</span>.*?</a>',
    re.IGNORECASE | re.DOTALL,
)


@dataclass(slots=True)
class BOSAgendaDocument:
    meeting_date: str
    meeting_name: str
    agenda_label: str
    url: str
    file_path: str
    text_path: str | None
    sha256: str
    bytes_downloaded: int
    mime_type: str
    document_type: str
    external_id: str
    document_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "meeting_date": self.meeting_date,
            "meeting_name": self.meeting_name,
            "agenda_label": self.agenda_label,
            "url": self.url,
            "file_path": self.file_path,
            "text_path": self.text_path,
            "sha256": self.sha256,
            "bytes_downloaded": self.bytes_downloaded,
            "mime_type": self.mime_type,
            "document_type": self.document_type,
            "external_id": self.external_id,
            "document_id": self.document_id,
        }


def download_bos_agendas_last_year(
    from_date: date,
    to_date: date,
    source_id: str = DEFAULT_SOURCE_ID,
    config_dir: Path = Path("configs/sources"),
    db_path: Path | None = None,
    download_root: Path | None = None,
) -> dict[str, Any]:
    source = get_source_config(config_dir, source_id)
    runtime = load_runtime_config()
    target_download_root = download_root or Path(source.download_root or "local/downloads/la_county_board_agendas")
    database_path = db_path or runtime.database_path
    target_download_root.mkdir(parents=True, exist_ok=True)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    timestamps = fetch_wayback_timestamps(from_date, to_date)
    meeting_links = collect_links_from_snapshots(timestamps, from_date, to_date)

    downloaded: list[BOSAgendaDocument] = []
    with sqlite3.connect(database_path) as connection:
        ensure_base_schema(connection)
        upsert_source(connection, source)
        for meeting_date_text, meeting_name, agenda_label, url in meeting_links:
            try:
                document = download_agenda_document(
                    meeting_date_text=meeting_date_text,
                    meeting_name=meeting_name,
                    agenda_label=agenda_label,
                    url=url,
                    download_root=target_download_root,
                )
            except URLError:
                continue
            upsert_document_record(connection, source_id, document)
            downloaded.append(document)
        connection.commit()

    manifest_path = target_download_root / "bos_last_12_months_manifest.json"
    manifest = {
        "source_id": source_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "wayback_snapshots_used": len(timestamps),
        "documents_downloaded": len(downloaded),
        "by_meeting_date": summarize_by_meeting_date(downloaded),
        "documents": [item.to_dict() for item in downloaded],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {
        "source_id": source_id,
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "wayback_snapshots_used": len(timestamps),
        "documents_downloaded": len(downloaded),
        "download_root": str(target_download_root.resolve()),
        "database_path": str(database_path.resolve()),
        "manifest_path": str(manifest_path.resolve()),
        "by_meeting_date": summarize_by_meeting_date(downloaded),
    }


def fetch_wayback_timestamps(from_date: date, to_date: date) -> list[str]:
    query = (
        f"{WAYBACK_CDX_URL}?url=https://bos.lacounty.gov/board-meeting-agendas/"
        f"&from={from_date:%Y%m}&to={to_date:%Y%m}&output=json"
        "&fl=timestamp&filter=statuscode:200"
    )
    payload = json.loads(fetch_text(query))
    timestamps = [row[0] for row in payload[1:]]
    return reduce_snapshot_volume(timestamps)


def reduce_snapshot_volume(timestamps: list[str]) -> list[str]:
    selected: list[str] = []
    last_kept: date | None = None
    for timestamp in timestamps:
        current = datetime.strptime(timestamp[:8], "%Y%m%d").date()
        if last_kept is None or current >= last_kept + timedelta(days=6):
            selected.append(timestamp)
            last_kept = current
    return selected


def collect_links_from_snapshots(
    timestamps: list[str], from_date: date, to_date: date
) -> list[tuple[str, str, str, str]]:
    collected: dict[str, tuple[str, str, str, str]] = {}
    for timestamp in timestamps:
        try:
            html_text = fetch_text(WAYBACK_SNAPSHOT_URL.format(timestamp=timestamp))
        except URLError:
            continue
        for meeting_date_text, meeting_name, agenda_label, url in parse_snapshot_links(html_text):
            meeting_date = datetime.strptime(meeting_date_text, "%Y-%m-%d").date()
            if not (from_date <= meeting_date <= to_date):
                continue
            collected.setdefault(url, (meeting_date_text, meeting_name, agenda_label, url))
    return sorted(collected.values(), key=lambda item: (item[0], item[1], item[2], item[3]))


def parse_snapshot_links(html_text: str) -> list[tuple[str, str, str, str]]:
    cards = CARD_SPLIT_RE.split(html_text)[1:]
    links: list[tuple[str, str, str, str]] = []
    for card in cards:
        title_match = TITLE_RE.search(card)
        time_matches = TIME_RE.findall(card)
        if not title_match or not time_matches:
            continue
        meeting_name = clean_text(title_match.group(1))
        meeting_date = datetime.strptime(clean_text(time_matches[0]), "%A, %B %d, %Y").date().isoformat()
        for pair in LINK_PAIR_RE.finditer(card):
            agenda_label = clean_text(pair.group("label"))
            links.append((meeting_date, meeting_name, agenda_label, pair.group("html")))
            links.append((meeting_date, meeting_name, f"{agenda_label} PDF", pair.group("pdf")))
    return links


def download_agenda_document(
    meeting_date_text: str,
    meeting_name: str,
    agenda_label: str,
    url: str,
    download_root: Path,
) -> BOSAgendaDocument:
    meeting_dir = download_root / "bos" / meeting_date_text / slugify(meeting_name)
    meeting_dir.mkdir(parents=True, exist_ok=True)
    suffix = ".html" if url.lower().endswith((".htm", ".html")) else ".pdf"
    filename = f"{meeting_date_text}_{slugify(meeting_name)}_{slugify(agenda_label)}{suffix}"
    file_path = meeting_dir / filename
    binary = fetch_binary(url)
    file_path.write_bytes(binary)

    text_path: str | None = None
    mime_type = "text/html" if suffix == ".html" else "application/pdf"
    document_type = "bos_agenda_html" if suffix == ".html" else "bos_agenda_pdf"
    if suffix == ".html":
        text_target = meeting_dir / f"{file_path.stem}.txt"
        text_target.write_text(binary.decode("utf-8", errors="ignore"), encoding="utf-8")
        text_path = str(text_target.resolve())
    else:
        extraction = extract_pdf_text(file_path, meeting_dir)
        text_path = extraction.text_path

    external_id = url
    return BOSAgendaDocument(
        meeting_date=meeting_date_text,
        meeting_name=meeting_name,
        agenda_label=agenda_label,
        url=url,
        file_path=str(file_path.resolve()),
        text_path=text_path,
        sha256=hashlib.sha256(binary).hexdigest(),
        bytes_downloaded=len(binary),
        mime_type=mime_type,
        document_type=document_type,
        external_id=external_id,
        document_id=build_document_id(external_id),
    )


def upsert_document_record(connection: sqlite3.Connection, source_id: str, document: BOSAgendaDocument) -> None:
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
            "document_id": document.document_id,
            "source_id": source_id,
            "external_id": document.external_id,
            "title": f"{document.meeting_name} - {document.agenda_label}",
            "document_type": document.document_type,
            "meeting_date": document.meeting_date,
            "body_name": "Los Angeles County Board of Supervisors",
            "jurisdiction": "Los Angeles County",
            "file_path": document.file_path,
            "text_path": document.text_path,
            "sha256": document.sha256,
            "mime_type": document.mime_type,
            "collected_at": datetime.now(timezone.utc).isoformat(),
        },
    )


def fetch_text(url: str) -> str:
    last_error: URLError | None = None
    for attempt in range(3):
        request = Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urlopen(request) as response:
                return response.read().decode("utf-8", errors="ignore")
        except URLError as exc:
            last_error = exc
            time.sleep(1 + attempt)
    if last_error is not None:
        raise last_error
    raise URLError("Unknown fetch failure")


def fetch_binary(url: str) -> bytes:
    last_error: URLError | None = None
    for attempt in range(3):
        request = Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urlopen(request) as response:
                return response.read()
        except URLError as exc:
            last_error = exc
            time.sleep(1 + attempt)
    if last_error is not None:
        raise last_error
    raise URLError("Unknown fetch failure")


def clean_text(value: str) -> str:
    return " ".join(value.replace("&nbsp;", " ").split())


def build_document_id(external_id: str) -> str:
    return f"doc_{hashlib.sha1(external_id.encode('utf-8')).hexdigest()[:16]}"


def slugify(value: str) -> str:
    chars = [char if char.isalnum() else "-" for char in value.lower()]
    slug = "".join(chars)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "agenda"


def summarize_by_meeting_date(documents: list[BOSAgendaDocument]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in documents:
        counts[item.meeting_date] = counts.get(item.meeting_date, 0) + 1
    return dict(sorted(counts.items()))
