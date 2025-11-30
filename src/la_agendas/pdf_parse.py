"""PDF text extraction."""

import logging
from pathlib import Path
from typing import List

import pandas as pd
from pypdf import PdfReader

logger = logging.getLogger(__name__)


def parse_pdfs(pdf_dir: Path, outdir: Path) -> None:
    """
    Extract text from all PDFs in pdf_dir and write structured output.
    Directory structure expected: pdf_dir/<group>/<date>/<filename>.pdf
    """
    records = []

    # Walk directory structure: group/date/filename.pdf
    for group_dir in pdf_dir.iterdir():
        if not group_dir.is_dir():
            continue
        group = group_dir.name

        for date_dir in group_dir.iterdir():
            if not date_dir.is_dir():
                continue
            date = date_dir.name

            for pdf_file in date_dir.glob("*.pdf"):
                record = extract_pdf_text(pdf_file, group, date)
                if record:
                    records.append(record)

    if not records:
        logger.warning("No PDFs found to parse")
        return

    # Write to CSV
    df = pd.DataFrame(records)
    columns = [
        "group",
        "date",
        "link_text",
        "url",
        "filename",
        "local_path",
        "text",
        "page_count",
        "extraction_status",
    ]
    # Ensure all columns exist
    for col in columns:
        if col not in df.columns:
            df[col] = ""

    df = df[columns]
    outfile = outdir / "pdf_text_extracted.csv"
    df.to_csv(outfile, index=False)
    logger.info(f"Wrote {len(df)} records to {outfile}")

    # Also write as JSONL for easier processing
    jsonl_file = outdir / "pdf_text_extracted.jsonl"
    df.to_json(jsonl_file, orient="records", lines=True)
    logger.info(f"Wrote {len(df)} records to {jsonl_file}")


def extract_pdf_text(pdf_path: Path, group: str, date: str) -> dict | None:
    """
    Extract text from a single PDF file.
    Returns dict with extraction results or None on error.
    """
    try:
        reader = PdfReader(str(pdf_path))
        page_count = len(reader.pages)

        # Extract text from all pages
        text_parts = []
        for page in reader.pages:
            try:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            except Exception as e:
                logger.warning(f"Error extracting text from page in {pdf_path}: {e}")

        full_text = "\n\n".join(text_parts)
        extraction_status = "success" if full_text.strip() else "empty"

        # Try to extract metadata
        metadata = reader.metadata or {}
        link_text = metadata.get("/Title", "") or pdf_path.stem
        url = ""  # Not available from file system

        return {
            "group": group,
            "date": date,
            "link_text": link_text,
            "url": url,
            "filename": pdf_path.name,
            "local_path": str(pdf_path),
            "text": full_text,
            "page_count": page_count,
            "extraction_status": extraction_status,
        }

    except Exception as e:
        logger.error(f"Error parsing PDF {pdf_path}: {e}")
        return {
            "group": group,
            "date": date,
            "link_text": pdf_path.stem,
            "url": "",
            "filename": pdf_path.name,
            "local_path": str(pdf_path),
            "text": "",
            "page_count": 0,
            "extraction_status": f"error: {str(e)}",
        }

