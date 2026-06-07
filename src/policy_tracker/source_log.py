from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from policy_tracker.primegov_import import download_la_city_agendas_last_12_months
from policy_tracker.refresh import refresh_source
from policy_tracker.la_county_bos_import import download_bos_current_agendas
from policy_tracker.la_county_ceo_import import download_county_ceo_agendas
from policy_tracker.lahsa_import import download_lahsa_documents
from policy_tracker.source_loader import load_source_config

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - exercised in minimal local envs
    yaml = None


REQUIRED_SOURCE_FIELDS = {
    "source_ref",
    "source_name",
    "status",
    "activation_stage",
    "collection_role",
    "source_type",
    "source_shape",
    "access_model",
    "public_urls",
    "schedule",
    "freshness",
    "current_notes",
    "gaps",
}

REQUIRED_BODY_FIELDS = {
    "body_id",
    "body_name",
    "jurisdiction",
    "government_level",
    "sources",
}


@dataclass(slots=True)
class SourceLogValidation:
    valid: bool
    errors: list[str]
    warnings: list[str]
    source_count: int
    body_count: int
    activation_queue_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "source_count": self.source_count,
            "body_count": self.body_count,
            "activation_queue_count": self.activation_queue_count,
        }


def load_source_log(path: Path = Path("configs/source_log.yaml")) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        payload = yaml.safe_load(text)
    else:
        payload = parse_simple_yaml(text)
    if not isinstance(payload, dict):
        raise ValueError("Source log must deserialize to a mapping.")
    return payload


def parse_simple_yaml(text: str) -> Any:
    """Small YAML subset parser for this repo's source log.

    The project depends on PyYAML, but this fallback keeps CLI commands usable in
    stripped-down local shells. It supports nested mappings, lists, nulls,
    booleans, quoted scalars, integers, and folded block scalars.
    """

    lines = text.splitlines()
    index = 0

    def parse_block(indent: int) -> tuple[Any, int]:
        nonlocal index
        container: dict[str, Any] | list[Any] | None = None
        while index < len(lines):
            raw = lines[index]
            if not raw.strip() or raw.lstrip().startswith("#"):
                index += 1
                continue
            current_indent = len(raw) - len(raw.lstrip(" "))
            if current_indent < indent:
                break
            if current_indent > indent:
                raise ValueError(f"Unexpected indentation at line {index + 1}: {raw}")

            stripped = raw.strip()
            if stripped.startswith("- "):
                if container is None:
                    container = []
                if not isinstance(container, list):
                    raise ValueError(f"Mixed list/mapping at line {index + 1}: {raw}")
                item_text = stripped[2:].strip()
                index += 1
                if not item_text:
                    value, _ = parse_block(indent + 2)
                    container.append(value)
                    continue
                if ":" in item_text and not item_text.startswith(("http://", "https://")):
                    key, raw_value = item_text.split(":", 1)
                    item: dict[str, Any] = {key.strip(): parse_scalar(raw_value.strip())}
                    if index < len(lines) and next_content_indent(index) > indent:
                        nested, _ = parse_block(indent + 2)
                        if isinstance(nested, dict):
                            item.update(nested)
                        else:
                            raise ValueError(f"List item mapping expected at line {index + 1}.")
                    container.append(item)
                    continue
                container.append(parse_scalar(item_text))
                continue

            if container is None:
                container = {}
            if not isinstance(container, dict):
                raise ValueError(f"Mixed mapping/list at line {index + 1}: {raw}")
            if ":" not in stripped:
                raise ValueError(f"Could not parse line {index + 1}: {raw}")
            key, raw_value = stripped.split(":", 1)
            value_text = raw_value.strip()
            index += 1
            if value_text == ">":
                chunks: list[str] = []
                while index < len(lines):
                    probe = lines[index]
                    if not probe.strip():
                        chunks.append("")
                        index += 1
                        continue
                    probe_indent = len(probe) - len(probe.lstrip(" "))
                    if probe_indent <= indent:
                        break
                    chunks.append(probe.strip())
                    index += 1
                container[key.strip()] = " ".join(chunk for chunk in chunks if chunk)
                continue
            if value_text:
                container[key.strip()] = parse_scalar(value_text)
                continue
            if index < len(lines) and next_content_indent(index) > indent:
                value, _ = parse_block(indent + 2)
                container[key.strip()] = value
            else:
                container[key.strip()] = None
        return container if container is not None else {}, index

    def next_content_indent(start: int) -> int:
        probe_index = start
        while probe_index < len(lines):
            probe = lines[probe_index]
            if probe.strip() and not probe.lstrip().startswith("#"):
                return len(probe) - len(probe.lstrip(" "))
            probe_index += 1
        return -1

    payload, _ = parse_block(0)
    return payload


