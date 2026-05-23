from __future__ import annotations

import hashlib
import html
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from policy_tracker.document_context import extract_pdf_text
from policy_tracker.runtime_config import load_runtime_config
from policy_tracker.source_loader import get_source_config

PRIMEGOV_API_BASE = "https://lacity.primegov.com"
PRIMEGOV_PORTAL_BASE = "https://portal-lacity.primegov.com"
USER_AGENT = "policy-tracker/0.1"
CITY_COUNCIL_COMMITTEE_ID = 1
HOUSING_HOMELESSNESS_COMMITTEE_ID = 104
TARGET_COMMITTEE_IDS = {CITY_COUNCIL_COMMITTEE_ID, HOUSING_HOMELESSNESS_COMMITTEE_ID}


@dataclass(slots=True)
class DownloadedPrimeGovDocument:
    document_id: str
    external_id: str
    meeting_id: int
    committee_id: int
    meeting_title: str
    meeting_date: str
    template_name: str
    document_type: str
    compile_output_type: int
    source_url: str
    file_path: str
    text_path: str | None
    sha256: str
    bytes_downloaded: int
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "external_id": self.external_id,
            "meeting_id": self.meeting_id,
            "committee_id": self.committee_id,
            "meeting_title": self.meeting_title,
            "meeting_date": self.meeting_date,
            "template_name": self.template_name,
            "document_type": self.document_type,
            "compile_output_type": self.compile_output_type,
            "source_url": self.source_url,
            "file_path": self.file_path,
            "text_path": self.text_path,
            "sha256": self.sha256,
            "bytes_downloaded": self.bytes_downloaded,
            "status": self.status,
        }


def download_la_city_agendas_last_12_months(
    from_date: str,
    to_date: str,
    source_id: str = "la_city_agendas",
    config_dir: Path = Path("configs/sources"),
    db_path: Path | None = None,
    download_root: Path | None = None,
) -> dict[str, Any]:
    source = get_source_config(config_dir, source_id)
    runtime = load_runtime_config()
    target_download_root = download_root or Path(source.download_root or "local/downloads")
    database_path = db_path or runtime.database_path
    database_path.parent.mkdir(parents=True, exist_ok=True)
    target_download_root.mkdir(parents=True, exist_ok=True)

    meetings = fetch_archived_meetings(from_date=from_date, to_date=to_date)
    selected_meetings = select_target_meetings(meetings)
    downloaded_documents: list[DownloadedPrimeGovDocument] = []

    with sqlite3.connect(database_path) as connection:
        ensure_base_schema(connection)
        upsert_source(connection, source)

        for meeting in selected_meetings:
            for document in select_agenda_documents(meeting):
                downloaded = download_meeting_document(document, meeting, target_download_root)
                upsert_document_record(connection, source_id=source_id, downloaded=downloaded)
                downloaded_documents.append(downloaded)

        connection.commit()

    manifest_path = target_download_root / "primegov_last_12_months_manifest.json"
    manifest_payload = {
        "source_id": source_id,
        "from_date": from_date,
        "to_date": to_date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "meetings_considered": len(meetings),
        "meetings_selected": len(selected_meetings),
        "documents_downloaded": len(downloaded_documents),
        "documents": [item.to_dict() for item in downloaded_documents],
    }
    manifest_path.write_text(json.dumps(manifest_payload, indent=2), encoding="utf-8")

    return {
        "source_id": source_id,
        "from_date": from_date,
        "to_date": to_date,
        "meetings_considered": len(meetings),
        "meetings_selected": len(selected_meetings),
        "documents_downloaded": len(downloaded_documents),
        "download_root": str(target_download_root.resolve()),
        "database_path": str(database_path.resolve()),
        "manifest_path": str(manifest_path.resolve()),
        "council_documents": len(
            [item for item in downloaded_documents if item.committee_id == CITY_COUNCIL_COMMITTEE_ID]
        ),
        "housing_homelessness_documents": len(
            [item for item in downloaded_documents if item.committee_id == HOUSING_HOMELESSNESS_COMMITTEE_ID]
        ),
    }


