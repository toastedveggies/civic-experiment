# Product Plan

## Product Direction

Build a local-first public-policy tracking system that starts with LA County agenda materials, now includes LA City agenda intake, and grows into a multi-jurisdiction research tool with durable memory, queryable history, and eventually a visual interface.

The primary operational goal is to harvest agenda emails and linked supporting documents from your Gmail on a schedule, then analyze those materials for both current developments and longer-term trends.

## Product Goals

- harvest agenda emails and linked supporting documents from Gmail on a schedule
- keep a repeatable local archive of raw files and extracted text
- generate current-awareness outputs from newly received agenda materials
- build trend memory over time as more meetings and supporting documents accumulate
- make public-sector agenda monitoring repeatable
- reduce repeated rereading of agenda packets and supporting documents
- keep findings traceable to source materials
- support longitudinal tracking across meetings and jurisdictions
- create outputs that are useful both for close review and higher-level trend analysis

## Current Product Shape

The product currently behaves like a backend/data pipeline with a CLI interface.

It already has the beginnings of:

- a source onboarding model
- a local archive
- a Gmail-first LA County intake path
- a Gmail-first LA City notice-to-PrimeGov intake path
- a historical LA City PrimeGov backfill path
- a historical LA County CEO archive backfill path
- a historical LA County BOS Statement of Proceedings backfill path
- structured item extraction
- a live SQLite store
- queryable item records
- digest generation

## Near-Term Product Priorities

### 1. Improve analytical usefulness

- add item-level findings generation
- add why-it-matters summaries
- add priority scoring
- improve topic mapping

### 2. Automate recurring intake

- add scheduled Gmail harvesting
- make linked-document refresh repeatable
- track which emails and linked documents have already been processed
- produce a reliable "what's new since last run" flow
- wire the live Gmail connector output into source-specific ingesters like the new LA City notice flow

### 3. Expand source coverage

- pull LA County Board historical materials from the Statement of Proceedings archive first, then expand into supporting documents from board agenda pages as needed
- add a parser family for BOS Statements of Proceedings so Board actions become item-level records, not just raw documents
- keep adding LA City bodies through parser-family reuse rather than one-off parsers
- increase structured coverage for LA County CEO archive PDFs through parser-family reuse
- add Family and Social Services and other high-relevance cluster packets consistently
- onboard the next LA County, LA City, or regional agenda sources

### 4. Improve operator workflow

- make refresh/import/report steps easier to rerun
- add failure dashboards via queue files and query commands
- improve document-level traceability

### 5. Prepare for a visual interface

- keep query outputs normalized and JSON-first
- define stable item/document response shapes
- add a small local read API layer
- design UI views around:
  - item browser
  - topic filters
  - cluster filters
  - weekly digest
  - trendline explorer

## Suggested UI v1

If a visual interface is added soon, the first useful screens should be:

1. Inbox/Batch view
   Show recently imported documents and processing status.
2. Item explorer
   Filter by topic, cluster, date, and search.
3. Digest view
   Show weekly summaries and high-signal items.
4. Review queue
   Surface `needs_retry` and `needs_manual_review` items.

## Suggested Next Build Sequence

1. raise parser coverage on LA County CEO archive pulls
2. live Gmail harvest plus source-specific ingest runners
3. stronger findings, taxonomy, and ranking
4. repeatable refresh/state tracking
5. local API
6. simple UI

## Resume Point

If picking this up later, the best next engineering task is:

- close the main LA County CEO parser gaps in this order:
- treat cancellation notices as intentional non-item documents
- extend the County parser for the cluster motion-line variant
- add parser families for regional homeless alignment agendas and homeless policy deputies agendas

That is the highest-leverage step because it turns a successful raw County archive backfill into a much more complete structured dataset before we automate more intake.
