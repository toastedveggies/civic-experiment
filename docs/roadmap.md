# Roadmap

## Phase 0: Foundation

- done: define repository structure
- done: define source registry format
- done: define schema for documents, items, findings, evidence, and trendlines
- done: create local database initialization path
- done: document onboarding workflow

## Phase 1: LA County V1

- done: add LA County source entries
- done: implement first Gmail-first ingestion adapter for observed LA County GovDelivery emails
- done: support linked document archiving and text extraction
- done: store structured document and item metadata as JSON and in SQLite companion tables
- in progress: generate item-level findings and batch memos

## Current Build Snapshot

- working Gmail message inspection for LA County agenda-related messages
- working resilient linked-PDF downloader with retry/manual-review queues
- working PDF text extraction on downloaded cluster packets
- working structured cluster agenda item extraction
- working JSON persistence for structured documents and item index
- working SQLite import into non-OneDrive local database
- working query and weekly digest commands over imported structured items

## Phase 2: Analytical Memory

- implement trendline storage and update rules
- track recurring entities, institutions, and vendors
- support longitudinal queries and richer weekly summaries
- add item-level findings generation
- add priority scoring and policy-significance ranking

## Phase 3: Additional Jurisdictions

- add City of Los Angeles sources
- validate multi-jurisdiction assumptions
- add source-specific adapters without changing core pipeline

## Phase 4: Operational Hardening

- scheduled local jobs
- reprocessing workflows
- data quality checks
- migration path toward always-on local deployment
- lightweight local API for future visual interface
