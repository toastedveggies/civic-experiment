from __future__ import annotations

import json
from pathlib import Path

from policy_tracker.adapters.la_county_gmail import assess_message
from policy_tracker.models import GmailMessage, MessageAssessment
from policy_tracker.source_loader import get_source_config


def assess_gmail_message_file(
    source_id: str, message_path: Path, config_dir: Path
) -> MessageAssessment:
    source = get_source_config(config_dir, source_id)
    payload = json.loads(message_path.read_text(encoding="utf-8"))
    message = GmailMessage.from_dict(payload)
    return assess_message(source, message)
