# Issue Scanning

## Goal

Create a repeatable recursive workflow that can:

- scan a policy issue area across the current corpus
- identify the bodies, clusters, and documents that matter most
- identify the people and institutions that keep appearing on the issue
- run second- and third-pass follow-up queries based on what the first pass discovers

This should be treated as a practical operator workflow for the current SQLite-backed system, not a future-only idea.

## Core Idea

Issue scanning should be recursive rather than single-pass:

1. start broad with an issue seed
2. identify the strongest source and cluster signals
3. identify recurring actors, programs, facilities, and funding streams
4. use those discoveries to run narrower second- and third-pass scans
5. keep a follow-up queue for the next refresh

In short:

`issue seed -> broad scan -> source discovery -> actor discovery -> focused rescan -> timeline/follow-up`

## First-Pass Scan

Start with an issue seed such as:

- `homelessness`
- `tenant protections`
- `probation`
- `fire recovery`
- `mental health facilities`
- `immigrant access`

The first pass should pull candidate items using multiple signals together:

- topic tags from `structured_item_topics`
- title and `text_block` keyword matches from `structured_agenda_items`
- high-priority findings from `structured_findings` when available
- cluster and committee names that are obviously related to the issue

The first pass should answer:

- which source families matter most
- which clusters, committees, or bodies matter most
- which recent items are highest-signal
- which terms or entities repeat often enough to deserve a narrower follow-up pass

## Second-Pass Scan

Use the first-pass results to narrow the search.

Examples:

- if a homelessness scan repeatedly hits `Housing and Homelessness Committee`, `Community Services Cluster`, `Homelessness & Housing Cluster`, and regional homeless-alignment committees, use those as explicit source filters in the second pass
- if the first pass repeatedly surfaces terms like `HHAP`, `interim housing`, `bridge housing`, `outreach metrics`, or `Department of Homeless Services and Housing`, use those as follow-up search terms
- if the first pass shows repeated budget and contract activity, rescan specifically for `appropriation`, `grant`, `contract`, `sole source`, `amendment`, and `award`

The second pass should answer:

- which sub-issues are active inside the broader issue area
- whether the issue is mostly budgetary, contractual, governance-related, legislative, or operational
- whether the issue is concentrated in one body or moving across City, County CEO, and BOS layers

## Third-Pass Scan

The third pass should focus on continuity and escalation:

- continued items and repeated appearances across meetings
- linked budget, contract, and implementation items
- movement from committee or cluster review into final Board or Council action
- recurring facilities, vendors, departments, or programs
- unresolved questions that should be checked again after the next refresh

This pass is what turns item collection into durable issue tracking.

## Key Players Pass

Issue scans should always include a dedicated key-players pass.

For now, think of key players in five buckets:

1. governing bodies
   Examples: `Housing and Homelessness Committee`, `Public Safety Cluster`, `Board of Supervisors`
2. departments and agencies
   Examples: `DMH`, `DPW`, `Los Angeles Housing Department`, `Chief Administrative Officer`, `Chief Executive Officer`
3. named presenters or speakers
   Drawn from parsed `speakers` fields and from repeated names in titles or text
4. elected officials or sponsors
   Often visible in City motions or BOS items through phrases like `Motion (Raman - McOsker)` or `as submitted by Supervisor Hahn`
5. outside institutions
   Examples: `LACDA`, `LAHSA`, vendors, partner agencies, hospitals, universities, or nonprofit operators

The first useful output is not a perfect entity graph. It is a ranked list of recurring actors by issue, with the context in which they appear.

## Current Key-Players Heuristics

With the current schema and parsers, the most reliable actor signals are:

- `cluster_name`
- `source_id`
- `title`
- `text_block`
- parsed `speakers`
- recurring organization names in findings and agenda text

The current system does not yet normalize all actor roles into separate tables, so the key-players pass should distinguish between:

- authoritative structural actors:
  - bodies
  - clusters
  - committees
  - departments explicitly named in titles
- softer extracted actors:
  - speakers
  - presenters
  - sponsors inferred from title text
  - organizations inferred from title or body text

## Recommended Outputs For Each Issue Scan

Each issue scan should produce these artifacts or report sections:

1. issue overview
   - issue name
   - scan date
   - scope and seed terms
2. top sources
   - source families
   - clusters or committees
   - why they matter
3. key players
   - bodies
   - departments
   - elected officials or sponsors
   - recurring outside institutions
4. top actions
   - budget actions
   - contracts
   - hearings
   - ordinances
   - oversight reports
   - implementation updates
5. timeline
   - earliest visible item
   - latest visible item
   - repeated or continued items
6. follow-up queue
   - terms to rescan later
   - sources to prioritize on next refresh
   - unanswered questions

## Query Strategy

Use a layered query strategy:

1. topic-led pull
   Use `structured_item_topics` to get broad recall.
2. text-led pull
   Use `title` and `text_block` search to catch items that tagging missed.
3. findings-led pull
   Use `structured_findings` to prioritize high-signal items where findings exist.
4. source-led pull
   Group by `source_id` and `cluster_name` to identify the main venues.
5. actor-led pull
   Rescan using discovered names, departments, programs, vendors, facilities, and sponsors.

## Current Schema Constraints

The workflow above is possible now, but a few current limitations should be kept in mind:

- `structured_findings` is not yet refreshed uniformly across every source after every parser change, so priority-driven scans are currently most reliable where findings are up to date
- `structured_item_topics` requires a join through `structured_agenda_items` for source-level analysis
- raw-to-structured lineage is still more brittle than ideal because `structured_documents` does not yet carry a direct `source_document_id`
- parsed `speakers` coverage is uneven by parser family, so named-person analysis should be treated as partial rather than exhaustive
- some sponsor or presenter names still live only in `title` or `text_block`, not in dedicated role columns

## Later Build Targets

To make recursive issue scans stronger over time, the next useful analytical upgrades would be:

1. add a dedicated issue-scan CLI flow such as `scan-issue --topic homelessness --depth 3`
2. add reusable SQL/query helpers for:
   - top sources by issue
   - recurring actors by issue
   - repeated items across meeting dates
3. normalize actor roles into richer fields or tables:
   - sponsors
   - presenters
   - departments
   - organizations
4. add issue briefs or snapshots that can be regenerated after each refresh
5. add cross-source linking so the system can better detect issue movement from review agendas to Board or Council action
