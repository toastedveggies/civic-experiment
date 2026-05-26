# Structured Storage

## Goal

Persist parsed agenda items into stable local JSON artifacts so the project can query, validate, and re-import them as parser coverage improves.

## Current Output

The `persist-items` CLI command writes:

- one structured document JSON per extracted text file
- one flat `agenda_items.index.json` file across all supplied documents

## Why This Exists

This gives the project a durable intermediate layer between:

- raw PDFs and extracted text
- SQLite ingestion and reporting

It also gives the project a durable intermediate layer for:

- parser regression checks
- scratch refresh validation before live DB writes
- preserving cleaned structured output separately from raw extracted text

## Current Status

This layer is active and feeds the live SQLite import path.

Structured JSON outputs now carry fields including:

- meeting date display text
- normalized `meeting_date_iso`
- cleaned titles and text blocks
- topic tags

## Next Step

The next natural move after this layer is:

1. carry meeting linkage and document-role metadata into the structured JSON layer
2. add parliamentary action fields where proceedings or minutes expose them
3. keep meeting-centric validation checks aligned with the live SQLite import path
