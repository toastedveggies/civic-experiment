from __future__ import annotations

from pathlib import Path

from policy_tracker.models import SourceConfig

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - exercised via fallback path
    yaml = None


def _load_yaml_text(text: str) -> dict[str, object]:
    if yaml is not None:
        payload = yaml.safe_load(text)
        if not isinstance(payload, dict):
            raise ValueError("Source config must deserialize to a mapping.")
        return payload
    return _parse_simple_yaml_mapping(text)


def _parse_simple_yaml_mapping(text: str) -> dict[str, object]:
    result: dict[str, object] = {}
    lines = text.splitlines()
    index = 0

    while index < len(lines):
        raw_line = lines[index]
        line = raw_line.rstrip()
        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            index += 1
            continue

        if line.startswith("  - "):
            raise ValueError("Unexpected list item without a preceding key.")

        if ":" not in line:
            raise ValueError(f"Could not parse line: {line}")

        key, raw_value = line.split(":", 1)
        key = key.strip()
        value = raw_value.strip()

        if value == "":
            items: list[str] = []
            lookahead = index + 1
            while lookahead < len(lines):
                next_line = lines[lookahead]
                next_stripped = next_line.strip()
                if not next_stripped or next_stripped.startswith("#"):
                    lookahead += 1
                    continue
                if next_line.startswith("  - "):
                    items.append(next_line[4:].strip())
                    lookahead += 1
                    continue
                break

            if items:
                result[key] = items
                index = lookahead
                continue

            result[key] = ""
            index += 1
            continue

        if value == "[]":
            result[key] = []
        elif value == "null":
            result[key] = None
        elif value == ">":
            chunks: list[str] = []
            lookahead = index + 1
            while lookahead < len(lines):
                next_line = lines[lookahead]
                if next_line.startswith("  "):
                    chunks.append(next_line.strip())
                    lookahead += 1
                    continue
                break
            result[key] = " ".join(chunks)
            index = lookahead
            continue
        else:
            result[key] = value

        index += 1

    return result


def load_source_config(path: Path) -> SourceConfig:
    payload = _load_yaml_text(path.read_text(encoding="utf-8"))
    return SourceConfig(**payload)


def load_source_configs(config_dir: Path) -> list[SourceConfig]:
    return [load_source_config(path) for path in sorted(config_dir.glob("*.yaml"))]


def get_source_config(config_dir: Path, source_id: str) -> SourceConfig:
    for config in load_source_configs(config_dir):
        if config.source_id == source_id:
            return config
    raise KeyError(f"Unknown source_id: {source_id}")
