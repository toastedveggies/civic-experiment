# Resilience Layer

## Goal

Make document ingestion durable even when downloads fail, PDFs are malformed, or text extraction is unavailable.

## Status Model

Each document target now ends in a visible state:

- `ready`
- `downloaded_without_text`
- `needs_retry`
- `download_failed`

Each document also carries a review state:

- `not_needed`
- `needs_manual_review`

## Failure Handling

### Fetch failures

For each target:

1. attempt download
2. retry up to `max_fetch_attempts`
3. classify the failure as retryable or non-retryable
4. write a failure record instead of silently dropping the target

### Extraction failures

If a PDF downloads but text extraction cannot run or returns no usable text:

- keep the PDF
- keep the metadata
- mark the item `downloaded_without_text`
- queue it for manual review

## Queue Files

Each manifest directory now includes:

- `manifest.json`
- `retry_queue.json`
- `manual_review_queue.json`

This gives the system a clean operational handoff instead of hiding failures inside logs.

## Backup Role

The intended workflow is:

1. automation handles the normal path
2. retry queue handles transient fetch problems
3. manual review queue handles stubborn PDFs or weak extraction
4. targeted human or AI review handles the exceptions

That means the backup plan is built into the pipeline rather than improvised after failure.