def parse_scalar(value: str) -> Any:
    if value in {"null", "None", "~"}:
        return None
    if value == "true":
        return True
    if value == "false":
        return False
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        return json.loads(value.replace("'", '"'))
    try:
        return int(value)
    except ValueError:
        return value


def validate_source_log(path: Path = Path("configs/source_log.yaml")) -> SourceLogValidation:
    payload = load_source_log(path)
    errors: list[str] = []
    warnings: list[str] = []

    sources = payload.get("sources")
    bodies = payload.get("bodies")
    activation_queue = payload.get("activation_queue", [])
    if not isinstance(sources, list):
        errors.append("Top-level sources must be a list.")
        sources = []
    if not isinstance(bodies, list):
        errors.append("Top-level bodies must be a list.")
        bodies = []
    if not isinstance(activation_queue, list):
        errors.append("Top-level activation_queue must be a list.")
        activation_queue = []

    source_refs: set[str] = set()
    for idx, source in enumerate(sources):
        if not isinstance(source, dict):
            errors.append(f"sources[{idx}] must be a mapping.")
            continue
        missing = sorted(REQUIRED_SOURCE_FIELDS - set(source))
        if missing:
            errors.append(f"{source.get('source_ref', f'sources[{idx}]')} missing fields: {', '.join(missing)}")
        ref = source.get("source_ref")
        if not isinstance(ref, str) or not ref:
            errors.append(f"sources[{idx}] has empty source_ref.")
            continue
        if ref in source_refs:
            errors.append(f"Duplicate source_ref: {ref}")
        source_refs.add(ref)
        validate_enum(payload, source, "status", "source_status_values", errors)
        validate_enum(payload, source, "collection_role", "collection_role_values", errors)
        validate_enum(payload, source, "activation_stage", "activation_stage_values", errors)
        validate_enum(payload, source, "access_model", "access_model_values", errors)
        if not source.get("public_urls"):
            warnings.append(f"{ref} has no public_urls.")
        schedule = source.get("schedule")
        if isinstance(schedule, dict) and "cadence" not in schedule:
            warnings.append(f"{ref} schedule has no cadence.")

    body_ids: set[str] = set()
    for idx, body in enumerate(bodies):
        if not isinstance(body, dict):
            errors.append(f"bodies[{idx}] must be a mapping.")
            continue
        missing = sorted(REQUIRED_BODY_FIELDS - set(body))
        if missing:
            errors.append(f"{body.get('body_id', f'bodies[{idx}]')} missing fields: {', '.join(missing)}")
        body_id = body.get("body_id")
        if isinstance(body_id, str):
            if body_id in body_ids:
                errors.append(f"Duplicate body_id: {body_id}")
            body_ids.add(body_id)
        for linked_source in body.get("sources", []) or []:
            ref = linked_source.get("source_ref") if isinstance(linked_source, dict) else None
            if ref not in source_refs:
                errors.append(f"{body_id} references unknown source_ref: {ref}")

    for idx, item in enumerate(activation_queue):
        if not isinstance(item, dict):
            errors.append(f"activation_queue[{idx}] must be a mapping.")
            continue
        ref = item.get("source_ref")
        if ref not in source_refs:
            errors.append(f"activation_queue[{idx}] references unknown source_ref: {ref}")

    return SourceLogValidation(
        valid=not errors,
        errors=errors,
        warnings=warnings,
        source_count=len(sources),
        body_count=len(bodies),
        activation_queue_count=len(activation_queue),
    )


def validate_enum(
    payload: dict[str, Any],
    source: dict[str, Any],
    field_name: str,
    enum_name: str,
    errors: list[str],
) -> None:
    allowed = payload.get(enum_name)
    value = source.get(field_name)
    if isinstance(allowed, list) and value not in allowed:
        errors.append(f"{source.get('source_ref')} has invalid {field_name}: {value}")


