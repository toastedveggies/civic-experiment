# Download and Context Flow

## Goal

Take a saved LA County Gmail agenda message, extract linked agenda materials, download them, and store enough context to support the next analysis stage.

## Current Behavior

The `download-message-links` CLI command:

1. loads a saved Gmail message JSON file
2. runs the LA County GovDelivery adapter
3. filters for document-bearing links
4. downloads each target
5. writes sidecar metadata for each file
6. attempts PDF text extraction when `pypdf` is available

## Output Shape

By default, files are stored under:

```text
local/downloads/<message_id>/
```

For each downloaded file, the pipeline writes:

- the downloaded binary document
- a `.metadata.json` sidecar
- a `.txt` file when text extraction succeeds

## Current Categorization

Linked files are currently classified as:

- `board_agenda_page`
- `board_supporting_document`
- `cluster_agenda_packet`
- `agenda_packet`
- `linked_pdf`

## Next Layer

The next implementation step after this one should:

1. fetch the board agenda page HTML
2. extract supporting document PDF links from that page
3. enrich document records with item numbers and titles
4. store item-level extracted context for downstream analysis
