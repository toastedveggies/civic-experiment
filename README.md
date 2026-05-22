# Policy Tracker

Policy Tracker is a local-first document intelligence system for tracking agendas, attachments, and policy actions across public-sector bodies over time.

The first implementation target is Los Angeles County agenda materials. The architecture is designed so we can later add City of Los Angeles, regional agencies, and additional jurisdictions without rebuilding the pipeline.

The intended end-state is a system that harvests agenda emails and linked supporting documents from your Gmail on a schedule, archives them locally, and analyzes them for both current developments and trends over time.

## What This Repo Contains

- source registry and source onboarding docs
- Python package for ingestion, extraction, analysis, and reporting workflows
- SQLite-first schema and initialization scripts
- prompt and taxonomy files for structured policy analysis
- documentation for trend tracking and longitudinal memory

## Design Goals

- separate collection from analysis
- preserve raw files and extracted text
- keep findings traceable to source documents
- make source onboarding a first-class workflow
- support incremental updates and longitudinal memory
- stay local-first and operationally simple

## Planned V1 Scope

- LA County source registry entries
- local and eventually scheduled ingestion workflow for Gmail-delivered agenda documents and linked supporting materials
- normalized document metadata and archive conventions
- SQLite storage for documents, agenda items, findings, evidence, and trendlines
- staged AI analysis pipeline for current-item review and longitudinal trend tracking
- weekly digest and batch memo outputs

## Repo Layout

- `src/policy_tracker/`: Python package
- `configs/sources/`: source registry entries
- `docs/`: architecture, onboarding, and roadmap docs
- `sql/`: schema and migration files
- `prompts/`: reusable analysis prompts
- `scripts/`: local setup and operational scripts
- `tests/`: test suite

## Local Data Strategy

Raw documents, extracted text, local databases, and logs should live outside Git or be Git-ignored. See `.gitignore` and [docs/architecture.md](/C:/Users/ramor/OneDrive/Documents/GitHub/civic-experiment/docs/architecture.md) for the intended split between code and local data.

If this repo stays inside a live-synced OneDrive folder, it is safer to keep the SQLite database in a separate non-synced local path. SQLite file writes can be unreliable in some synced directories.

The current runtime config points the live SQLite database to [configs/runtime.json](/C:/Users/ramor/OneDrive/Documents/GitHub/civic-experiment/configs/runtime.json), which uses `C:\Users\ramor\AppData\Local\policy-tracker\policy_tracker.sqlite`.

## Current Status

This repo is now the real implementation project.

Current working status:

- LA County Gmail intake pattern is implemented for GovDelivery agenda emails
- linked agenda PDFs can be categorized and downloaded with retry/manual-review states
- downloaded PDFs can be text-extracted
- extracted cluster agenda text can be parsed into structured agenda items
- structured items can be persisted to JSON and imported into SQLite
- query and digest commands now work against the live SQLite database

Current live data snapshot:

- live SQLite DB: `C:\Users\ramor\AppData\Local\policy-tracker\policy_tracker.sqlite`
- imported structured documents: `3`
- imported structured agenda items: `22`
- imported structured topic links: `43`

For the best current handoff docs, see:

- [docs/build-status.md](/C:/Users/ramor/OneDrive/Documents/GitHub/civic-experiment/docs/build-status.md)
- [docs/product-plan.md](/C:/Users/ramor/OneDrive/Documents/GitHub/civic-experiment/docs/product-plan.md)
