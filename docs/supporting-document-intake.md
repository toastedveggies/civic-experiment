# Supporting Document Intake

## Current CEO Profile

As of May 26, 2026, the County CEO supporting-document crawl shows a viable general intake target rather than one-off attachment handling.

### Live / local snapshot

- CEO agenda PDFs audited: `322`
- Trusted supporting links discovered from agenda PDFs: `424`
- Existing local supporting PDFs found on disk: `413`
- Existing local supporting documents found by inventory pass: `427`
  - count includes local metadata-backed rows that may not map 1:1 to raw PDF files
- Live SQLite CEO supporting-document rows: `434`
- Live SQLite CEO supporting-document rows with extracted text: `428`

### Trusted backend families

These patterns were stable enough to treat as first-class supporting-document sources:

- `file.lacounty.gov/SDSInter/bos/supdocs/`
- `file.lacounty.gov/SDSInter/bos/bc/`
- `ftp.pw.lacounty.gov:8443/pub/bos/`
- `lacounty.sharepoint.com/:b:/...`

These should remain the default allowlist for unattended supporting-document fetches unless a new family is profiled first.

### Source concentration

Most current CEO supporting documents are concentrated in a few agenda families:

- `executive-committee-for-regional-homeless-alignment`
- `public-safety-cluster`
- `leadership-table-for-regional-homeless-alignment`
- smaller but still meaningful support-doc presence in `operations-cluster`, `family-and-social-services-cluster`, `health-and-mental-health-services-cluster`, and `community-services-cluster`

This means a generalized intake model should support both:

- committee minutes / proceedings-style records
- cluster packet materials such as reports, board letters, agreements, motions, resolutions, and large enclosures

## Intake Findings

### 1. Supporting documents are not one document family

The current CEO support-doc corpus mixes several distinct artifacts:

- `minutes` / `statement of proceedings`
- `reports`
- `agreements` / `amendments`
- `motions`
- `resolutions`
- `presentations` / `slide decks`
- `governance docs` such as bylaws / charters
- large `enclosure` packets

So the intake model should not treat every supporting PDF as a generic attachment forever.

### 2. A meeting can have multiple supporting-doc roles

One agenda can point to:

- prior meeting minutes
- draft motions
- final board letters
- packet enclosures
- slide decks
- staff memos

The document layer therefore needs role classification, not just parent-child file storage.

### 3. Reused support docs appear across multiple agenda contexts

Some documents are surfaced in more than one cluster or meeting context. The current schema can store the raw file, but it does not yet model many-to-many relationships between:

- source document
- presenting meeting
- related meeting
- agenda item(s)

That is the main structural gap for generalized supporting-doc intake.

### 4. Duplicate file-path rows were an obvious early error

The first support-doc passes produced duplicate `documents` rows for the same `file_path` when:

- one run inserted a live-downloaded supporting doc
- a later inventory pass rediscovered the same local file using a different identity path

The importer now reuses an existing row for the same `source_id + file_path`, but old duplicates already in SQL may still need cleanup.

## Generalized Intake Model

Supporting-document intake should move toward four stages.

### Stage 1. Discover

For each meeting agenda:

- extract trusted backend links from the agenda PDF or HTML
- record the raw discovered URL
- record the parent agenda document
- record whether the URL is direct or required a landing-page hop

### Stage 2. Materialize

For each discovered support doc:

- download the raw file
- extract text if possible
- store local metadata sidecars
- assign a stable canonical identity

Preferred identity order:

1. explicit backend URL when stable
2. normalized file-path identity when only a local artifact exists
3. content-hash fallback

### Stage 3. Classify

Each support doc should eventually get a `document_role`, such as:

- `minutes`
- `proceedings`
- `board_letter`
- `memo`
- `report`
- `presentation`
- `agreement`
- `resolution`
- `motion`
- `enclosure`
- `packet`
- `other_supporting_document`

Classification can begin with heuristics from:

- source URL family
- filename tokens
- first-page text
- known recurring body patterns

### Stage 4. Relate

Each support doc may need multiple relationship fields:

- `presented_at_meeting_id`
- `related_meeting_id`
- `approval_meeting_id`
- `parent_document_id`
- eventual `agenda_item_id` linkage when a document clearly belongs to one item

This is especially important for:

- minutes approved later than the meeting they describe
- board letters discussed in cluster review before the Board meeting
- packet enclosures reused across multiple agenda layers

## Recommended Next Build Order

1. Add support-doc profiling / classification fields to SQLite and JSON materialization.
2. Create a lightweight support-doc inventory query surface.
3. Add heuristic role classification for CEO support docs.
4. Normalize minutes / proceedings first, since they are highest-value for parliamentary action tracking.
5. Add meeting-linkage fields so minutes can attach to the meeting they describe rather than only the meeting where they were surfaced.
6. After that, expand to board letters, motions, agreements, and packet enclosures.

## Parser Onboarding Rule

When onboarding a new agenda family, check whether it exposes:

- direct support-doc URLs
- landing-page support-doc URLs
- prior meeting minutes
- draft or final board letters
- proceedings, motions, or resolutions

If yes:

- store the support docs as raw linked documents
- do not let them enter agenda refresh parsing by default
- add or reuse a document-role classifier before building one-off parsers