def fetch_archived_meetings(from_date: str, to_date: str) -> list[dict[str, Any]]:
    url = (
        f"{PRIMEGOV_API_BASE}/api/v2/PublicPortal/ListArchivedMeetingsByDate"
        f"?fromDate={from_date}&toDate={to_date}"
    )
    return fetch_json(url)


def fetch_json(url: str) -> list[dict[str, Any]]:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_binary(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request) as response:
        return response.read()


def select_target_meetings(meetings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        meeting
        for meeting in meetings
        if meeting.get("committeeId") in TARGET_COMMITTEE_IDS
        and "sap" not in html.unescape(meeting.get("title", "")).lower()
    ]


def select_agenda_documents(meeting: dict[str, Any]) -> list[dict[str, Any]]:
    selected_by_template: dict[str, dict[str, Any]] = {}
    for document in meeting.get("documentList", []):
        template_name = html.unescape(document.get("templateName", "")).strip()
        if not is_agenda_template(template_name):
            continue

        key = template_name.lower()
        current = selected_by_template.get(key)
        if current is None:
            selected_by_template[key] = document
            continue

        if prefer_document(document, current):
            selected_by_template[key] = document
    return list(selected_by_template.values())


def is_agenda_template(template_name: str) -> bool:
    lowered = template_name.lower()
    if "agenda" in lowered:
        return True
    return "notice of cancellation" in lowered


def prefer_document(candidate: dict[str, Any], current: dict[str, Any]) -> bool:
    candidate_type = candidate.get("compileOutputType")
    current_type = current.get("compileOutputType")
    if candidate_type == 1 and current_type != 1:
        return True
    if candidate_type == 3 and current_type != 3:
        return False
    return int(candidate.get("id", 0)) > int(current.get("id", 0))


def download_meeting_document(
    document: dict[str, Any],
    meeting: dict[str, Any],
    download_root: Path,
) -> DownloadedPrimeGovDocument:
    meeting_title = html.unescape(meeting.get("title", "")).strip()
    meeting_date = str(meeting.get("dateTime", "")).split("T")[0]
    document_url = build_document_url(document)
    suffix = ".pdf" if document.get("compileOutputType") == 1 else ".html"
    meeting_dir = download_root / "primegov" / meeting_date / slugify(meeting_title)
    meeting_dir.mkdir(parents=True, exist_ok=True)

    template_name = html.unescape(document.get("templateName", "")).strip()
    filename = f"{meeting_date}_{slugify(meeting_title)}_{slugify(template_name)}{suffix}"
    file_path = meeting_dir / filename

    binary = fetch_binary(document_url)
    file_path.write_bytes(binary)

    sha256 = hashlib.sha256(binary).hexdigest()
    text_path: str | None = None
    status = "downloaded"

    if suffix == ".pdf":
        extraction = extract_pdf_text(file_path, meeting_dir)
        text_path = extraction.text_path
        status = "ready" if extraction.status == "extracted" else extraction.status
    elif suffix == ".html":
        text_target = meeting_dir / f"{file_path.stem}.txt"
        html_text = file_path.read_text(encoding="utf-8", errors="ignore")
        text_target.write_text(html_text, encoding="utf-8")
        text_path = str(text_target.resolve())
        status = "ready"

    external_id = build_external_id(meeting, document)
    document_id = build_document_id(external_id)
    return DownloadedPrimeGovDocument(
        document_id=document_id,
        external_id=external_id,
        meeting_id=int(meeting["id"]),
        committee_id=int(meeting["committeeId"]),
        meeting_title=meeting_title,
        meeting_date=meeting_date,
        template_name=template_name,
        document_type=normalize_document_type(template_name),
        compile_output_type=int(document["compileOutputType"]),
        source_url=document_url,
        file_path=str(file_path.resolve()),
        text_path=text_path,
        sha256=sha256,
        bytes_downloaded=len(binary),
        status=status,
    )


