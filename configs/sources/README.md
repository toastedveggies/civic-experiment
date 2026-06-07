# Source Registry

Each YAML file in this directory describes one active or near-active ingestion
source.

The registry is meant to be stable across ingestion and analysis changes. Adapters should read source config rather than hard-code source behavior into the broader pipeline.

For the broader inventory of public bodies and all known online locations, use
`configs/source_log.yaml`. The source log is intentionally wider than this
directory: it can include candidate sources, backstops, historical archives,
public APIs, and listserv sources before they are ready for pipeline ingestion.

## Required Fields

- `source_id`
- `source_name`
- `jurisdiction`
- `government_level`
- `body_name`
- `source_type`
- `collection_method`
- `priority_level`
- `status`

## Optional Fields

- `base_url`
- `email_sender_patterns`
- `attachment_patterns`
- `meeting_frequency`
- `tags`
- `notes`
- `adapter`
- `parser`
- `gmail_query`
- `download_root`
- `structured_output_dir`

## Gmail-Automation Fields

These optional fields are useful when a source is harvested through the connected Gmail workflow:

- `gmail_query`: preferred Gmail search query for scheduled scans
- `download_root`: source-specific local landing zone for downloaded PDFs/text
- `structured_output_dir`: source-specific directory for structured JSON output

Adapters can now support more than body-link parsing. For example, LA County currently uses a body-link Gmail adapter, while LA City uses an attachment-aware adapter that reads Clerk `.htm` notices, extracts PrimeGov meeting links, and then hands the fetched HTML to a source-specific parser family.

## Parser Planning Notes

- the `parser` field should point to the canonical parser family for the source's best parse target
- sources may still archive multiple renditions of the same meeting, but not every rendition should count as parser debt
- low-value artifacts such as cancellation notices or duplicate PDF/plain-text companions should stay in `documents` while being screened out from structured-coverage goals
- parser comprehensiveness should be measured against substantive agenda/proceeding families, not every archived file variant
