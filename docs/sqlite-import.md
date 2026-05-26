# SQLite Import

## Goal

Load structured agenda document and item JSON into the live SQLite database without losing the richer parsed fields.

## Current Strategy

The importer writes to companion structured tables:

- `structured_documents`
- `structured_agenda_items`
- `structured_item_topics`

This preserves:

- cluster name
- meeting date display text
- normalized meeting date ISO
- section metadata
- speakers
- full text block
- topic tags

without forcing those fields awkwardly into the earliest core schema tables.

## Command

Use:

```text
policy-tracker import-structured-items <index_path>
```

It defaults to the runtime-configured database path in [configs/runtime.json](/C:/Users/ramor/OneDrive/Documents/GitHub/civic-experiment/configs/runtime.json).

## Current Status

The structured rows are already imported into the live SQLite companion tables.

The current importer also:

- ensures `meeting_date_iso` exists on structured document and item tables
- backfills `meeting_date_iso` from legacy `meeting_date` text when possible
- replaces stale structured item rows on re-import instead of accumulating duplicates

## Next Step

The next useful layer is a stronger meeting-aware reporting/query path for:

- items by cluster
- items by topic
- items by canonical meeting date
- supporting documents and minutes associated with a meeting
- parliamentary actions such as motion, second, and vote outcome
