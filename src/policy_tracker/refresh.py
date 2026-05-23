from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from policy_tracker.findings import generate_findings
from policy_tracker.item_extraction import is_preferred_text_path_for_parser
from policy_tracker.models import SourceConfig
from policy_tracker.query_layer import QueryFilters
from policy_tracker.source_loader import get_source_config
from policy_tracker.sqlite_import import import_items_index
from policy_tracker.storage import (
    build_items_index,
    materialize_structured_document,
    write_items_index,
    write_structured_document,
)


@dataclass(slots=True)
class RefreshFileState:
    path: str
    modified_time_ns: int
    size_bytes: int
    recorded_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def refresh_source(
    source_id: str,
    config_dir: Path,
    state_dir: Path,
    db_path: Path | None = None,
    skip_findings: bool = False,
    findings_limit: int = 10000,
) -> dict[str, Any]:
    source = get_source_config(config_dir, source_id)
    download_root = get_download_root(source)
    structured_dir = get_structured_output_dir(source)
    state_path = get_state_path(state_dir, source_id)
    known_files = load_refresh_state(state_path)
    text_paths = discover_text_paths(download_root, source.parser)
    changed_paths = select_changed_paths(text_paths, known_files)

    summary: dict[str, Any] = {
        "source_id": source_id,
        "download_root": str(download_root),
        "structured_output_dir": str(structured_dir),
        "text_files_discovered": len(text_paths),
        "new_or_changed_text_files": len(changed_paths),
        "documents_written": 0,
        "items_written": 0,
        "import_summary": None,
        "findings_summary": None,
        "state_path": str(state_path),
    }

    if not changed_paths:
        return summary

    documents = [materialize_structured_document(path, parser_name=source.parser) for path in changed_paths]
    documents = [document for document in documents if document.item_count > 0]
    structured_dir.mkdir(parents=True, exist_ok=True)
    for document in documents:
        source_name = Path(document.source_path).stem
        output_path = structured_dir / f"{source_name}.structured.json"
        write_structured_document(document, output_path)

    rows = build_items_index(documents)
    index_path = structured_dir / "agenda_items.latest_refresh.index.json"
    write_items_index(rows, index_path)
    import_summary = import_items_index(index_path=index_path, db_path=db_path, source_id=source_id)

    findings_summary = None
    if not skip_findings:
        findings_summary = generate_findings(
            db_path=db_path,
            filters=QueryFilters(source_id=source_id, limit=findings_limit),
        )

    update_refresh_state(state_path, known_files, changed_paths)

    summary["documents_written"] = len(documents)
    summary["items_written"] = len(rows)
    summary["import_summary"] = import_summary
    summary["findings_summary"] = findings_summary
    return summary


def get_download_root(source: SourceConfig) -> Path:
    return Path(source.download_root or "local/downloads")


def get_structured_output_dir(source: SourceConfig) -> Path:
    if source.structured_output_dir:
        return Path(source.structured_output_dir)
    return Path("local/structured") / source.source_id


def get_state_path(state_dir: Path, source_id: str) -> Path:
    return state_dir / f"{source_id}.refresh_state.json"


def discover_text_paths(download_root: Path, parser_name: str | None = None) -> list[Path]:
    if not download_root.exists():
        return []
    return sorted(
        path
        for path in download_root.rglob("*.txt")
        if path.is_file() and is_preferred_text_path_for_parser(path, parser_name)
    )


def select_changed_paths(paths: list[Path], known_files: dict[str, RefreshFileState]) -> list[Path]:
    changed: list[Path] = []
    for path in paths:
        resolved = str(path.resolve())
        stat = path.stat()
        previous = known_files.get(resolved)
        if previous is None:
            changed.append(path)
            continue
        if previous.modified_time_ns != stat.st_mtime_ns or previous.size_bytes != stat.st_size:
            changed.append(path)
    return changed


def load_refresh_state(state_path: Path) -> dict[str, RefreshFileState]:
    if not state_path.exists():
        return {}
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    return {
        path: RefreshFileState(**entry)
        for path, entry in payload.get("files", {}).items()
    }


def update_refresh_state(
    state_path: Path,
    known_files: dict[str, RefreshFileState],
    changed_paths: list[Path],
) -> None:
    for path in changed_paths:
        stat = path.stat()
        resolved = str(path.resolve())
        known_files[resolved] = RefreshFileState(
            path=resolved,
            modified_time_ns=stat.st_mtime_ns,
            size_bytes=stat.st_size,
            recorded_at=datetime.now(timezone.utc).isoformat(),
        )

    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "files": {
            path: entry.to_dict()
            for path, entry in sorted(known_files.items())
        }
    }
    state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
