from __future__ import annotations

import importlib
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from policy_tracker.models import ExtractedLink, MessageAssessment

PDF_SUFFIX = ".pdf"
MAX_CONTEXT_CHARS = 1200


def _maybe_add_archived_site_packages() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    archived_site_packages = repo_root / "archives" / ".venv" / "Lib" / "site-packages"
    archived_path = str(archived_site_packages)
    if archived_site_packages.exists() and archived_path not in sys.path:
        sys.path.append(archived_path)


def _load_pdf_reader() -> Any:
    candidates = ("pypdf", "PyPDF2")
    for module_name in candidates:
        try:
            module = importlib.import_module(module_name)
            return getattr(module, "PdfReader", None)
        except ModuleNotFoundError:
            continue
    return None


_maybe_add_archived_site_packages()
PdfReader = _load_pdf_reader()


@dataclass(slots=True)
class ProcessingError:
    stage: str
    code: str
    message: str
    retryable: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ExtractionOutcome:
    status: str
    method: str | None
    text_path: str | None
    text_excerpt: str | None
    errors: list[ProcessingError] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "method": self.method,
            "text_path": self.text_path,
            "text_excerpt": self.text_excerpt,
            "errors": [error.to_dict() for error in self.errors],
        }


@dataclass(slots=True)
class DownloadTarget:
    source_id: str
    message_id: str
    message_type: str
    meeting_date: str | None
    link_text: str
    url: str
    category: str
    document_kind: str
    filename: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ProcessedDocument:
    target: DownloadTarget
    processing_status: str
    review_status: str
    fetch_attempts: int
    local_path: str | None
    metadata_path: str | None
    bytes_downloaded: int
    extraction: ExtractionOutcome
    errors: list[ProcessingError] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target.to_dict(),
            "processing_status": self.processing_status,
            "review_status": self.review_status,
            "fetch_attempts": self.fetch_attempts,
            "local_path": self.local_path,
            "metadata_path": self.metadata_path,
            "bytes_downloaded": self.bytes_downloaded,
            "extraction": self.extraction.to_dict(),
            "errors": [error.to_dict() for error in self.errors],
        }


def build_download_targets(assessment: MessageAssessment) -> list[DownloadTarget]:
    targets: list[DownloadTarget] = []
    seen_urls: set[str] = set()
    for link in assessment.links:
        if link.category not in {"direct_pdf", "board_agenda_page"}:
            continue
        if link.resolved_url in seen_urls:
            continue
        seen_urls.add(link.resolved_url)
        targets.append(_target_from_link(assessment, link))
    return targets


def _target_from_link(
    assessment: MessageAssessment, link: ExtractedLink
) -> DownloadTarget:
    filename = derive_filename(link, assessment)
    return DownloadTarget(
        source_id=assessment.source_id,
        message_id=assessment.message_id,
        message_type=assessment.message_type,
        meeting_date=assessment.meeting_date,
        link_text=link.text,
        url=link.resolved_url,
        category=link.category,
        document_kind=classify_document_kind(link),
        filename=filename,
    )


def classify_document_kind(link: ExtractedLink) -> str:
    lowered_text = link.text.lower()
    lowered_url = link.resolved_url.lower()

    if link.category == "board_agenda_page":
        return "board_agenda_page"
    if "supdocs" in lowered_url:
        return "board_supporting_document"
    if "cluster" in lowered_text or "clusteragendas" in lowered_url:
        return "cluster_agenda_packet"
    if "agenda" in lowered_text:
        return "agenda_packet"
    return "linked_pdf"


def derive_filename(link: ExtractedLink, assessment: MessageAssessment) -> str:
    parsed = urlparse(link.resolved_url)
    path_name = Path(parsed.path).name
    if path_name:
        return sanitize_filename(path_name)

    parts = [
        assessment.meeting_date or "undated",
        link.text or assessment.message_type,
    ]
    base = "_".join(sanitize_filename(part) for part in parts if part)
    suffix = ".html" if link.category == "board_agenda_page" else PDF_SUFFIX
    return f"{base}{suffix}"


