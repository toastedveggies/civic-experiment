# Meeting-Centric Model

## Goal

Shift the project from a document-first tracker toward a meeting-centric record system where:

- a meeting is the primary unit of analysis
- agendas, minutes, board letters, staff reports, presentations, and attachments are queryable alongside that meeting
- minutes can be linked to the meeting they describe, even when they are approved later at a different meeting
- parliamentary actions can be stored in structured form instead of being trapped in raw minute text

## Why This Matters

For the current goals, the system needs to answer questions like:

- what happened at a given meeting
- which supporting documents belonged to that meeting
- who moved and seconded each item
- what the final vote tally was
- whether minutes for that meeting were later approved, corrected, or continued

The current document-first structure is good for ingestion, but it blurs together:

- the meeting where a document was presented
- the meeting a document is about
- the meeting where a prior meeting's minutes were approved

That becomes a major problem for parliamentary analysis, issue timelines, and key-player tracking.

## Proposed Entities

### Meetings

Add a dedicated `meetings` table that represents the canonical meeting record.

Suggested fields:

- `meeting_id`
- `source_id`
- `body_name`
- `meeting_date`
- `meeting_date_iso`
- `meeting_title`
- `meeting_type`
  - examples: `regular`, `special`, `adjourned`, `agenda_review`, `public_hearing`
- `meeting_status`
  - examples: `scheduled`, `held`, `cancelled`, `continued`
- `jurisdiction`
- `location_text`
- `start_time_text`
- `created_at`
- `updated_at`

Suggested uniqueness rule:

- one canonical meeting row per `source_id + body_name + meeting_date_iso + meeting_type`

That rule can be relaxed later when the same body truly has multiple meetings on the same day.

### Documents

Keep `documents`, but make document-to-meeting relationships explicit.

Suggested additional fields:

- `document_role`
  - examples: `agenda`, `minutes`, `board_letter`, `staff_report`, `presentation`, `attachment`, `transcript`, `ordinance`, `resolution`
- `presented_at_meeting_id`
  - the meeting where the document appeared or was approved
- `related_meeting_id`
  - the meeting the document is substantively about
- `approval_meeting_id`
  - useful when minutes or reports are approved later
- `document_status`
  - examples: `active`, `cancelled`, `continued`, `revised`, `superseded`

For minutes:

- `presented_at_meeting_id` is often the later approval meeting
- `related_meeting_id` should point to the earlier meeting the minutes describe
- `approval_meeting_id` can duplicate `presented_at_meeting_id` if that makes querying clearer

### Structured Documents

The structured layer should keep a stable lineage back to both raw documents and meetings.

Suggested additions:

- `source_document_id`
- `meeting_id`
- `document_role`

### Agenda Items

Agenda items should belong to a meeting, not only to a structured document.

Suggested additions to `structured_agenda_items`:

- `meeting_id`
- `source_document_id`
- `document_role`
- `action_text_raw`
- `vote_text_raw`
- `final_action`
  - examples: `approved`, `adopted`, `continued`, `received_and_filed`, `rejected`, `no_action_recorded`
- `motion_by`
- `second_by`
- `ayes_count`
- `noes_count`
- `abstain_count`
- `absent_count`
- `ayes_members_json`
- `noes_members_json`
- `abstain_members_json`
- `absent_members_json`

## Key Relationship Rules

### Agendas

- `document_role = agenda`
- `presented_at_meeting_id = related_meeting_id = meeting_id of the meeting itself`

### Minutes

- `document_role = minutes`
- `related_meeting_id = the meeting the minutes describe`
- `presented_at_meeting_id = the later meeting where the minutes were presented or approved`
- `approval_meeting_id = same as presented_at_meeting_id` when approval is explicit

### Supporting Documents

Examples:

- board letters
- staff reports
- presentations
- ordinances
- attachments

These should usually point at the meeting where they were presented:

- `presented_at_meeting_id = related_meeting_id = the associated meeting`

If a later meeting reuses or approves the same document, that can be represented by:

- a document-link table later, or
- a later document record that references the earlier one

## Recommended Query Shape

The system should support meeting-centric queries like:

- show me the canonical agenda for meeting `X`
- show me all supporting documents tied to meeting `X`
- show me the minutes that describe meeting `X`
- show me which later meeting approved the minutes for meeting `X`
- show me all item-level parliamentary actions for meeting `X`

That implies a conceptual flow like:

`meeting -> agenda + items + supporting docs + minutes + parliamentary actions`

## Parliamentary Action Extraction

Minutes and proceedings should be parsed into structured action fields whenever possible.

Priority fields:

- `motion_by`
- `second_by`
- `final_action`
- `ayes_count`
- `noes_count`
- `abstain_count`
- `absent_count`
- member-level vote lists

Initial priority source:

- LA County BOS Statement of Proceedings

Later sources may include:

- approved minutes linked from City or County committee agendas
- attached committee minutes in packets
- transcripts or action summaries where available

## Ingestion and Parser Workflow Changes

When onboarding or extending a source family, treat linked minutes and related supporting docs as first-class collection targets.

For any agenda source, ask:

1. does the agenda link to prior meeting minutes
2. does it link to board letters, staff reports, presentations, ordinances, or attachments
3. are those documents directly about the current meeting, or about a prior meeting
4. should those docs be queryable only as attachments, or should they become structured documents with their own role
5. do any of those docs contain parliamentary actions or outcome language that belongs to the related meeting record

## Suggested Migration Plan

### Phase 1: Non-breaking additions

Add:

- `meetings`
- `source_document_id` on structured tables
- `meeting_id` on structured tables
- `document_role`, `presented_at_meeting_id`, `related_meeting_id`, `approval_meeting_id` on `documents`
- parliamentary action columns on `structured_agenda_items`

Keep current queries working by leaving existing columns in place.

### Phase 2: Populate canonical meetings

Backfill meetings from current structured documents using:

- source id
- cluster/body name
- meeting date text
- `meeting_date_iso`
- source path hints

### Phase 3: Re-link documents

Map existing agenda documents to their canonical meetings.

Then begin linking:

- minutes to the meeting they describe
- supporting docs to their associated meetings

### Phase 4: Parser and importer upgrades

Upgrade parsers and import paths so new structured rows automatically write:

- `meeting_id`
- `source_document_id`
- `document_role`
- parliamentary action fields when present

### Phase 5: Meeting-centric query layer

Add read paths for:

- meeting detail
- meeting document bundle
- meeting parliamentary summary
- issue scans that traverse meetings rather than only documents

## Immediate Practical Priorities

If sequencing this work incrementally, the highest-value order is:

1. add schema support for `meeting_id` and document roles
2. add parliamentary action fields to structured items
3. extend BOS parsing to capture motion/second/final-vote details
4. add minute discovery/download rules for agenda families that link prior minutes
5. link minutes to the meeting they describe rather than only the approval meeting

That would materially improve issue tracking, key-player analysis, and cross-meeting history without requiring a full system rewrite first.
