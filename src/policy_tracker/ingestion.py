from __future__ import annotations

import json
from pathlib import Path

from policy_tracker.la_city_email_ingestion import ingest_la_city_gmail_message_file
from policy_tracker.adapters.la_city_gmail import assess_message as assess_la_city_message
from policy_tracker.adapters.la_county_gmail import assess_message as assess_la_county_message
from policy_tracker.models import GmailMessage, MessageAssessment
from policy_tracker.source_loader import get_source_config

DEFAULT_ADAPTER = "la_county_gmail"
ASSESSORS = {
    "la_county_gmail": assess_la_county_message,
    "la_city_gmail": assess_la_city_message,
}
INGESTORS = {
    "la_city_gmail": ingest_la_city_gmail_message_file,
}


def assess_gmail_message_file(
    source_id: str, message_path: Path, config_dir: Path
) -> MessageAssessment:
    source = get_source_config(config_dir, source_id)
    payload = json.loads(message_path.read_text(encoding="utf-8"))
    message = GmailMessage.from_dict(payload)
    adapter_name = source.adapter or DEFAULT_ADAPTER
    try:
        assessor = ASSESSORS[adapter_name]
    except KeyError as exc:
        raise KeyError(f"Unknown Gmail adapter: {adapter_name}") from exc
    return assessor(source, message)


def ingest_gmail_message_file(
    source_id: str,
    message_path: Path,
    config_dir: Path,
    db_path: Path | None = None,
    download_root: Path | None = None,
    structured_output_dir: Path | None = None,
) -> dict[str, object]:
    source = get_source_config(config_dir, source_id)
    adapter_name = source.adapter or DEFAULT_ADAPTER
    try:
        ingestor = INGESTORS[adapter_name]
    except KeyError as exc:
        raise NotImplementedError(
            f"Full Gmail message ingestion is not implemented for adapter: {adapter_name}"
        ) from exc
    return ingestor(
        message_path=message_path,
        config_dir=config_dir,
        source_id=source_id,
        db_path=db_path,
        download_root=download_root,
        structured_output_dir=structured_output_dir,
    )
