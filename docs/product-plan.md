# Product Plan

## Product Direction

Build a local-first public-policy tracking system that starts with LA County agenda materials, now includes LA City agenda intake, and grows into a multi-jurisdiction research and analytics product with durable memory, queryable history, operator visibility, and eventually paid insight layers.

The primary operational goal is to harvest agenda emails and linked supporting documents from your Gmail on a schedule, then analyze those materials for both current developments and longer-term trends.

The primary product goal is to turn that backend pipeline into a dashboard-driven intelligence system: first for internal visibility into what is in the database and what is broken, then for user-facing policy insights, historical context, issue monitoring, and risk analysis.

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
- provide dashboard visibility into source health, latest agendas, refresh failures, parser coverage, findings, and recent policy activity
- support a tiered product path where basic users can see recent public activity and advanced users can access deeper historical, cross-source, and risk-oriented insights

## Current Product Shape

The product currently behaves like a backend/data pipeline with a CLI interface. The next product surface should be a local operator dashboard backed by the same SQLite/query layer.

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
- normalize meeting dates and canonical metadata so cross-source filtering and sorting become reliable
- add a recursive issue-scan workflow that can identify top sources, key players, and follow-up passes for a given issue area
- separate structural actors from softer extracted actors so issue scans can distinguish bodies, departments, sponsors, speakers, and outside institutions

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

### 3a. Screen low-value artifacts before parser work

- add a canonical-document selection layer so we parse the best available rendition of a meeting, not every duplicate
- exclude cancellation notices, duplicate PDF/plain-text companions, and other non-item artifacts from parser-debt metrics
- keep those low-value artifacts archived in `documents`, but separate them from substantive agenda/proceeding coverage goals
- treat parser comprehensiveness as a goal for substantive agenda families, not for every raw file variant

### 4. Improve operator workflow

- make refresh/import/report steps easier to rerun
- add failure dashboards via queue files and query commands
- improve document-level traceability
- distinguish low-value archived artifacts from substantive parser debt in operator-facing summaries

### 4a. Data hygiene

- add normalized fields such as `meeting_date_iso`
- preserve original display values alongside canonical normalized values
- standardize body names, document status, and item-type semantics across parser families
- improve parser cleanup rules for headers, footers, docket ids, and attachment boilerplate
- add a meeting-centric model so agendas, minutes, presentations, staff reports, and other supporting docs can be queried together
- distinguish the meeting where a document is presented from the meeting the document is actually about
- normalize parliamentary actions such as motion, second, final action, and vote tally where minutes or proceedings expose them

### 5. Build the operator dashboard foundation

- keep query outputs normalized and JSON-first
- define stable item/document response shapes
- add a small local read API layer
- add dashboard summary queries for source health, latest agendas, review queues, parser coverage, and findings
- design UI views around:
  - overview KPIs
  - source health
  - recent agendas
  - item browser
  - findings
  - retry/manual-review queues
  - issue lenses

### 6. Prepare the paid analytics path

- define free vs pro vs team analytics boundaries
- add issue-lens summaries that aggregate items, findings, actors, and timelines
- add confidence and coverage warnings so insights show when source data is incomplete
- prepare risk/opportunity scoring as a layer above traceable findings, not as a replacement for source evidence

## Suggested Dashboard v1

The first useful dashboard should be an internal local tool that replaces repeated manual prompting for database status.

1. Overview
   Show total sources, documents, structured items, findings, latest agenda dates, and unresolved failures.
2. Sources
   Show source-level status, latest refresh, latest agenda/proceeding date, parser coverage, and known gaps.
3. Agendas
   Show recent meetings/agendas by date, body, source, document role, and item count.
4. Item explorer
   Filter by topic, source, body/cluster, date, action, and search.
5. Findings
   Show high-signal findings, priority levels, topics, and traceability back to source items.
6. Review queue
   Surface `needs_retry`, `needs_manual_review`, parser failures, and stale sources.
7. Issue lens
   Start with a single-topic view that summarizes top sources, recent actions, recurring actors, and follow-up questions.

## Suggested Next Build Sequence

1. add meeting-centric schema support for `meeting_id`, document roles, and supporting-document relationships
2. normalize parliamentary action fields such as motion, second, final action, and vote tally
3. raise remaining parser coverage on substantive LA County CEO outliers and linked minutes/supporting docs
4. generate findings consistently across active sources
5. live Gmail harvest plus source-specific ingest runners
6. stronger issue-scan, actor, and timeline workflows
7. dashboard summary queries, local API, and internal prototype UI
8. issue-lens prototype and paid-insight boundary design

## Resume Point

If picking this up later, the best next engineering task is:

- first build dashboard summary queries over the current SQLite database so the operator can see source health, latest agendas, item counts, findings, and failures without prompting
- then add a small local read API and dashboard prototype around those summaries
- in parallel, continue moving the schema toward a meeting-centric model so agendas, minutes, and supporting docs can be linked to the meetings they describe
- then add parliamentary-action fields and extend BOS/minutes parsing to capture who moved, seconded, and voted on items
- then close the remaining substantive parser gaps in County CEO outliers and linked supporting-document families

That is the highest-leverage step because it upgrades visibility immediately while preserving the path toward a meeting-history and analytics product with usable outcome data, issue tracking, and paid insight layers.

Detailed dashboard guidance lives in [docs/dashboard-product-plan.md](/C:/Users/ramor/OneDrive/Documents/GitHub/civic-experiment/docs/dashboard-product-plan.md).
