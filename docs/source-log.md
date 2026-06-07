# Source Log

The project now keeps two related but separate records:

- `configs/source_log.yaml`: broad inventory of public bodies and where their public records live.
- `configs/sources/*.yaml`: active ingestion configs used by the pipeline.

This distinction matters as the system grows. A body may have multiple public locations: a live agenda page, an archive, a public API, a listserv notice, a document portal, and a minutes/proceedings archive. Not all of those should become active ingestion sources immediately, but all of them should be logged.

## Operating Model

Use the source log to answer:

- What public body are we tracking?
- Where does that body publish agendas, minutes, proceedings, packets, staff reports, and supporting documents?
- Which source is primary versus a backstop?
- Which sources are active, candidates, deprecated, or still under review?
- What is the expected check cadence?
- What parser or adapter will likely be needed?

Use active source configs to answer:

- How does the current pipeline collect from this source?
- Which parser is used for canonical text artifacts?
- Where do local downloads and structured JSON outputs go?
- What Gmail query or source-specific adapter is currently wired up?

## Source Roles

- `primary`: preferred online source for scheduled checks.
- `secondary`: useful, but not complete enough to stand alone.
- `alert_backstop`: email/listserv or notification source that catches changes or links.
- `historical_backfill`: best source for older records.
- `reference_only`: useful for manual review, not planned for ingestion yet.

## Adding A New Public Body

1. Add a `body_id` entry under `bodies`.
2. List every known online/public source under that body, even if it is not ready to ingest.
3. Add matching entries under `sources`.
4. Pick the likely `collection_role` for each source.
5. Only add `configs/sources/<source_id>.yaml` when a source is ready for actual ingestion.
6. Keep Gmail/listserv sources as alerts unless the public web source is unreliable or unavailable.

## Minimum New Source Fields

Each new source-log entry should capture:

- `source_ref`
- `source_name`
- `status`
- `activation_stage`
- `collection_role`
- `source_type`
- `source_shape`
- `access_model`
- `public_urls`
- `schedule`
- `freshness`
- `current_notes`
- `gaps`

When known, also add:

- `current_source_id`
- `gmail_query`
- `local_download_root`
- `parser`
- `known_document_types`

## Structured Metadata To Keep

The log should carry enough structure for an agent to activate a source without rediscovering basics every time.

Identity:

- stable `source_ref`
- optional active pipeline `current_source_id`
- body links through `bodies[].sources`
- jurisdiction, government level, parent body, and issue tags

Access:

- public URLs and API endpoints
- `access_model`, such as anonymous public access, email subscription, API key, or login-required
- source shape, such as public API, JavaScript app, document portal, search index, or PDF archive
- known rate-limit, robots, or session quirks when discovered

Artifacts:

- `artifact_types`, such as agenda, minutes, staff report, board letter, motion, contract, budget document, public comment, cancellation notice, or supplemental agenda
- canonical artifact choice
- companion/supporting/low-value artifact rules
- dedupe keys, such as `meetingTemplateId`, portal document id, source URL, meeting date, or SHA-256

Freshness:

- last successful check
- last successful import
- latest imported meeting date
- last failure and retry posture
- expected cadence and lookback window

Activation:

- `activation_stage`
- `adapter_candidate`
- parser candidate
- local download root
- activation checks
- known blockers

Provenance:

- source URL
- fetched timestamp
- original email metadata where relevant
- body name
- meeting date
- hash
- upstream ids such as meeting id, template id, document id, or portal result id

## Agent Activation Pattern

When I need to activate or refresh sources, I should:

1. Read `configs/source_log.yaml`.
2. Find sources with `activation_stage: ready_for_activation` or active sources with stale freshness.
3. Check `access_model`, `source_shape`, `schedule`, and `activation_checks`.
4. Create or update the active ingestion config only when the source has enough metadata to run.
5. Save artifacts under the configured `local_download_root`.
6. Update `freshness`, `last_failure`, and any manual-review notes after the run.

This keeps the source log as the control plane and the ingestion configs as execution details.

## CLI Commands

The source log has operational commands:

- `policy-tracker validate-source-log`
- `policy-tracker list-source-log`
- `policy-tracker sync-source-config <source_ref> --write`
- `policy-tracker activate-source <source_ref> --write`
- `policy-tracker check-online-source <source_ref>`

`check-online-source` currently supports `la_city_primegov_archive`. It uses the
source log schedule/lookback fields, downloads recent PrimeGov agenda materials,
then runs the normal source refresh.

## Current Strategy

The preferred growth path is web/API first, Gmail second:

- LA City: PrimeGov online checks should be primary; Clerk listserv Gmail should remain an alert/backstop.
- LA County CEO: CEO agenda archive should be primary.
- LA County BOS: Statement of Proceedings is preferred for historical backfill; live agenda page and GovDelivery notices cover current/supplemental discovery.

This gives the project a repeatable public-data spine while still using email where public-sector notice behavior is messy.
