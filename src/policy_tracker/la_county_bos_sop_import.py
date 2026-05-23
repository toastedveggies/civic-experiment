from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from policy_tracker.document_context import extract_pdf_text
from policy_tracker.primegov_import import ensure_base_schema, upsert_source
from policy_tracker.runtime_config import load_runtime_config
from policy_tracker.source_loader import get_source_config

DEFAULT_SOURCE_ID = "la_county_bos_sop"


@dataclass(slots=True)
class DownloadedBOSSOPDocument:
    document_id: str
    external_id: str
    sds_doc_id: str
    title: str
    meeting_date: str
    source_url: str
    local_path: str
    text_path: str | None
    sha256: str
    bytes_downloaded: int
    mime_type: str
    document_type: str
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "external_id": self.external_id,
            "sds_doc_id": self.sds_doc_id,
            "title": self.title,
            "meeting_date": self.meeting_date,
            "source_url": self.source_url,
            "local_path": self.local_path,
            "text_path": self.text_path,
            "sha256": self.sha256,
            "bytes_downloaded": self.bytes_downloaded,
            "mime_type": self.mime_type,
            "document_type": self.document_type,
            "status": self.status,
        }


def import_bos_sop_manifest(
    manifest_path: Path,
    source_id: str = DEFAULT_SOURCE_ID,
    config_dir: Path = Path("configs/sources"),
    db_path: Path | None = None,
) -> dict[str, Any]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    source = get_source_config(config_dir, source_id)
    runtime = load_runtime_config()
    database_path = db_path or runtime.database_path
    database_path.parent.mkdir(parents=True, exist_ok=True)

    imported_documents: list[DownloadedBOSSOPDocument] = []
    missing_files: list[str] = []

    with sqlite3.connect(database_path) as connection:
        ensure_base_schema(connection)
        upsert_source(connection, source)

        for item in payload.get("documents", []):
            local_path = Path(str(item.get("local_path", "")))
            if not local_path.exists():
                missing_files.append(str(local_path))
                continue

            imported = prepare_downloaded_document(item, local_path)
            upsert_document_record(connection, source_id=source_id, downloaded=imported)
            imported_documents.append(imported)

        connection.commit()

    import_manifest_path = manifest_path.with_name("bos_sop_import_manifest.json")
    import_manifest_path.write_text(
        json.dumps(
            {
                "source_id": source_id,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "input_manifest_path": str(manifest_path.resolve()),
                "database_path": str(database_path.resolve()),
                "documents_imported": len(imported_documents),
                "missing_files": missing_files,
                "documents": [item.to_dict() for item in imported_documents],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "source_id": source_id,
        "documents_imported": len(imported_documents),
        "missing_files": len(missing_files),
        "database_path": str(database_path.resolve()),
        "import_manifest_path": str(import_manifest_path.resolve()),
    }


def prepare_downloaded_document(item: dict[str, Any], local_path: Path) -> DownloadedBOSSOPDocument:
    binary = local_path.read_bytes()
    sha256 = hashlib.sha256(binary).hexdigest()
    meeting_date = normalize_meeting_date(item)
    extraction = extract_pdf_text(local_path, local_path.parent)
    status = "ready" if extraction.status == "extracted" else extraction.status

    sds_doc_id = str(item.get("sds_doc_id") or "").strip()
    external_id = f"bos_sop:{sds_doc_id or local_path.stem}"
    document_id = build_document_id(external_id)

    return DownloadedBOSSOPDocument(
        document_id=document_id,
        external_id=external_id,
        sds_doc_id=sds_doc_id or local_path.stem,
        title=str(item.get("title") or item.get("sds_title") or local_path.stem),
        meeting_date=meeting_date,
        source_url=str(item.get("source_url") or item.get("sds_published_url") or ""),
        local_path=str(local_path.resolve()),
        text_path=extraction.text_path,
        sha256=sha256,
        bytes_downloaded=len(binary),
        mime_type="application/pdf",
        document_type="statement_of_proceedings",
        status=status,
    )


def normalize_meeting_date(item: dict[str, Any]) -> str:
    raw = str(item.get("meeting_date") or item.get("sds_document_dt") or "").strip()
    if not raw:
        return ""
    raw_date = raw.split(",")[0].strip()
    if "-" in raw_date:
        return raw_date
    parsed = datetime.strptime(raw_date, "%m/%d/%Y")
    return parsed.date().isoformat()


def build_document_id(external_id: str) -> str:
    digest = hashlib.sha1(external_id.encode("utf-8")).hexdigest()[:16]
    return f"doc_{digest}"


def upsert_document_record(
    connection: sqlite3.Connection,
    source_id: str,
    downloaded: DownloadedBOSSOPDocument,
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
            "title": downloaded.title,
            "document_type": downloaded.document_type,
            "meeting_date": downloaded.meeting_date,
            "body_name": "Los Angeles County Board of Supervisors",
            "jurisdiction": "Los Angeles County",
            "file_path": downloaded.local_path,
            "text_path": downloaded.text_path,
            "sha256": downloaded.sha256,
            "mime_type": downloaded.mime_type,
            "collected_at": datetime.now(timezone.utc).isoformat(),
        },
    )
