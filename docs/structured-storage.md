# Structured Storage

## Goal

Persist parsed agenda items into stable local JSON artifacts so the project can query and summarize them before the SQLite path is finalized.

## Current Output

The `persist-items` CLI command writes:

- one structured document JSON per extracted text file
- one flat `agenda_items.index.json` file across all supplied documents

## Why This Exists

This gives the project a durable intermediate layer between:

- raw PDFs and extracted text
- eventual SQLite ingestion and reporting

It also avoids blocking on the current OneDrive-related SQLite write issue.

## Next Step

The next natural move after this layer is:

1. add a report script that groups items by topic and cluster
2. add SQLite import from the structured JSON index
3. start generating weekly digests from structured rows
