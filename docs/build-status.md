# Build Status

## Current State

The project is now beyond scaffolding. It has a working LA County v1 pipeline for a first real source family and a live non-OneDrive SQLite database.

The target operating model is:

- harvest agenda-related emails from Gmail on a schedule
- follow links to agenda packets and supporting documents
- archive and structure those materials locally
- analyze new materials for current high-signal developments
- accumulate trend memory over time

## What Works Now

### Source intake

- LA County GovDelivery-style Gmail agenda message parsing
- support for:
  - board agenda emails
  - supplemental agenda emails
  - agenda spotlight emails
  - cluster meeting agenda emails

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

### Query/report layer

- `list-items`
- `weekly-digest`
- topic, cluster, meeting-date, search, and limit filters

## Current Live Database

- path: `C:\Users\ramor\AppData\Local\policy-tracker\policy_tracker.sqlite`
- structured documents imported: `3`
- structured agenda items imported: `22`
- structured item topics imported: `43`

## Important Local Paths

- runtime config: [configs/runtime.json](/C:/Users/ramor/OneDrive/Documents/GitHub/civic-experiment/configs/runtime.json)
- live structured JSON index: [local/structured/live_test/agenda_items.index.json](/C:/Users/ramor/OneDrive/Documents/GitHub/civic-experiment/local/structured/live_test/agenda_items.index.json)
- live downloaded PDFs/text: [local/downloads/live_test](/C:/Users/ramor/OneDrive/Documents/GitHub/civic-experiment/local/downloads/live_test)

## Known Gaps

- no scheduled Gmail harvest job yet
- no true board-agenda-page crawler yet for supporting-document expansion
- no full item-level findings generation yet
- no trendline memory updater yet
- topic tagging is still heuristic and intentionally coarse
- no visual interface yet
- some temporary test-output directories may remain due to Windows/OneDrive file locks

## Best Next Steps

1. build a first item-level findings generator
2. add scheduled Gmail harvest and repeatable refresh workflow
3. add stronger taxonomy and priority scoring
4. add a lightweight local read API for future UI work
5. expand LA County coverage from cluster packets to broader board supporting documents
