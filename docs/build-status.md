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
- structured agenda item extraction for County CEO regional homeless alignment Brown Act agendas
- first-pass structured extraction for BOS Statement of Proceedings text
- refresh-time screening for low-value artifacts:
  - cancellation notices
  - non-canonical LA City PDF/plain-text companions when richer HTML twins exist
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
- raw documents in live DB: `743`
- structured documents in live DB: `430`
- structured agenda items in live DB: `3,395`
- structured item topics in live DB: `4,730`
- LA City structured item index: `local/structured/la_city_agendas/agenda_items.index.json`
- LA City structured items in index: `2,188`
- LA City structured document JSON files in workspace: `372`
- LA City downloads root present: `local/downloads/la_city_agendas`
- LA County CEO documents downloaded: `324`
- LA County CEO structured documents imported: `250`
- LA County CEO structured agenda items imported: `1,136`
- LA County CEO manifest: `local/downloads/la_county_ceo_agendas/ceo_last_12_months_manifest.json`
- LA County BOS SOP PDFs downloaded: `48`
- LA County BOS SOP extracted text files: `48`
- LA County BOS SOP documents imported into live DB: `48`
- LA County BOS SOP structured documents imported: `21`
- LA County BOS SOP structured agenda items imported: `39`
- LA County BOS SOP date range in DB: `2025-05-27` through `2026-05-06`
- LA County BOS SOP manifest: `local/downloads/la_county_bos_sop/bos_sop_last_12_months_manifest.json`
- LA City refresh screening baseline:
  - canonical parse candidates: `165`
  - screened out: `207`
  - breakdown: `164` non-canonical companions, `43` cancellation notices
- LA County CEO refresh screening baseline:
  - canonical parse candidates: `288`
  - screened out: `36` cancellation notices

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
- no trendline memory updater yet
- topic tagging is still heuristic and intentionally coarse
- no visual interface yet
- some temporary test-output directories may remain due to Windows/OneDrive file locks
- the remaining unstructured corpus now needs to be split into two categories:
  - low-value or non-item artifacts that should not be treated as parser failures
  - substantive agenda/proceeding formats that need parser-family expansion

## Current Unstructured Classification

- LA City screened refresh baseline:
  - canonical parse candidates: `165`
  - screened out low-value files: `207`
  - most remaining substantive gaps are HTML cancellation/continuation/special variants
- LA County CEO remaining raw-with-text but not structured: `74`
  - `36` cancellation notices
  - `18` homelessness and housing virtual agenda format
  - `9` residual other/outlier misses
  - `6` regional homeless alignment leftovers
  - `5` housing committee / LACDA board-deputies packet formats
- LA County BOS SOP remaining raw-with-text but not structured: `27`
  - mostly Statement of Proceedings parser misses on available text
  - at least one file appears to have first-page-only or otherwise degraded extraction

## Data Hygiene Priorities

- normalize structured meeting dates to a canonical ISO field like `meeting_date_iso`
- preserve original display date text separately from normalized dates
- normalize body/cluster names to a canonical form across parser families
- add or normalize document status fields such as `active`, `cancelled`, `revised`, and `continued`
- improve title cleaning so docket ids, page headers/footers, and attachment boilerplate do not leak into item titles
- keep cleaned item text separate from raw extracted source text when practical

Parser-build reference:
- future parser work should preserve display date text in `meeting_date`, emit canonical ISO values in `meeting_date_iso` when confidently derivable, and leave the ISO field empty rather than guessing
- use the shared helper in [src/policy_tracker/date_utils.py](/C:/Users/ramor/OneDrive/Documents/GitHub/civic-experiment/src/policy_tracker/date_utils.py:14) and the standing parser guidance in [docs/item-extraction.md](/C:/Users/ramor/OneDrive/Documents/GitHub/civic-experiment/docs/item-extraction.md)

## Screening Rules To Add

- do not count LA City PDF/plain-text agenda companions as parser debt when a richer `_html-*.txt` twin exists
- treat cancellation notices and other non-item meeting-status documents as intentional document outcomes, not failed structured parses
- preserve low-value companion files in `documents`, but exclude them from parser-backlog metrics and policy-scan expectations
- prefer one canonical parse target per meeting when multiple source renditions exist

## Best Next Steps

1. add structured date normalization and canonical metadata hygiene, especially `meeting_date_iso`
2. add a homelessness and housing virtual agenda parser family
3. improve BOS Statement of Proceedings parsing and text-normalization coverage
4. handle housing/LACDA packet formats and County CEO residual outliers
5. connect the live Gmail connector output to the new `ingest-gmail-message` flow for LA City notices
