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
from urllib.parse import urljoin, urlparse

from policy_tracker.document_context import PdfReader, extract_pdf_text
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
LANDING_PAGE_LINK_RE = re.compile(r"""<(?:a|iframe|embed)[^>]+(?:href|src)=["']([^"']+)["']""", re.IGNORECASE)
META_REFRESH_RE = re.compile(r"""<meta[^>]+http-equiv=["']refresh["'][^>]+content=["'][^"']*url=([^"' >]+)""", re.IGNORECASE)
SUPPORTING_LABEL_RE = re.compile(r"\b(Supporting Document|Attachments:)\b", re.IGNORECASE)
SUPPORTED_DOWNLOAD_SUFFIXES = {
    ".pdf",
    ".html",
    ".htm",
    ".txt",
    ".csv",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
}
SKIPPED_SUPPORTING_LINK_DOMAINS = {
    "webex.com",
    "zoom.us",
    "teams.microsoft.com",
}
ALLOWED_SUPPORTING_LINK_PATTERNS = (
    "file.lacounty.gov/sdsinter/bos/supdocs/",
    "file.lacounty.gov/sdsinter/bos/bc/",
    "ftp.pw.lacounty.gov:8443/pub/bos/",
    "lacounty.sharepoint.com/:b:/",
)


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
class DownloadedCEODocument:
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
    document_type: str
    mime_type: str
    parent_external_id: str | None = None

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
            "document_type": self.document_type,
            "mime_type": self.mime_type,
            "parent_external_id": self.parent_external_id,
        }


@dataclass(slots=True)
class SupportingDocumentReviewTarget:
    agenda_external_id: str
    agenda_url: str
    support_url: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {
            "agenda_external_id": self.agenda_external_id,
            "agenda_url": self.agenda_url,
            "support_url": self.support_url,
            "reason": self.reason,
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

    downloaded: list[DownloadedCEODocument] = []
    supporting_documents: list[DownloadedCEODocument] = []
    review_targets: list[SupportingDocumentReviewTarget] = []
    with sqlite3.connect(database_path) as connection:
        ensure_base_schema(connection)
        upsert_source(connection, source)
        for link in selected_links:
            agenda = download_agenda(link, target_download_root)
            upsert_document_record(connection, source_id, agenda)
            downloaded.append(agenda)
            agenda_supporting_documents, agenda_review_targets = download_supporting_documents_for_agenda(agenda)
            for supporting_document in agenda_supporting_documents:
                upsert_document_record(connection, source_id, supporting_document)
            supporting_documents.extend(agenda_supporting_documents)
            review_targets.extend(agenda_review_targets)
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
        "supporting_documents_downloaded": len(supporting_documents),
        "supporting_document_review_targets": len(review_targets),
        "by_body": summarize_by_body(downloaded),
        "documents": [agenda.to_dict() for agenda in downloaded],
        "supporting_documents": [document.to_dict() for document in supporting_documents],
        "review_targets": [target.to_dict() for target in review_targets],
    }
    manifest_path.write_text(json.dumps(manifest_payload, indent=2), encoding="utf-8")
    return {
        "source_id": source_id,
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "requested_bodies": requested_bodies,
        "agendas_downloaded": len(downloaded),
        "supporting_documents_downloaded": len(supporting_documents),
        "supporting_document_review_targets": len(review_targets),
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


def fetch_resource(url: str) -> tuple[bytes, str, str]:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request) as response:
        content_type = response.headers.get_content_type()
        final_url = response.geturl()
        return response.read(), content_type, final_url


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


def download_agenda(link: CEOAgendaLink, download_root: Path) -> DownloadedCEODocument:
    meeting_dir = download_root / "ceo" / link.agenda_date.isoformat() / slugify(link.body_name)
    meeting_dir.mkdir(parents=True, exist_ok=True)
    file_name = f"{link.agenda_date.isoformat()}_{slugify(link.body_name)}_{slugify(link.label)}.pdf"
    file_path = meeting_dir / file_name
    binary = fetch_binary(link.url)
    file_path.write_bytes(binary)
    extraction = extract_pdf_text(file_path, meeting_dir)
    external_id = link.url
    document_id = build_document_id(external_id)
    return DownloadedCEODocument(
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
        document_type="ceo_agenda_pdf",
        mime_type="application/pdf",
    )


