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

## Next Step

Once the structured rows are in SQLite, the next useful layer is a reporting/query script for:

- items by cluster
- items by topic
- items by meeting date
- first-pass weekly digest summaries
