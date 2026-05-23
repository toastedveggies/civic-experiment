from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from policy_tracker.adapters.la_city_gmail import assess_message
from policy_tracker.document_context import sanitize_filename
from policy_tracker.item_extraction import LA_CITY_PRIMEGOV_HTML_PARSER
from policy_tracker.models import GmailMessage
from policy_tracker.primegov_import import ensure_base_schema, fetch_binary, slugify, upsert_source
from policy_tracker.runtime_config import load_runtime_config
from policy_tracker.source_loader import get_source_config
from policy_tracker.sqlite_import import import_items_index
from policy_tracker.storage import (
    build_items_index,
    materialize_structured_document,
    write_items_index,
    write_structured_document,
)


def ingest_la_city_gmail_message_file(
    message_path: Path,
    config_dir: Path = Path("configs/sources"),
    source_id: str = "la_city_agendas",
    db_path: Path | None = None,
    download_root: Path | None = None,
    structured_output_dir: Path | None = None,
) -> dict[str, Any]:
    source = get_source_config(config_dir, source_id)
    runtime = load_runtime_config()
    target_download_root = download_root or Path(source.download_root or "local/downloads")
    target_structured_dir = structured_output_dir or Path(
        source.structured_output_dir or "local/structured/la_city_agendas"
    )
    database_path = db_path or runtime.database_path

    payload = json.loads(message_path.read_text(encoding="utf-8"))
    message = GmailMessage.from_dict(payload)
    assessment = assess_message(source, message)
    notices = [
        notice
        for notice in assessment.metadata.get("attachment_notices", [])
        if isinstance(notice, dict)
    ]

    message_dir = target_download_root / "gmail" / message.message_id
    message_dir.mkdir(parents=True, exist_ok=True)
    target_structured_dir.mkdir(parents=True, exist_ok=True)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    database_path.touch(exist_ok=True)

    notice_documents = materialize_notice_attachments(message, notices, message_dir)
    remote_documents = materialize_primegov_documents(notices, target_download_root)
    structured_documents = build_structured_documents(remote_documents, target_structured_dir)
    batch_index_path = write_batch_index(message.message_id, structured_documents, target_structured_dir)

    with sqlite3.connect(database_path) as connection:
        ensure_base_schema(connection)
        upsert_source(connection, source)
        upsert_notice_documents(connection, source_id, assessment.subject, notice_documents)
        upsert_primegov_documents(connection, source_id, remote_documents)
        connection.commit()

    import_summary = {"documents_imported": 0, "items_imported": 0, "topics_imported": 0}
    if structured_documents:
        import_summary = import_items_index(
            index_path=batch_index_path,
            db_path=database_path,
            source_id=source_id,
        )

    manifest_path = message_dir / "ingestion_manifest.json"
    manifest = {
        "source_id": source_id,
        "message_id": message.message_id,
        "subject": assessment.subject,
        "meeting_date": assessment.meeting_date,
        "notice_documents": notice_documents,
        "primegov_documents": remote_documents,
        "structured_documents": [
            {
                "document_id": document.document_id,
                "source_path": document.source_path,
                "meeting_date": document.meeting_date,
                "cluster_name": document.cluster_name,
                "item_count": document.item_count,
            }
            for document in structured_documents
        ],
        "batch_index_path": str(batch_index_path.resolve()) if batch_index_path else None,
        "import_summary": import_summary,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return {
        "source_id": source_id,
        "message_id": message.message_id,
        "assessment": assessment.to_dict(),
        "notice_documents_written": len(notice_documents),
        "primegov_documents_written": len(remote_documents),
        "structured_documents_written": len(structured_documents),
        "batch_index_path": str(batch_index_path.resolve()) if batch_index_path else None,
        "manifest_path": str(manifest_path.resolve()),
        "database_path": str(database_path.resolve()),
        "import_summary": import_summary,
    }


def materialize_notice_attachments(
    message: GmailMessage,
    notices: list[dict[str, Any]],
    message_dir: Path,
) -> list[dict[str, Any]]:
    notice_by_filename = {
        str(notice.get("filename")): notice for notice in notices if notice.get("filename")
    }
    documents: list[dict[str, Any]] = []
    for attachment in message.attachments:
        if not attachment.content:
            continue
        filename = sanitize_filename(attachment.filename)
        html_path = message_dir / filename
        txt_path = message_dir / f"{Path(filename).stem}.txt"
        html_path.write_text(attachment.content, encoding="utf-8")
        txt_path.write_text(attachment.content, encoding="utf-8")
        notice = notice_by_filename.get(attachment.filename, {})
        documents.append(
            {
                "document_id": build_external_document_id(f"gmail_notice:{message.message_id}:{filename}"),
                "external_id": f"gmail_notice:{message.message_id}:{filename}",
                "title": f"{notice.get('body_name') or message.subject} - Email Notice",
                "document_type": (
                    "email_notice_of_cancellation" if notice.get("is_cancellation") else "email_agenda_notice"
                ),
                "meeting_date": notice.get("meeting_date"),
                "body_name": notice.get("body_name"),
                "file_path": str(html_path.resolve()),
                "text_path": str(txt_path.resolve()),
                "mime_type": "text/html",
                "sha256": hashlib.sha256(attachment.content.encode("utf-8")).hexdigest(),
                "bytes_downloaded": len(attachment.content.encode("utf-8")),
            }
        )
    return documents


def materialize_primegov_documents(
    notices: list[dict[str, Any]],
    download_root: Path,
) -> list[dict[str, Any]]:
    remote_documents: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for notice in notices:
        primegov_url = notice.get("primegov_url")
        if not isinstance(primegov_url, str) or not primegov_url or primegov_url in seen_urls:
            continue
        seen_urls.add(primegov_url)

        meeting_date = str(notice.get("meeting_date") or "undated")
        body_name = str(notice.get("body_name") or "la-city-agenda")
        template_id = str(notice.get("primegov_meeting_template_id") or "unknown")
        meeting_dir = download_root / "primegov_email" / meeting_date / slugify(body_name)
        meeting_dir.mkdir(parents=True, exist_ok=True)

        basename = f"{meeting_date}_{slugify(body_name)}_template-{template_id}_html-email"
        html_path = meeting_dir / f"{basename}.html"
        txt_path = meeting_dir / f"{basename}.txt"

        binary = fetch_binary(primegov_url)
        html_text = binary.decode("utf-8", errors="ignore")
        html_path.write_bytes(binary)
        txt_path.write_text(html_text, encoding="utf-8")

        external_id = f"primegov_email:{template_id}"
        remote_documents.append(
            {
                "document_id": build_external_document_id(external_id),
                "external_id": external_id,
                "title": f"{body_name} - PrimeGov Agenda",
                "document_type": (
                    "primegov_notice_of_cancellation_html"
                    if notice.get("is_cancellation")
                    else "primegov_agenda_html"
                ),
                "meeting_date": notice.get("meeting_date"),
                "body_name": body_name,
                "file_path": str(html_path.resolve()),
                "text_path": str(txt_path.resolve()),
                "mime_type": "text/html",
                "sha256": hashlib.sha256(binary).hexdigest(),
                "bytes_downloaded": len(binary),
                "source_url": primegov_url,
            }
        )
    return remote_documents


def build_structured_documents(
    remote_documents: list[dict[str, Any]],
    structured_output_dir: Path,
):
    structured_documents = []
    for remote_document in remote_documents:
        text_path = remote_document.get("text_path")
        if not isinstance(text_path, str) or not text_path:
            continue
        document = materialize_structured_document(
            Path(text_path),
            parser_name=LA_CITY_PRIMEGOV_HTML_PARSER,
        )
        if document.item_count == 0:
            continue
        output_path = structured_output_dir / f"{Path(document.source_path).stem}.structured.json"
        write_structured_document(document, output_path)
        structured_documents.append(document)
    return structured_documents


def write_batch_index(message_id: str, structured_documents, structured_output_dir: Path) -> Path | None:
    if not structured_documents:
        return None
    batch_dir = structured_output_dir / "batches"
    batch_dir.mkdir(parents=True, exist_ok=True)
    batch_index_path = batch_dir / f"{message_id}.agenda_items.index.json"
    write_items_index(build_items_index(structured_documents), batch_index_path)
    return batch_index_path


def upsert_notice_documents(
    connection: sqlite3.Connection,
    source_id: str,
    subject: str,
    documents: list[dict[str, Any]],
) -> None:
    upsert_document_rows(connection, source_id, documents, fallback_title=subject)


def upsert_primegov_documents(
    connection: sqlite3.Connection,
    source_id: str,
    documents: list[dict[str, Any]],
) -> None:
    upsert_document_rows(connection, source_id, documents, fallback_title="LA City PrimeGov Agenda")


def upsert_document_rows(
    connection: sqlite3.Connection,
    source_id: str,
    documents: list[dict[str, Any]],
    fallback_title: str,
) -> None:
    if not documents:
        return
    connection.executemany(
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
        [
            {
                "document_id": document["document_id"],
                "source_id": source_id,
                "external_id": document["external_id"],
                "title": document.get("title") or fallback_title,
                "document_type": document["document_type"],
                "meeting_date": document.get("meeting_date"),
                "body_name": document.get("body_name"),
                "jurisdiction": "Los Angeles",
                "file_path": document["file_path"],
                "text_path": document.get("text_path"),
                "sha256": document["sha256"],
                "mime_type": document["mime_type"],
                "collected_at": datetime.now(timezone.utc).isoformat(),
            }
            for document in documents
        ],
    )


def build_external_document_id(external_id: str) -> str:
    digest = hashlib.sha1(external_id.encode("utf-8")).hexdigest()[:16]
    return f"doc_{digest}"