def list_source_log(
    path: Path = Path("configs/source_log.yaml"),
    *,
    status: str | None = None,
    activation_stage: str | None = None,
    collection_role: str | None = None,
) -> dict[str, Any]:
    payload = load_source_log(path)
    sources = payload.get("sources", [])
    if not isinstance(sources, list):
        sources = []
    rows = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        if status and source.get("status") != status:
            continue
        if activation_stage and source.get("activation_stage") != activation_stage:
            continue
        if collection_role and source.get("collection_role") != collection_role:
            continue
        freshness = source.get("freshness") if isinstance(source.get("freshness"), dict) else {}
        schedule = source.get("schedule") if isinstance(source.get("schedule"), dict) else {}
        rows.append(
            {
                "source_ref": source.get("source_ref"),
                "source_name": source.get("source_name"),
                "current_source_id": source.get("current_source_id"),
                "status": source.get("status"),
                "activation_stage": source.get("activation_stage"),
                "collection_role": source.get("collection_role"),
                "access_model": source.get("access_model"),
                "cadence": schedule.get("cadence"),
                "latest_imported_meeting_date": freshness.get("latest_imported_meeting_date"),
                "last_failure": freshness.get("last_failure"),
            }
        )
    return {
        "source_log_path": str(path),
        "count": len(rows),
        "sources": rows,
    }


def activate_source(
    source_ref: str,
    path: Path = Path("configs/source_log.yaml"),
    config_dir: Path = Path("configs/sources"),
    *,
    write: bool = False,
) -> dict[str, Any]:
    validation = validate_source_log(path)
    if not validation.valid:
        return {"source_ref": source_ref, "activated": False, "validation": validation.to_dict()}

    source = get_source_log_entry(source_ref, path)
    if source is None:
        raise KeyError(f"Unknown source_ref: {source_ref}")

    download_root = source.get("local_download_root")
    actions: list[dict[str, Any]] = []
    if isinstance(download_root, str) and write:
        Path(download_root).mkdir(parents=True, exist_ok=True)
        actions.append({"action": "ensure_download_root", "path": download_root})

    sync_summary = None
    if source.get("current_source_id"):
        sync_summary = sync_source_config_from_log(source_ref, path, config_dir, write=write)

    return {
        "source_ref": source_ref,
        "activated": bool(write),
        "write": write,
        "activation_stage": source.get("activation_stage"),
        "status": source.get("status"),
        "actions": actions,
        "sync_summary": sync_summary,
        "activation_checks": source.get("activation_checks", []),
    }


def sync_source_config_from_log(
    source_ref: str,
    path: Path = Path("configs/source_log.yaml"),
    config_dir: Path = Path("configs/sources"),
    *,
    write: bool = False,
) -> dict[str, Any]:
    source = get_source_log_entry(source_ref, path)
    if source is None:
        raise KeyError(f"Unknown source_ref: {source_ref}")
    source_id = source.get("current_source_id")
    if not isinstance(source_id, str) or not source_id:
        return {"source_ref": source_ref, "changed": False, "reason": "no_current_source_id"}

    config_path = config_dir / f"{source_id}.yaml"
    config = load_source_config(config_path)
    primary_url = first_public_url(source)
    changes: dict[str, dict[str, Any]] = {}
    if primary_url and config.base_url != primary_url:
        changes["base_url"] = {"old": config.base_url, "new": primary_url}

    if write and changes:
        update_simple_yaml_scalars(config_path, {field: str(change["new"]) for field, change in changes.items()})

    return {
        "source_ref": source_ref,
        "source_id": source_id,
        "config_path": str(config_path),
        "write": write,
        "changed": bool(changes),
        "changes": changes,
    }


def get_source_log_entry(source_ref: str, path: Path = Path("configs/source_log.yaml")) -> dict[str, Any] | None:
    payload = load_source_log(path)
    for source in payload.get("sources", []) or []:
        if isinstance(source, dict) and source.get("source_ref") == source_ref:
            return source
    return None


