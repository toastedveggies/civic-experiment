# Architecture Overview

## Goal

Build a local-first policy-tracking system that can ingest public-sector agenda materials, extract structured findings, and maintain durable analytical memory across jurisdictions.

## Core Layers

### 1. Source Registry

Stores source definitions independent of ingestion logic.

Examples:

- LA County Board agenda emails
- agency agenda webpages
- manual uploads for one-off document sets

The registry should answer:

- what this source is
- how documents arrive
- how we collect them
- how high-priority the source is
- what parser or adapter it needs

### 2. Ingestion Adapters

Adapters handle source-specific retrieval and normalization.

Responsibilities:

- collect messages, links, or files
- normalize filenames
- store metadata
- deduplicate by hash
- preserve relationships between parent agenda packets and attachments

### 3. Archive and Metadata Store

The archive layer keeps:

- raw files
- extracted text
- OCR outputs when needed
- source metadata
- parent/child relationships

Raw data should be local and Git-ignored.

### 4. AI Analysis Pipeline

Analysis should be staged:

1. intake classification
2. item extraction
3. policy analysis
4. cross-document synthesis
5. memory update

This keeps prompts smaller, makes outputs easier to validate, and allows later reprocessing without recollecting files.

### 5. Reporting and Longitudinal Memory

The reporting layer should support:

- item-level findings
- batch memos
- weekly digests
- monthly trend summaries
- issue/entity/jurisdiction search

Memory records should compress prior findings so future reviews do not require re-reading the full archive.

## Local-First Runtime Model

Initial runtime assumptions:

- Python scripts for orchestration
- SQLite for v1 storage
- config files in YAML
- prompts in Markdown
- scheduled local jobs later

Practical note:

- prefer storing the live SQLite database in a non-synced local path if the repo lives inside OneDrive, because synced folders can cause SQLite disk I/O issues
- keep the runtime path in repo config, but keep the actual database file in a non-OneDrive location such as `AppData\Local`

Planned migration path:

- SQLite to Postgres
- local workstation to always-on mini PC or laptop server
- scripts to lightweight internal API when justified

## Proposed Local Data Layout

Example non-Git data layout:

```text
local/
  raw/
    <source_id>/
      2026/
        2026-05-20/
  text/
    <document_id>.txt
  ocr/
    <document_id>.txt
  reports/
  db/
    policy_tracker.sqlite
  logs/
```

## Boundary Between Generic and Source-Specific Logic

Keep source-specific quirks in:

- source configs
- source adapters
- source parsers

Keep generic logic in:

- shared metadata models
- hashing and dedupe
- storage
- taxonomy
- analysis prompts
- reporting

## Near-Term Build Order

1. finalize source registry format
2. create SQLite schema
3. implement local database initialization
4. add first LA County source configs
5. implement initial ingestion adapter interface
6. add analysis prompt templates
7. add reporting and trend-memory workflows