def download_supporting_documents_for_agenda(
    agenda: DownloadedCEODocument,
) -> tuple[list[DownloadedCEODocument], list[SupportingDocumentReviewTarget]]:
    agenda_path = Path(agenda.file_path)
    meeting_dir = agenda_path.parent
    supporting_dir = meeting_dir / "supporting_docs"
    links = extract_pdf_annotation_links(agenda_path)
    extracted_text = Path(agenda.text_path).read_text(encoding="utf-8") if agenda.text_path else ""

    documents: list[DownloadedCEODocument] = []
    review_targets: list[SupportingDocumentReviewTarget] = []
    seen_urls: set[str] = set()
    supporting_index = 0

    for url in links:
        if not should_follow_supporting_link(url):
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)
        supporting_index += 1
        try:
            binary, content_type, final_url, resolution_reason = resolve_supporting_resource(url)
        except Exception as exc:
            review_targets.append(
                SupportingDocumentReviewTarget(
                    agenda_external_id=agenda.external_id,
                    agenda_url=agenda.url,
                    support_url=url,
                    reason=f"download_error: {exc}",
                )
            )
            continue

        if resolution_reason == "html_page_needs_review":
            review_targets.append(
                SupportingDocumentReviewTarget(
                    agenda_external_id=agenda.external_id,
                    agenda_url=agenda.url,
                    support_url=final_url,
                    reason="html_page_needs_review",
                )
            )

        document = materialize_supporting_document(
            agenda=agenda,
            binary=binary,
            content_type=content_type,
            original_url=url,
            final_url=final_url,
            index=supporting_index,
            output_dir=supporting_dir,
        )
        documents.append(document)

    if SUPPORTING_LABEL_RE.search(extracted_text) and not documents:
        review_targets.append(
            SupportingDocumentReviewTarget(
                agenda_external_id=agenda.external_id,
                agenda_url=agenda.url,
                support_url=agenda.url,
                reason="supporting_labels_without_trusted_links",
            )
        )

    return documents, review_targets


def extract_pdf_annotation_links(path: Path) -> list[str]:
    if PdfReader is None:
        return []

    reader = PdfReader(str(path))
    links: list[str] = []
    seen: set[str] = set()
    for page in reader.pages:
        annotations = page.get("/Annots")
        if not annotations:
            continue
        for annotation_ref in annotations:
            annotation = annotation_ref.get_object()
            action = annotation.get("/A")
            uri = action.get("/URI") if action else None
            if not isinstance(uri, str):
                continue
            normalized = uri.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            links.append(normalized)
    return links


