# Build Status

## Current State

The project is now beyond scaffolding. It has a working LA County pipeline, a working LA City historical backfill path, and a new LA City email-ingest path for ongoing Clerk notices.

It also now has a working LA County CEO archive downloader for the last 12 months of selected cluster and commission agendas, plus a first structured-import pass over those PDFs.

The target operating model is:

- harvest agenda-related emails from Gmail on a schedule
- follow links to agenda packets and supporting documents
- archive and structure those materials locally
- analyze new materials for current high-signal developments
- accumulate trend memory over time

## What Works Now

### Source intake

- LA County GovDelivery-style Gmail agenda message parsing
- LA City Clerk listserv Gmail notice parsing from `.htm` attachments
- LA County CEO agendas page archive scraping for selected bodies
- support for:
  - board agenda emails
  - supplemental agenda emails
  - agenda spotlight emails
  - cluster meeting agenda emails
  - PrimeGov-linked City Council and committee notice emails
  - CEO archive PDFs for cluster, homeless-alignment, housing, and commission bodies

### Link handling and download

- GovDelivery tracking-link unwrapping
- categorization of board pages vs direct PDFs
- resilient download flow with:
  - `ready`
  - `downloaded_without_text`
  - `needs_retry`
  - `download_failed`
  - `manual_review_queue`
  - `retry_queue`

### Text and structure extraction

- PDF text extraction on downloaded cluster packets
- structured agenda item extraction for LA County cluster agenda text
- structured agenda item extraction for LA City PrimeGov HTML agendas
- item fields currently captured:
  - cluster name
  - meeting date
  - section metadata
  - item label
  - item type
  - title
  - speakers
  - text block
  - coarse topic tags

### Persistence

- structured document JSON output
- flat agenda item JSON index
- SQLite import into companion structured tables
- archival of LA City email notice attachments alongside fetched PrimeGov meeting HTML
- archival of LA County CEO agenda PDFs plus extracted text and manifest metadata

### Query/report layer

- `list-items`
- `weekly-digest`
- `generate-findings`
- `refresh-source`
- `ingest-gmail-message`
- topic, cluster, meeting-date, search, and limit filters

## Current Workspace Snapshot

- path: `C:\Users\ramor\AppData\Local\policy-tracker\policy_tracker.sqlite`
- LA City structured item index: `local/structured/la_city_agendas/agenda_items.index.json`
- LA City structured items in index: `2,188`
- LA City structured document JSON files in workspace: `372`
- LA City downloads root present: `local/downloads/la_city_agendas`
- LA County CEO documents downloaded: `324`
- LA County CEO structured documents imported: `229`
- LA County CEO structured agenda items imported: `961`
- LA County CEO manifest: `local/downloads/la_county_ceo_agendas/ceo_last_12_months_manifest.json`
- LA County BOS SOP PDFs downloaded: `48`
- LA County BOS SOP extracted text files: `48`
- LA County BOS SOP documents imported into live DB: `48`
- LA County BOS SOP date range in DB: `2025-05-27` through `2026-05-06`
- LA County BOS SOP manifest: `local/downloads/la_county_bos_sop/bos_sop_last_12_months_manifest.json`

## BOS Historical Note

- the live BOS agenda page at `bos.lacounty.gov/board-meeting-agendas/` is a Nuxt app that only exposes a short recent window and is not a reliable sole source for a 12-month backfill
- a BOS Wayback reconstruction scaffold exists in [src/policy_tracker/la_county_bos_import.py](/C:/Users/ramor/OneDrive/Documents/GitHub/civic-experiment/src/policy_tracker/la_county_bos_import.py)
- `55` archived BOS page snapshots were saved locally under [local/tmp_bos_snapshots](/C:/Users/ramor/OneDrive/Documents/GitHub/civic-experiment/local/tmp_bos_snapshots)
- that BOS-page path is now considered a fallback/reference path, not the main historical import route
- the preferred BOS historical source is the LA County Statement of Proceedings archive, which is backed by the SOP portal search index and is better suited to repeatable backfill work
- that SOP path is now working for raw historical backfill; the current result is `48` BOS Statement of Proceedings PDFs for the last 12 months

## Important Local Paths

- runtime config: [configs/runtime.json](/C:/Users/ramor/OneDrive/Documents/GitHub/civic-experiment/configs/runtime.json)
- live structured JSON index: [local/structured/live_test/agenda_items.index.json](/C:/Users/ramor/OneDrive/Documents/GitHub/civic-experiment/local/structured/live_test/agenda_items.index.json)
- live downloaded PDFs/text: [local/downloads/live_test](/C:/Users/ramor/OneDrive/Documents/GitHub/civic-experiment/local/downloads/live_test)
- LA City structured output: [local/structured/la_city_agendas](/C:/Users/ramor/OneDrive/Documents/GitHub/civic-experiment/local/structured/la_city_agendas)
- LA City download archive: [local/downloads/la_city_agendas](/C:/Users/ramor/OneDrive/Documents/GitHub/civic-experiment/local/downloads/la_city_agendas)
- LA County CEO structured output: [local/structured/la_county_ceo_agendas](/C:/Users/ramor/OneDrive/Documents/GitHub/civic-experiment/local/structured/la_county_ceo_agendas)
- LA County CEO download archive: [local/downloads/la_county_ceo_agendas](/C:/Users/ramor/OneDrive/Documents/GitHub/civic-experiment/local/downloads/la_county_ceo_agendas)

## Known Gaps

- no scheduled Gmail harvest job yet
- no mailbox-to-repo export automation yet for live Gmail connector intake
- no true board-agenda-page crawler yet for broader supporting-document expansion
- BOS page reconstruction exists only as a partial scaffold and should not be reworked first; use the Statement of Proceedings archive for BOS historical backfill
- BOS Statement of Proceedings are in the DB as raw documents with extracted text, but not yet parsed into structured agenda-item tables
- no trendline memory updater yet
- topic tagging is still heuristic and intentionally coarse
- no visual interface yet
- some temporary test-output directories may remain due to Windows/OneDrive file locks
- the LA County CEO pull is only partially structured today:
  - `95` downloaded PDFs remain unparsed into structured items
  - the misses are mostly repeatable format families, not one-off failures

## Best Next Steps

1. handle LA County CEO `cancellation_notice` files as intentional non-item documents instead of parser misses
2. extend the County parser for `county_cluster_motion_line_variant` agendas
3. add a `regional_homeless_alignment_brown_act_agenda` parser family
4. add a `homeless_policy_deputies_virtual_agenda` parser family
5. connect the live Gmail connector output to the new `ingest-gmail-message` flow for LA City notices
6. use the SOP archive, not the live BOS page, for the first Board of Supervisors historical backfill
7. add a BOS Statement of Proceedings parser family so those `48` Board records can be converted into structured items
