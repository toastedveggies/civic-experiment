from __future__ import annotations

import hashlib
import html
import json
import re
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import parse_qs, unquote, urljoin, urlparse
from urllib.request import Request, urlopen

from policy_tracker.document_context import extract_pdf_text
from policy_tracker.primegov_import import ensure_base_schema, upsert_source
from policy_tracker.runtime_config import load_runtime_config
from policy_tracker.source_loader import get_source_config

LAHSA_DOCUMENTS_URL = "https://www.lahsa.org/documents"
USER_AGENT = "policy-tracker/0.1"
DEFAULT_SOURCE_ID = "lahsa_documents"

SCOPE_LINK_RE = re.compile(
    r'<a[^>]+href="(?P<href>documents\?scope=(?P<scope_id>\d+))"[^>]*>.*?'
    r'<div class="tile-label">(?P<label>.*?)</div>.*?</a>',
    re.IGNORECASE | re.DOTALL,
)
DOCUMENT_CARD_RE = re.compile(
    r'<a\s+href="(?P<href>documents\?id=(?P<document_id>[^"]+))"\s+class="doclib-item">.*?'
    r'<div class="doclib-item-name">(?P<title>.*?)</div>.*?</a>',
    re.IGNORECASE | re.DOTALL,
)
JSON_LD_RE = re.compile(
    r'<script\s+type="application/ld\+json">\s*(?P<payload>{.*?})\s*</script>',
    re.IGNORECASE | re.DOTALL,
)
DOWNLOAD_RE = re.compile(r'id="bodycontent_hlDownload"[^>]+href="(?P<href>[^"]+)"', re.IGNORECASE | re.DOTALL)
SPAN_VALUE_RE = re.compile(
    r'id="(?P<id>bodycontent_lbl(?:DocumentType|Project|ProgramType|Scope|PubDate|ExpireDate|Lastmodified))">'
    r'(?P<value>.*?)</span>',
    re.IGNORECASE | re.DOTALL,
)


@dataclass(slots=True)
class LAHSADocumentLink:
    scope_id: str
    scope_name: str | None
    title: str
    detail_url: str
    lahsa_document_id: str


@dataclass(slots=True)
class LAHSADocument:
    title: str
    lahsa_document_id: str
    scope_id: str
    scope_name: str | None
    detail_url: str
    download_url: str
    file_path: str
    text_path: str | None
    sha256: str
    bytes_downloaded: int
    mime_type: str
    document_type: str
    project: str | None
    program_type: str | None
    project_scope: str | None
    published_date: str | None
    last_modified: str | None
    document_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "lahsa_document_id": self.lahsa_document_id,
            "scope_id": self.scope_id,
            "scope_name": self.scope_name,
            "detail_url": self.detail_url,
            "download_url": self.download_url,
            "file_path": self.file_path,
            "text_path": self.text_path,
            "sha256": self.sha256,
            "bytes_downloaded": self.bytes_downloaded,
            "mime_type": self.mime_type,
            "document_type": self.document_type,
            "project": self.project,
            "program_type": self.program_type,
            "project_scope": self.project_scope,
            "published_date": self.published_date,
            "last_modified": self.last_modified,
            "document_id": self.document_id,
        }