def build_document_url(document: dict[str, Any]) -> str:
    if document.get("link"):
        return str(document["link"])

    compile_output_type = int(document["compileOutputType"])
    template_id = int(document.get("templateId") or 0)
    if compile_output_type == 3:
        if template_id > 0:
            return (
                f"{PRIMEGOV_API_BASE}/Portal/Meeting?meetingTemplateId={template_id}"
                "&parentLink=newPublicPortal"
            )
        return (
            f"{PRIMEGOV_API_BASE}/Portal/Meeting?compiledMeetingDocumentFileId={int(document['id'])}"
            "&parentLink=newPublicPortal"
        )

    if template_id > 0:
        return (
            f"{PRIMEGOV_API_BASE}/Public/CompiledDocument?meetingTemplateId={template_id}"
            f"&compileOutputType={compile_output_type}"
        )
    return (
        f"{PRIMEGOV_API_BASE}/Public/CompiledDocument?compiledMeetingDocumentFileId={int(document['id'])}"
        f"&compileOutputType={compile_output_type}"
    )


def build_external_id(meeting: dict[str, Any], document: dict[str, Any]) -> str:
    return (
        f"primegov:{meeting['committeeId']}:{meeting['id']}:"
        f"{document.get('templateId') or document['id']}:{document['compileOutputType']}"
    )


def build_document_id(external_id: str) -> str:
    digest = hashlib.sha1(external_id.encode("utf-8")).hexdigest()[:16]
    return f"doc_{digest}"


def normalize_document_type(template_name: str) -> str:
    lowered = template_name.lower().strip()
    lowered = lowered.replace("&", "and")
    pieces = [piece for piece in slugify(lowered).split("-") if piece]
    return "_".join(pieces) or "agenda_document"


def slugify(value: str) -> str:
    safe_chars = []
    for char in value.lower():
        if char.isalnum():
            safe_chars.append(char)
        else:
            safe_chars.append("-")
    slug = "".join(safe_chars)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "document"


def ensure_base_schema(connection: sqlite3.Connection) -> None:
    schema_path = Path(__file__).resolve().parents[2] / "sql" / "schema_v1.sql"
    connection.executescript(schema_path.read_text(encoding="utf-8"))


def upsert_source(connection: sqlite3.Connection, source: Any) -> None:
    connection.execute(
        """
        INSERT INTO sources (
            source_id, source_name, jurisdiction, government_level, body_name,
            source_type, collection_method, base_url, meeting_frequency,
            priority_level, status, adapter, parser, notes
        ) VALUES (
            :source_id, :source_name, :jurisdiction, :government_level, :body_name,
            :source_type, :collection_method, :base_url, :meeting_frequency,
            :priority_level, :status, :adapter, :parser, :notes
        )
        ON CONFLICT(source_id) DO UPDATE SET
            source_name = excluded.source_name,
            jurisdiction = excluded.jurisdiction,
            government_level = excluded.government_level,
            body_name = excluded.body_name,
            source_type = excluded.source_type,
            collection_method = excluded.collection_method,
            base_url = excluded.base_url,
            meeting_frequency = excluded.meeting_frequency,
            priority_level = excluded.priority_level,
            status = excluded.status,
            adapter = excluded.adapter,
            parser = excluded.parser,
            notes = excluded.notes,
            updated_at = CURRENT_TIMESTAMP
        """,
        {
            "source_id": source.source_id,
            "source_name": source.source_name,
            "jurisdiction": source.jurisdiction,
            "government_level": source.government_level,
            "body_name": source.body_name,
            "source_type": source.source_type,
            "collection_method": source.collection_method,
            "base_url": source.base_url,
            "meeting_frequency": source.meeting_frequency,
            "priority_level": source.priority_level,
            "status": source.status,
            "adapter": source.adapter,
            "parser": source.parser,
            "notes": source.notes,
        },
    )


def upsert_document_record(
    connection: sqlite3.Connection,
    source_id: str,
    downloaded: DownloadedPrimeGovDocument,
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
            "document_id": downloaded.document_id,
            "source_id": source_id,
            "external_id": downloaded.external_id,
            "title": f"{downloaded.meeting_title} - {downloaded.template_name}",
            "document_type": downloaded.document_type,
            "meeting_date": downloaded.meeting_date,
            "body_name": downloaded.meeting_title,
            "jurisdiction": "Los Angeles",
            "file_path": downloaded.file_path,
            "text_path": downloaded.text_path,
            "sha256": downloaded.sha256,
            "mime_type": "application/pdf" if downloaded.compile_output_type == 1 else "text/html",
            "collected_at": datetime.now(timezone.utc).isoformat(),
        },
    )
