# Policy Tracker

Policy Tracker is a local-first document intelligence system for tracking agendas, attachments, and policy actions across public-sector bodies over time.

The repo started with Los Angeles County agenda materials, and now also includes a real City of Los Angeles intake path. The architecture is designed so we can keep adding new agenda families and jurisdictions without rebuilding the pipeline each time.

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

- LA County Gmail intake is implemented for GovDelivery agenda emails
- LA City historical PrimeGov agendas have been downloaded, archived, and parsed into structured items
- LA City Gmail notice intake is now implemented for Clerk listserv `.htm` attachments that point to PrimeGov meeting pages
- LA County CEO archive agendas for selected bodies have been downloaded and loaded into the live database
- attachment-aware source adapters and parser dispatch are in place, so new source families can plug into the same shared pipeline
- low-value screening is now built into refresh so duplicate companions and cancellation notices stop inflating parser backlog
- linked agenda documents can be downloaded, text-extracted, structured, and imported into SQLite
- query, digest, and findings commands now work against the live SQLite database

Current live data snapshot:

- live SQLite DB: `C:\Users\ramor\AppData\Local\policy-tracker\policy_tracker.sqlite`
- raw documents in live DB: `743`
- structured documents in live DB: `445`
- structured agenda items in live DB: `3,410`
- structured item topics in live DB: `4,781`
- LA City raw documents / structured items: `371` / `2,188`
- LA County CEO raw documents / structured items: `324` / `1,136`
- LA County BOS Statement of Proceedings raw documents / structured items: `48` / `58`

Current BOS note:

- the public BOS agenda page is a Nuxt app that only exposes a short rolling window on the live site
- a Wayback-based BOS page backfill scaffold exists, and `55` archived page snapshots were saved locally for reference
- that path is not the preferred historical import route now
- the County Statement of Proceedings archive is now the preferred BOS historical source, and the last 12 months of BOS SOP PDFs have been downloaded and imported as raw documents

Current parser backlog highlight:

- the remaining unstructured set is not all true parser debt
- a large share of remaining LA City misses are low-value companion files where richer HTML twins already exist
- the next planning step is to separate:
  - low-value/non-item documents that should be screened out or downgraded
  - substantive documents that need broader parser-family coverage
- current substantive parser backlog is concentrated in:
  - housing committee and LACDA board-deputies packets
  - residual BOS Statement of Proceedings shapes that still defeat the current parser pass
  - residual LA County CEO outliers, especially `real-estate-management-commission` and linked supporting-document families
- the next structural step is to move toward a meeting-centric model so we can:
  - link agendas, minutes, and supporting docs to the meeting they describe
  - normalize parliamentary actions such as motion, second, final action, and vote tally
  - keep display dates alongside canonical values like `meeting_date_iso`

Parser instruction reference:

- parser-family extensions should preserve display date text in `meeting_date` and separately emit canonical normalized values in `meeting_date_iso`
- if normalization is uncertain, leave `meeting_date_iso` empty rather than guessing
- shared parser guidance lives in [docs/item-extraction.md](/C:/Users/ramor/OneDrive/Documents/GitHub/civic-experiment/docs/item-extraction.md)

For the best current handoff docs, see:

- [docs/build-status.md](/C:/Users/ramor/OneDrive/Documents/GitHub/civic-experiment/docs/build-status.md)
- [docs/product-plan.md](/C:/Users/ramor/OneDrive/Documents/GitHub/civic-experiment/docs/product-plan.md)
- [docs/item-extraction.md](/C:/Users/ramor/OneDrive/Documents/GitHub/civic-experiment/docs/item-extraction.md)
- [docs/issue-scanning.md](/C:/Users/ramor/OneDrive/Documents/GitHub/civic-experiment/docs/issue-scanning.md)
- [docs/meeting-centric-model.md](/C:/Users/ramor/OneDrive/Documents/GitHub/civic-experiment/docs/meeting-centric-model.md)
