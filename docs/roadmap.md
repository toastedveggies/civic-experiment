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
- add issue-lens summaries that connect agenda items, findings, actors, and historical context
- add confidence and coverage indicators so analysis reflects parser/source completeness

## Phase 3: Additional Jurisdictions

- add City of Los Angeles sources
- validate multi-jurisdiction assumptions
- add source-specific adapters without changing core pipeline

## Phase 4: Dashboard And Operator Visibility

- dashboard summary query functions over SQLite
- source-health and parser-coverage views
- latest agenda/proceeding dates by source
- retry and manual-review queue visibility
- recent items and findings explorer
- local read API for dashboard data
- internal local dashboard prototype

## Phase 5: Operational Hardening

- scheduled local jobs
- reprocessing workflows
- data quality checks
- migration path toward always-on local deployment
- durable refresh-run records for dashboard status and audit trails

## Phase 6: Productization

- free public-awareness tier with basic agenda and item visibility
- pro analyst tier with issue lenses, history, risk scoring, and exports
- team tier with saved monitors, shared review state, custom sources, and integrations
- authentication, billing, and account-level data boundaries after the local dashboard proves the value
