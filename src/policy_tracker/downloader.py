from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from policy_tracker.document_context import (
    ProcessedDocument,
    ProcessingError,
    build_download_targets,
    make_failed_document,
    materialize_downloaded_document,
)
from policy_tracker.ingestion import assess_gmail_message_file

USER_AGENT = "policy-tracker/0.1"


def download_assessed_message_targets(
    source_id: str,
    message_path: Path,
    config_dir: Path,
    output_dir: Path,
    max_fetch_attempts: int = 2,
) -> list[ProcessedDocument]:
    assessment = assess_gmail_message_file(source_id, message_path, config_dir)
    targets = build_download_targets(assessment)
    download_dir = build_message_output_dir(output_dir, assessment.message_id)
    results: list[ProcessedDocument] = []
    for target in targets:
        results.append(
            process_target(
                target=target,
                output_dir=download_dir,
                max_fetch_attempts=max_fetch_attempts,
            )
        )
    return results


def process_target(
    target,
    output_dir: Path,
    max_fetch_attempts: int,
) -> ProcessedDocument:
    fetch_attempts = 0
    last_error: ProcessingError | None = None

    while fetch_attempts < max_fetch_attempts:
        fetch_attempts += 1
        try:
            binary = fetch_binary(target.url)
            return materialize_downloaded_document(
                target=target,
                binary_content=binary,
                output_dir=output_dir,
                fetch_attempts=fetch_attempts,
            )
        except Exception as exc:
            last_error = classify_fetch_error(exc)
            if not last_error.retryable:
                break

    assert last_error is not None
    failed = make_failed_document(
        target=target,
        fetch_attempts=fetch_attempts,
        error=last_error,
    )
    failed_metadata_path = output_dir / f"{Path(target.filename).stem}.failure.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    failed_metadata_path.write_text(json.dumps(failed.to_dict(), indent=2), encoding="utf-8")
    failed.metadata_path = str(failed_metadata_path)
    return failed


def build_message_output_dir(base_dir: Path, message_id: str) -> Path:
    return base_dir / message_id


def fetch_binary(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request) as response:
        return response.read()


def classify_fetch_error(exc: Exception) -> ProcessingError:
    if isinstance(exc, HTTPError):
        retryable = exc.code >= 500 or exc.code in {408, 429}
        return ProcessingError(
            stage="fetch",
            code=f"http_{exc.code}",
            message=str(exc),
            retryable=retryable,
        )
    if isinstance(exc, URLError):
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, FileNotFoundError):
            return ProcessingError(
                stage="fetch",
                code="file_not_found",
                message=str(reason),
                retryable=False,
            )
        return ProcessingError(
            stage="fetch",
            code="url_error",
            message=str(reason),
            retryable=True,
        )
    if isinstance(exc, FileNotFoundError):
        return ProcessingError(
            stage="fetch",
            code="file_not_found",
            message=str(exc),
            retryable=False,
        )
    return ProcessingError(
        stage="fetch",
        code="unexpected_fetch_error",
        message=str(exc),
        retryable=False,
    )


def write_manifest(results: list[ProcessedDocument], manifest_path: Path) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_payload = {
        "summary": summarize_results(results),
        "documents": [result.to_dict() for result in results],
    }
    manifest_path.write_text(json.dumps(manifest_payload, indent=2), encoding="utf-8")
    write_resilience_queues(results, manifest_path.parent)


def summarize_results(results: list[ProcessedDocument]) -> dict[str, int]:
    summary = {
        "total": len(results),
        "ready": 0,
        "needs_retry": 0,
        "needs_manual_review": 0,
        "download_failed": 0,
    }
    for result in results:
        if result.processing_status == "ready":
            summary["ready"] += 1
        elif result.processing_status == "needs_retry":
            summary["needs_retry"] += 1
        elif result.review_status == "needs_manual_review":
            summary["needs_manual_review"] += 1
        elif result.processing_status == "download_failed":
            summary["download_failed"] += 1
    return summary


def write_resilience_queues(results: list[ProcessedDocument], output_dir: Path) -> None:
    retry_items = [result.to_dict() for result in results if result.processing_status == "needs_retry"]
    manual_review_items = [
        result.to_dict()
        for result in results
        if result.review_status == "needs_manual_review"
    ]
    (output_dir / "retry_queue.json").write_text(json.dumps(retry_items, indent=2), encoding="utf-8")
    (output_dir / "manual_review_queue.json").write_text(
        json.dumps(manual_review_items, indent=2),
        encoding="utf-8",
    )
