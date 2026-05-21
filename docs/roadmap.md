# Roadmap

## Phase 0: Foundation

- define repository structure
- define source registry format
- define schema for documents, items, findings, evidence, and trendlines
- create local database initialization path
- document onboarding workflow

## Phase 1: LA County V1

- add LA County source entries
- implement first ingestion adapter(s)
- support document archiving and text extraction
- store structured document and item metadata
- generate item-level findings and batch memos

## Phase 2: Analytical Memory

- implement trendline storage and update rules
- track recurring entities, institutions, and vendors
- support longitudinal queries and weekly summaries

## Phase 3: Additional Jurisdictions

- add City of Los Angeles sources
- validate multi-jurisdiction assumptions
- add source-specific adapters without changing core pipeline

## Phase 4: Operational Hardening

- scheduled local jobs
- reprocessing workflows
- data quality checks
- migration path toward always-on local deployment