def download_lahsa_documents(
    *,
    source_id: str = DEFAULT_SOURCE_ID,
    config_dir: Path = Path("configs/sources"),
    db_path: Path | None = None,
    download_root: Path | None = None,
    scope_ids: list[str] | None = None,
    keywords: list[str] | None = None,
    manifest_filename: str = "lahsa_documents_manifest.json",
    max_documents_per_scope: int = 20,
) -> dict[str, Any]:
    source = get_source_config(config_dir, source_id)
    runtime = load_runtime_config()
    target_download_root = download_root or Path(source.download_root or "local/downloads/lahsa_documents")
    database_path = db_path or runtime.database_path
    target_download_root.mkdir(parents=True, exist_ok=True)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    scope_map = discover_lahsa_scopes()
    selected_scope_ids = scope_ids or sorted(scope_map)
    links: list[LAHSADocumentLink] = []
    for scope_id in selected_scope_ids:
        scope_name = scope_map.get(scope_id)
        scope_links = discover_lahsa_scope_documents(scope_id, scope_name)
        links.extend(scope_links[:max_documents_per_scope])

    filtered_links = filter_document_links(links, keywords)
    downloaded: list[LAHSADocument] = []
    failures: list[dict[str, Any]] = []
    with sqlite3.connect(database_path) as connection:
        ensure_base_schema(connection)
        upsert_source(connection, source)
        for link in filtered_links:
            try:
                document = download_lahsa_document(link, target_download_root)
            except URLError as exc:
                failures.append({"detail_url": link.detail_url, "error": str(exc)})
                continue
            upsert_lahsa_document_record(connection, source_id, document)
            downloaded.append(document)
        connection.commit()

    manifest_path = target_download_root / manifest_filename
    manifest = {
        "source_id": source_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "discovery_method": "lahsa_document_library_scope_pages",
        "source_url": LAHSA_DOCUMENTS_URL,
        "scope_ids": selected_scope_ids,
        "keywords": keywords or [],
        "documents_discovered": len(links),
        "documents_selected": len(filtered_links),
        "documents_downloaded": len(downloaded),
        "failures": failures,
        "by_scope": summarize_by_scope(downloaded),
        "documents": [item.to_dict() for item in downloaded],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return {
        "source_id": source_id,
        "discovery_method": "lahsa_document_library_scope_pages",
        "source_url": LAHSA_DOCUMENTS_URL,
        "scope_ids": selected_scope_ids,
        "keywords": keywords or [],
        "documents_discovered": len(links),
        "documents_selected": len(filtered_links),
        "documents_downloaded": len(downloaded),
        "failures": len(failures),
        "download_root": str(target_download_root.resolve()),
        "database_path": str(database_path.resolve()),
        "manifest_path": str(manifest_path.resolve()),
        "by_scope": summarize_by_scope(downloaded),
    }


def discover_lahsa_scopes() -> dict[str, str]:
    html_text = fetch_text(LAHSA_DOCUMENTS_URL)
    scopes: dict[str, str] = {}
    for match in SCOPE_LINK_RE.finditer(html_text):
        scopes[match.group("scope_id")] = clean_text(match.group("label"))
    return scopes


def discover_lahsa_scope_documents(scope_id: str, scope_name: str | None = None) -> list[LAHSADocumentLink]:
    scope_url = f"{LAHSA_DOCUMENTS_URL}?scope={scope_id}"
    html_text = fetch_text(scope_url)
    links: list[LAHSADocumentLink] = []
    seen: set[str] = set()
    for match in DOCUMENT_CARD_RE.finditer(html_text):
        raw_id = html.unescape(match.group("document_id"))
        if raw_id in seen:
            continue
        seen.add(raw_id)
        links.append(
            LAHSADocumentLink(
                scope_id=scope_id,
                scope_name=scope_name,
                title=clean_text(match.group("title")),
                detail_url=urljoin(LAHSA_DOCUMENTS_URL, html.unescape(match.group("href"))),
                lahsa_document_id=raw_id,
            )
        )
    return links


def filter_document_links(links: list[LAHSADocumentLink], keywords: list[str] | None) -> list[LAHSADocumentLink]:
    if not keywords:
        return links
    lowered_keywords = [keyword.lower() for keyword in keywords]
    return [link for link in links if any(keyword in link.title.lower() for keyword in lowered_keywords)]


def download_lahsa_document(link: LAHSADocumentLink, download_root: Path) -> LAHSADocument:
    detail_html = fetch_text(link.detail_url)
    metadata = parse_lahsa_detail_metadata(detail_html)
    download_url = metadata.get("download_url")
    if not isinstance(download_url, str) or not download_url:
        raise URLError(f"No LAHSA download URL found for {link.detail_url}")
    binary = fetch_binary(download_url)

    suffix = suffix_for_url(download_url)
    scope_part = f"scope-{link.scope_id}-{slugify(link.scope_name or 'documents')}"
    output_dir = download_root / "lahsa" / scope_part
    output_dir.mkdir(parents=True, exist_ok=True)
    file_path = output_dir / f"{slugify(link.lahsa_document_id)}{suffix}"
    file_path.write_bytes(binary)

    text_path: str | None = None
    if suffix == ".pdf":
        extraction = extract_pdf_text(file_path, output_dir)
        text_path = extraction.text_path

    document_type = build_document_type(metadata.get("document_type"), suffix)
    published_date = normalize_date(metadata.get("published_date"))
    last_modified = normalize_datetime(metadata.get("last_modified"))
    document = LAHSADocument(
        title=str(metadata.get("title") or link.title),
        lahsa_document_id=link.lahsa_document_id,
        scope_id=link.scope_id,
        scope_name=link.scope_name,
        detail_url=link.detail_url,
        download_url=download_url,
        file_path=str(file_path.resolve()),
        text_path=text_path,
        sha256=hashlib.sha256(binary).hexdigest(),
        bytes_downloaded=len(binary),
        mime_type=mime_type_for_suffix(suffix),
        document_type=document_type,
        project=empty_to_none(metadata.get("project")),
        program_type=empty_to_none(metadata.get("program_type")),
        project_scope=empty_to_none(metadata.get("project_scope")),
        published_date=published_date,
        last_modified=last_modified,
        document_id=build_document_id(link.detail_url),
    )
    metadata_path = output_dir / f"{file_path.stem}.metadata.json"
    metadata_path.write_text(json.dumps(document.to_dict(), indent=2), encoding="utf-8")
    return document


def parse_lahsa_detail_metadata(detail_html: str) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    json_match = JSON_LD_RE.search(detail_html)
    if json_match:
        try:
            payload = json.loads(html.unescape(json_match.group("payload")))
        except json.JSONDecodeError:
            payload = {}
        if isinstance(payload, dict):
            metadata["title"] = payload.get("name")
            metadata["published_date"] = payload.get("datePublished")
            metadata["last_modified"] = payload.get("dateModified")
    download_match = DOWNLOAD_RE.search(detail_html)
    if download_match:
        metadata["download_url"] = html.unescape(download_match.group("href"))

    span_values = {match.group("id"): clean_text(match.group("value")) for match in SPAN_VALUE_RE.finditer(detail_html)}
    metadata["document_type"] = span_values.get("bodycontent_lblDocumentType")
    metadata["project"] = span_values.get("bodycontent_lblProject")
    metadata["program_type"] = span_values.get("bodycontent_lblProgramType")
    metadata["project_scope"] = span_values.get("bodycontent_lblScope")
    metadata["published_date"] = span_values.get("bodycontent_lblPubDate") or metadata.get("published_date")
    metadata["last_modified"] = span_values.get("bodycontent_lblLastmodified") or metadata.get("last_modified")
    return metadata


def upsert_lahsa_document_record(connection: sqlite3.Connection, source_id: str, document: LAHSADocument) -> None:
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
            "external_id": document.detail_url,
            "title": document.title,
            "document_type": document.document_type,
            "meeting_date": document.published_date,
            "body_name": "Los Angeles Homeless Services Authority",
            "jurisdiction": "Los Angeles County and City of Los Angeles",
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


def suffix_for_url(url: str) -> str:
    parsed = urlparse(unquote(url))
    filename = Path(parsed.path).name
    query_id = parse_qs(parsed.query).get("id", [""])[0]
    candidate = filename or query_id
    suffix = Path(candidate).suffix.lower()
    return suffix if suffix in {".pdf", ".xlsx", ".xls", ".doc", ".docx"} else ".pdf"


def mime_type_for_suffix(suffix: str) -> str:
    return {
        ".pdf": "application/pdf",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xls": "application/vnd.ms-excel",
        ".doc": "application/msword",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }.get(suffix, "application/octet-stream")


def build_document_type(document_type: Any, suffix: str) -> str:
    label = slugify(str(document_type or "document")).replace("-", "_")
    suffix_label = suffix.lstrip(".") or "file"
    return f"lahsa_{label}_{suffix_label}"


def normalize_date(value: Any) -> str | None:
    raw = empty_to_none(value)
    if raw is None:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return raw


def normalize_datetime(value: Any) -> str | None:
    raw = empty_to_none(value)
    if raw is None:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw, fmt).isoformat()
        except ValueError:
            continue
    return raw


def empty_to_none(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = clean_text(str(value))
    return cleaned or None


def clean_text(value: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", value)).split())


def build_document_id(external_id: str) -> str:
    return f"doc_{hashlib.sha1(external_id.encode('utf-8')).hexdigest()[:16]}"


def slugify(value: str) -> str:
    chars = [char if char.isalnum() else "-" for char in value.lower()]
    slug = "".join(chars)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "document"


def summarize_by_scope(documents: list[LAHSADocument]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in documents:
        label = item.scope_name or item.scope_id
        counts[label] = counts.get(label, 0) + 1
    return dict(sorted(counts.items()))
