# Source Registry

Each YAML file in this directory describes one tracked source.

The registry is meant to be stable across ingestion and analysis changes. Adapters should read source config rather than hard-code source behavior into the broader pipeline.

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