def first_public_url(source: dict[str, Any]) -> str | None:
    public_urls = source.get("public_urls")
    if not isinstance(public_urls, list):
        return None
    for item in public_urls:
        if isinstance(item, dict) and isinstance(item.get("url"), str):
            return item["url"]
    return None


def update_simple_yaml_scalars(path: Path, updates: dict[str, str]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    seen: set[str] = set()
    output: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not line.startswith(" ") and ":" in stripped:
            key = stripped.split(":", 1)[0]
            if key in updates:
                output.append(f"{key}: {updates[key]}")
                seen.add(key)
                continue
        output.append(line)
    for key, value in updates.items():
        if key not in seen:
            output.append(f"{key}: {value}")
    path.write_text("\n".join(output) + "\n", encoding="utf-8")


def check_online_source(
    source_ref: str,
    path: Path = Path("configs/source_log.yaml"),
    config_dir: Path = Path("configs/sources"),
    state_dir: Path = Path("local/state"),
    db_path: Path | None = None,
    *,
    today: date | None = None,
    skip_findings: bool = False,
    download_only: bool = False,
) -> dict[str, Any]:
    source = get_source_log_entry(source_ref, path)
    if source is None:
        raise KeyError(f"Unknown source_ref: {source_ref}")
    adapter = source.get("adapter_candidate")
    source_id = source.get("current_source_id")
    if not isinstance(source_id, str):
        raise ValueError(f"{source_ref} does not define current_source_id.")

    schedule = source.get("schedule") if isinstance(source.get("schedule"), dict) else {}
    lookback_days = int(schedule.get("lookback_days") or 14)
    lookahead_days = int(schedule.get("lookahead_days") or 0)
    current_date = today or date.today()
    from_date = current_date - timedelta(days=lookback_days)
    to_date = current_date + timedelta(days=lookahead_days)

    if adapter == "la_city_primegov_online":
        download_summary = download_la_city_agendas_last_12_months(
            from_date=format_primegov_date(from_date),
            to_date=format_primegov_date(to_date),
            source_id=source_id,
            config_dir=config_dir,
            db_path=db_path,
        )
    elif adapter == "la_county_ceo_agendas_archive":
        requested_bodies = source.get("tracked_body_names")
        if not isinstance(requested_bodies, list) or not requested_bodies:
            raise ValueError(f"{source_ref} must define tracked_body_names for CEO agenda checks.")
        download_summary = download_county_ceo_agendas(
            requested_bodies=[str(body) for body in requested_bodies],
            from_date=from_date,
            to_date=to_date,
            source_id=source_id,
            config_dir=config_dir,
            db_path=db_path,
            manifest_filename="ceo_incremental_manifest.json",
            include_supporting_documents=False,
        )
    elif adapter == "la_county_bos_current_page":
        download_summary = download_bos_current_agendas(
            from_date=from_date,
            to_date=to_date,
            source_id=source_id,
            config_dir=config_dir,
            db_path=db_path,
            manifest_filename="bos_current_manifest.json",
        )
    elif adapter == "lahsa_document_library":
        tracked_scope_ids = source.get("tracked_scope_ids")
        keywords = source.get("tracked_keywords")
        max_documents_per_scope = int(source.get("max_documents_per_scope") or 20)
        download_summary = download_lahsa_documents(
            source_id=source_id,
            config_dir=config_dir,
            db_path=db_path,
            scope_ids=[str(scope_id) for scope_id in tracked_scope_ids] if isinstance(tracked_scope_ids, list) else None,
            keywords=[str(keyword) for keyword in keywords] if isinstance(keywords, list) else None,
            manifest_filename="lahsa_documents_manifest.json",
            max_documents_per_scope=max_documents_per_scope,
        )
    else:
        raise NotImplementedError(f"Online check is not implemented for adapter_candidate: {adapter}")
    refresh_summary = None
    if not download_only:
        refresh_summary = refresh_source(
            source_id=source_id,
            config_dir=config_dir,
            state_dir=state_dir,
            db_path=db_path,
            skip_findings=skip_findings,
        )
    return {
        "source_ref": source_ref,
        "source_id": source_id,
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "download_summary": download_summary,
        "refresh_summary": refresh_summary,
        "download_only": download_only,
    }


def format_primegov_date(value: date) -> str:
    return value.strftime("%m-%d-%Y")