def should_follow_supporting_link(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    netloc = parsed.netloc.lower()
    if any(blocked_domain in netloc for blocked_domain in SKIPPED_SUPPORTING_LINK_DOMAINS):
        return False
    lowered = url.lower()
    if "mailto:" in lowered or "publiccomment" in lowered:
        return False
    return any(pattern in lowered for pattern in ALLOWED_SUPPORTING_LINK_PATTERNS)


def resolve_supporting_resource(
    url: str,
    *,
    max_depth: int = 2,
    visited: set[str] | None = None,
) -> tuple[bytes, str, str, str]:
    seen = visited or set()
    if url in seen:
        raise ValueError(f"supporting link resolution loop detected for {url}")
    seen.add(url)

    binary, content_type, final_url = fetch_resource(url)
    if is_html_content(final_url, content_type):
        child_links = extract_landing_page_links(binary, final_url)
        candidate = select_best_supporting_child_link(child_links, seen)
        if candidate and max_depth > 0:
            resolved_binary, resolved_type, resolved_final_url, _ = resolve_supporting_resource(
                candidate,
                max_depth=max_depth - 1,
                visited=seen,
            )
            return resolved_binary, resolved_type, resolved_final_url, "followed_landing_page"
        return binary, content_type, final_url, "html_page_needs_review"
    return binary, content_type, final_url, "direct_download"


def is_html_content(url: str, content_type: str) -> bool:
    if content_type.lower() == "text/html":
        return True
    suffix = Path(urlparse(url).path).suffix.lower()
    return suffix in {".html", ".htm"}


def extract_landing_page_links(binary: bytes, base_url: str) -> list[str]:
    html_text = binary.decode("utf-8", errors="ignore")
    urls: list[str] = []
    seen: set[str] = set()

    meta_match = META_REFRESH_RE.search(html_text)
    if meta_match:
        candidate = urljoin(base_url, html.unescape(meta_match.group(1).strip()))
        if candidate not in seen:
            seen.add(candidate)
            urls.append(candidate)

    for href in LANDING_PAGE_LINK_RE.findall(html_text):
        candidate = urljoin(base_url, html.unescape(href.strip()))
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        urls.append(candidate)
    return urls


def select_best_supporting_child_link(urls: list[str], visited: set[str]) -> str | None:
    candidates = [url for url in urls if url not in visited and should_follow_supporting_link(url)]
    if not candidates:
        return None

    def rank(url: str) -> tuple[int, int, str]:
        lowered = url.lower()
        suffix = Path(urlparse(url).path).suffix.lower()
        if "/supdocs/" in lowered:
            return (0, 0, lowered)
        if suffix == ".pdf":
            return (0, 1, lowered)
        if suffix in {".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".csv"}:
            return (0, 2, lowered)
        if any(token in lowered for token in ("download", "attachment", "support", "supdoc", "boardletter")):
            return (1, 0, lowered)
        if suffix in {".html", ".htm", ""}:
            return (2, 0, lowered)
        return (3, 0, lowered)

    return sorted(candidates, key=rank)[0]


def materialize_supporting_document(
    *,
    agenda: DownloadedCEODocument,
    binary: bytes,
    content_type: str,
    original_url: str,
    final_url: str,
    index: int,
    output_dir: Path,
) -> DownloadedCEODocument:
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = determine_download_suffix(final_url, content_type)
    filename_base = derive_supporting_document_filename(final_url, index)
    file_path = output_dir / f"{filename_base}{suffix}"
    file_path.write_bytes(binary)

    text_path: str | None = None
    status = "downloaded"
    mime_type = normalize_mime_type(content_type, suffix)

    if suffix == ".pdf":
        extraction = extract_pdf_text(file_path, output_dir)
        text_path = extraction.text_path
        status = extraction.status if extraction.status != "not_applicable" else "downloaded"
    elif suffix in {".html", ".htm", ".txt"} or mime_type.startswith("text/"):
        text_target = output_dir / f"{file_path.stem}.txt"
        text_target.write_text(binary.decode("utf-8", errors="ignore"), encoding="utf-8")
        text_path = str(text_target.resolve())
        status = "ready"

    external_id = final_url
    document_id = build_document_id(external_id)
    label = f"{agenda.label} Supporting Document {index}"
    document_type = infer_supporting_document_type(final_url, mime_type, suffix)
    return DownloadedCEODocument(
        requested_name=agenda.requested_name,
        body_name=agenda.body_name,
        label=label,
        agenda_date=agenda.agenda_date,
        url=final_url,
        file_path=str(file_path.resolve()),
        text_path=text_path,
        sha256=hashlib.sha256(binary).hexdigest(),
        bytes_downloaded=len(binary),
        status=status,
        document_id=document_id,
        external_id=external_id,
        document_type=document_type,
        mime_type=mime_type,
        parent_external_id=agenda.external_id,
    )


def determine_download_suffix(url: str, content_type: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in SUPPORTED_DOWNLOAD_SUFFIXES:
        return suffix
    if content_type == "application/pdf":
        return ".pdf"
    if content_type == "text/html":
        return ".html"
    if content_type.startswith("text/"):
        return ".txt"
    return ".bin"


def normalize_mime_type(content_type: str, suffix: str) -> str:
    if content_type:
        return content_type
    if suffix == ".pdf":
        return "application/pdf"
    if suffix in {".html", ".htm"}:
        return "text/html"
    if suffix == ".txt":
        return "text/plain"
    return "application/octet-stream"


def derive_supporting_document_filename(url: str, index: int) -> str:
    parsed = urlparse(url)
    path_name = Path(parsed.path).name
    if path_name:
        stem = Path(path_name).stem
        sanitized = slugify(stem)
        if sanitized:
            return f"supporting_{index:03d}_{sanitized}"
    return f"supporting_{index:03d}"


def infer_supporting_document_type(url: str, mime_type: str, suffix: str) -> str:
    lowered_url = url.lower()
    if "/supdocs/" in lowered_url and suffix == ".pdf":
        return "ceo_supporting_document_pdf"
    if mime_type == "text/html" or suffix in {".html", ".htm"}:
        return "ceo_supporting_document_page"
    if suffix == ".pdf":
        return "ceo_supporting_document_pdf"
    return "ceo_supporting_document_file"


def upsert_document_record(
    connection: sqlite3.Connection,
    source_id: str,
    agenda: DownloadedCEODocument,
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
            "document_type": agenda.document_type,
            "meeting_date": agenda.agenda_date,
            "body_name": agenda.body_name,
            "jurisdiction": "Los Angeles County",
            "file_path": agenda.file_path,
            "text_path": agenda.text_path,
            "sha256": agenda.sha256,
            "mime_type": agenda.mime_type,
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


def summarize_by_body(downloaded: list[DownloadedCEODocument]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for agenda in downloaded:
        counts[agenda.requested_name] = counts.get(agenda.requested_name, 0) + 1
    return dict(sorted(counts.items()))
