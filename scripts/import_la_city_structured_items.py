from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from policy_tracker.item_extraction import LA_CITY_PRIMEGOV_HTML_PARSER
from policy_tracker.sqlite_import import import_items_index
from policy_tracker.storage import (
    build_items_index,
    materialize_structured_document,
    write_items_index,
    write_structured_document,
)


def main() -> int:
    text_paths = sorted(
        path
        for path in (REPO_ROOT / "local" / "downloads" / "la_city_agendas" / "primegov").rglob("*_html-*.txt")
        if path.is_file()
    )
    documents = [
        materialize_structured_document(path, parser_name=LA_CITY_PRIMEGOV_HTML_PARSER)
        for path in text_paths
    ]
    documents = [document for document in documents if document.item_count > 0]

    output_dir = REPO_ROOT / "local" / "structured" / "la_city_agendas"
    output_dir.mkdir(parents=True, exist_ok=True)
    for document in documents:
        output_path = output_dir / f"{Path(document.source_path).stem}.structured.json"
        write_structured_document(document, output_path)

    rows = build_items_index(documents)
    index_path = output_dir / "agenda_items.index.json"
    write_items_index(rows, index_path)
    import_summary = import_items_index(index_path=index_path, source_id="la_city_agendas")
    print(
        json.dumps(
            {
                "documents_structured": len(documents),
                "items_structured": len(rows),
                "index_path": str(index_path.resolve()),
                "import_summary": import_summary,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
