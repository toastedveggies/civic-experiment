"""PDF download functionality with rate limiting and resume support."""

import logging
from pathlib import Path
from urllib.parse import urlparse

from la_agendas.fetch import Fetcher
from la_agendas.parse import parse_date
from la_agendas.util import extract_filename, normalize_url

logger = logging.getLogger(__name__)


def download_pdfs(records: list[dict], outdir: Path, fetcher: Fetcher) -> None:
    """
    Download PDFs to outdir/pdfs/<group>/YYYY-MM-DD/filename.pdf.
    Skip if file already exists with same size.
    """
    pdf_dir = outdir / "pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)

    downloaded = 0
    skipped = 0
    errors = 0

    for record in records:
        url = record.get("url", "")
        group = record.get("group", "(unlabeled)").replace("/", "_")
        date = record.get("date", "unknown_date")
        filename = record.get("filename", extract_filename(url)) or "unknown.pdf"

        # Sanitize group name for filesystem
        group_safe = "".join(c for c in group if c.isalnum() or c in (" ", "-", "_")).strip()
        if not group_safe:
            group_safe = "unlabeled"

        # Create directory structure
        date_dir = pdf_dir / group_safe / date
        date_dir.mkdir(parents=True, exist_ok=True)

        file_path = date_dir / filename

        # Check if file already exists
        if file_path.exists():
            # Try to verify it's not zero-byte
            if file_path.stat().st_size > 0:
                logger.debug(f"Skipping existing file: {file_path}")
                skipped += 1
                continue

        # Download PDF
        try:
            logger.info(f"Downloading: {url} -> {file_path}")
            content_type, content = fetcher.fetch(url)

            # Verify it's a PDF (best effort)
            if "pdf" not in content_type.lower() and not url.lower().endswith(".pdf"):
                logger.warning(
                    f"Unexpected content-type {content_type} for {url}, saving anyway"
                )

            # Verify non-zero content
            if len(content) == 0:
                logger.warning(f"Zero-byte file downloaded from {url}, skipping")
                errors += 1
                continue

            # Write file
            file_path.write_bytes(content)
            downloaded += 1
            logger.debug(f"Downloaded {len(content)} bytes to {file_path}")

        except Exception as e:
            logger.error(f"Error downloading {url}: {e}")
            errors += 1

    logger.info(
        f"Download complete: {downloaded} downloaded, {skipped} skipped, {errors} errors"
    )