def sanitize_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    cleaned = cleaned.strip("._")
    return cleaned or "document"


def materialize_downloaded_document(
    target: DownloadTarget,
    binary_content: bytes,
    output_dir: Path,
    fetch_attempts: int,
) -> ProcessedDocument:
    output_dir.mkdir(parents=True, exist_ok=True)
    document_path = output_dir / target.filename
    document_path.write_bytes(binary_content)

    extraction = ExtractionOutcome(
        status="not_applicable",
        method=None,
        text_path=None,
        text_excerpt=None,
        errors=[],
    )
    processing_status = "downloaded"
    review_status = "not_needed"

    if document_path.suffix.lower() == PDF_SUFFIX:
        extraction = extract_pdf_text(document_path, output_dir)
        if extraction.status == "extracted":
            processing_status = "ready"
        elif extraction.status == "extractor_unavailable":
            processing_status = "downloaded_without_text"
            review_status = "needs_manual_review"
        elif extraction.status == "failed":
            processing_status = "downloaded_without_text"
            review_status = "needs_manual_review"
        else:
            processing_status = "downloaded_without_text"
            review_status = "needs_manual_review"
    elif document_path.suffix.lower() == ".html":
        processing_status = "ready"

    metadata_path = output_dir / f"{document_path.stem}.metadata.json"
    processed = ProcessedDocument(
        target=target,
        processing_status=processing_status,
        review_status=review_status,
        fetch_attempts=fetch_attempts,
        local_path=str(document_path),
        metadata_path=str(metadata_path),
        bytes_downloaded=len(binary_content),
        extraction=extraction,
        errors=[],
    )
    metadata_path.write_text(json.dumps(processed.to_dict(), indent=2), encoding="utf-8")
    return processed


def make_failed_document(
    target: DownloadTarget,
    fetch_attempts: int,
    error: ProcessingError,
) -> ProcessedDocument:
    return ProcessedDocument(
        target=target,
        processing_status="needs_retry" if error.retryable else "download_failed",
        review_status="not_needed",
        fetch_attempts=fetch_attempts,
        local_path=None,
        metadata_path=None,
        bytes_downloaded=0,
        extraction=ExtractionOutcome(
            status="not_started",
            method=None,
            text_path=None,
            text_excerpt=None,
            errors=[],
        ),
        errors=[error],
    )


def extract_pdf_text(path: Path, output_dir: Path) -> ExtractionOutcome:
    if PdfReader is None:
        return ExtractionOutcome(
            status="extractor_unavailable",
            method=None,
            text_path=None,
            text_excerpt=None,
            errors=[
                ProcessingError(
                    stage="extract",
                    code="pdf_backend_missing",
                    message="No PDF text extraction backend is available in the active environment.",
                    retryable=False,
                )
            ],
        )

    try:
        reader = PdfReader(str(path))
        parts: list[str] = []
        for page in reader.pages[:3]:
            page_text = page.extract_text() or ""
            if page_text.strip():
                parts.append(page_text.strip())
        text = "\n\n".join(parts).strip()
        if not text:
            return ExtractionOutcome(
                status="failed",
                method=getattr(PdfReader, "__module__", "unknown"),
                text_path=None,
                text_excerpt=None,
                errors=[
                    ProcessingError(
                        stage="extract",
                        code="no_text_extracted",
                        message="PDF was downloaded but no extractable text was returned.",
                        retryable=False,
                    )
                ],
            )
        text_path = output_dir / f"{path.stem}.txt"
        text_path.write_text(text, encoding="utf-8")
        return ExtractionOutcome(
            status="extracted",
            method=getattr(PdfReader, "__module__", "unknown"),
            text_path=str(text_path),
            text_excerpt=text[:MAX_CONTEXT_CHARS],
            errors=[],
        )
    except Exception as exc:
        return ExtractionOutcome(
            status="failed",
            method=getattr(PdfReader, "__module__", "unknown"),
            text_path=None,
            text_excerpt=None,
            errors=[
                ProcessingError(
                    stage="extract",
                    code="extract_exception",
                    message=str(exc),
                    retryable=False,
                )
            ],
        )
