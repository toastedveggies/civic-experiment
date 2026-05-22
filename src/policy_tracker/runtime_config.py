from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class RuntimeConfig:
    database_path: Path
    data_root: Path
    documents_root: Path
    logs_root: Path


def load_runtime_config(path: Path | None = None) -> RuntimeConfig:
    config_path = path or Path("configs/runtime.json")
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    return RuntimeConfig(
        database_path=Path(payload["database_path"]).expanduser(),
        data_root=Path(payload["data_root"]).expanduser(),
        documents_root=Path(payload["documents_root"]).expanduser(),
        logs_root=Path(payload["logs_root"]).expanduser(),
    )
