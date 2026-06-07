# Dashboard Product Plan

## Vision

Policy Tracker should become a policy-intelligence product, not only an ingestion pipeline.

The first dashboard should give the operator immediate visibility into what is in the database, what was recently added, what failed, and where the corpus is incomplete. Over time, the same surface should become a tiered analytics product that helps users understand public-sector activity, compare related bodies, and identify risks, opportunities, and follow-up work.

The product shape is:

- backend ingestion and archival
- structured extraction and source health monitoring
- analytical processing over meetings, items, actors, topics, and findings
- dashboard access for basic visibility
- paid insight layers for deeper analysis, historical context, and connectivity

## Product Thesis

Public-sector agenda monitoring is valuable when it does three things well:

1. tells users what changed recently
2. explains why those changes matter in context
3. preserves enough history to show patterns across bodies, departments, and meetings

The dashboard should therefore be both an operations console and an insight product. The early version can be local and operator-focused, but it should use product concepts that can later support accounts, tiers, saved issue areas, and connected workflows.

## Near-Term Operator Dashboard

The first dashboard should answer:

- which sources are active
- when each source was last checked
- how many documents and agenda items exist by source
- which agenda dates are represented
- what was added in the last refresh
- which downloads, parses, imports, or findings failed
- which sources are incomplete or stale
- which high-priority findings are available now

Suggested first screens:

1. Overview
   Source health, total documents, structured items, findings, recent refresh status, and unresolved failures.
2. Sources
   Per-source status, latest agenda dates, document counts, item counts, parser coverage, and current gaps.
3. Agendas
   Meeting-centric browser showing recent agenda/proceeding dates, body, source, document role, item count, and links back to raw/structured artifacts.
4. Items
   Searchable item explorer with filters for source, body, topic, date, action, priority, and text search.
5. Findings
   High-signal findings, priority scoring, topic filters, and source traceability.
6. Review Queue
   Download retries, manual-review cases, parser misses, incomplete source checks, and stale refresh states.
7. Issue Lens
   Prototype insight view for one topic at a time, initially powered by existing topic tags and issue-scanning heuristics.

## Performance Indicators

Initial dashboard indicators should be measurable from SQLite and local state files:

- active source count
- last successful refresh by source
- latest agenda or proceeding date by source
- raw document count by source
- structured document count by source
- structured item count by source
- finding count and high-priority finding count by source
- parser coverage rate for substantive documents
- retry queue count
- manual-review queue count
- stale source count
- sources with known parser/config blockers

The dashboard should distinguish operational health from analytical value. For example, a source can be healthy because it refreshes cleanly but still analytically weak because few findings or issue links exist.

## Insight Product Direction

The long-term product should organize insights around issues, bodies, actors, and risks.

Core insight types:

- issue activity summary
- recent high-signal actions
- historical timeline
- recurring actors and departments
- related activity in adjacent bodies
- budget, contract, governance, and implementation signals
- continuation or escalation patterns
- risk and opportunity analysis
- suggested follow-up questions
- source-confidence and coverage warnings

The dashboard should make clear when an insight is based on strong structured data, partial parser coverage, or weaker text heuristics.

## Tiered Product Model

### Free / Public Awareness

- basic source and agenda visibility
- recent meeting and item browser
- simple topic filters
- limited recent findings
- public-source traceability

### Pro / Analyst

- saved issue lenses
- deeper historical search
- recurring actor and department views
- cross-source timelines
- priority and risk scoring
- exportable briefs
- follow-up queues

### Team / Advanced

- shared saved searches and issue monitors
- custom source sets
- connected alerts
- annotations and review state
- richer integrations with email, documents, and CRM-style workflows
- organization-specific policy memory

## Data And Infrastructure Implications

To support the dashboard without creating throwaway work, the next infrastructure should include:

- a read-only local API over SQLite
- stable JSON response shapes for dashboard cards, tables, and detail pages
- source-health summary queries
- meeting-centric query helpers
- parser-coverage and queue-summary helpers
- issue-scan summary helpers
- explicit raw-to-structured lineage fields
- durable refresh-run records instead of only ad hoc state files

The dashboard should not query raw tables directly from UI components once an API layer exists. The first prototype can use direct SQLite queries if that is faster, but those queries should be organized around response shapes that can move behind an API.

## Prototype Scope

The useful prototype is an internal local dashboard, not a polished SaaS app.

Build only enough to replace repeated manual prompting for status:

- top-level KPIs
- source health table
- latest agenda dates
- recent documents/items
- retry/manual-review queue counts
- findings preview
- simple topic/source/date filters

Do not block the prototype on authentication, billing, multi-user state, or advanced AI analysis. Those belong after the local dashboard proves the data shape.

## Recommended Build Sequence

1. Add dashboard summary query functions in Python for KPIs, source health, recent agendas, review queues, and findings.
2. Add a minimal read API that exposes those summaries from the configured SQLite database.
3. Scaffold a local web dashboard that consumes the API.
4. Add an issue-lens prototype using existing topic, search, and findings data.
5. Add durable refresh-run records so the dashboard can show last run, failures, and imports without scraping logs.
6. Add tier-aware product boundaries once the insight views are useful locally.

## Design Principles

- Show operational truth first; do not hide failed sources.
- Keep every insight traceable to source documents and agenda items.
- Separate known data from inferred analysis.
- Make incomplete coverage visible instead of silently producing weak conclusions.
- Prefer reusable query/API shapes over UI-only logic.
- Optimize the first dashboard for the operator, while preserving the path to a paid analytics product.
