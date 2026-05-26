# Item Extraction

## Goal

Convert extracted agenda text into structured agenda-item rows that are usable for downstream policy analysis.

## Current Output

For each extracted text file, the parser currently captures:

- cluster name
- meeting date
- normalized meeting date ISO
- section number and section title
- item label
- item type
- title text
- speakers
- source text block
- coarse topic tags

## Current Assumptions

This first pass is optimized for LA County cluster agenda text with patterns like:

- `2. INFORMATIONAL ITEM(S):`
- `A. BOARD LETTER:`
- `Speaker(s): ...`

It should be treated as a structured v1 parser, not the final generalized parser.

## Parser Metadata Rules

For future parser builds and parser-family extensions, keep these date-normalization rules consistent:

- preserve the original display date text in `meeting_date`
- also emit a canonical ISO date in `meeting_date_iso` when the display date can be normalized
- use shared normalization helpers rather than parser-specific one-off date formatting
- do not overwrite raw source text just to force normalization
- if a date cannot be normalized confidently, leave `meeting_date_iso` empty rather than guessing

The current shared helper lives in [src/policy_tracker/date_utils.py](/C:/Users/ramor/OneDrive/Documents/GitHub/civic-experiment/src/policy_tracker/date_utils.py:14).

## New Parser Family Workflow

Use this workflow when onboarding a new agenda or proceedings format so we expand parser coverage deliberately instead of adding one-off fixes:

1. collect 2-5 representative raw text samples for the format, including at least one clean case and one messy/outlier case
2. decide whether the format is a real parser target or a low-value artifact that should be screened out instead
3. identify the parser-family marker(s) that should drive dispatch in `detect_parser_name()` and prefer reusing an existing family when the structure is materially the same
4. preserve raw extracted source text, then add only the cleaned parsing logic needed to isolate:
   - canonical meeting linkage when the document is clearly about a specific meeting
   - canonical `cluster_name`
   - display `meeting_date`
   - normalized `meeting_date_iso`
   - section structure
   - item boundaries
   - cleaned titles and body text
   - document role when the file is minutes, a presentation, a board letter, or another supporting document rather than the canonical agenda
5. explicitly strip repeated headers, page footers, attachment boilerplate, vote boilerplate, and other recurring non-item text so it does not inflate structured rows or pollute topic tagging
6. when agendas link prior meeting minutes or substantive supporting documents, treat those links as first-class onboarding targets and decide whether:
   - the document should be queryable alongside the associated meeting
   - the document is actually about a prior meeting and should later be linked to that earlier meeting instead of only the approval meeting
   - the document may contain parliamentary actions or other outcome context worth structured extraction
7. keep parser-family helpers shared when possible instead of creating a new body-specific parser for each board or committee
8. add focused regression tests for:
   - parser detection
   - representative item extraction
   - date normalization behavior
   - repeated-header cleanup
   - meeting/minutes relationship cues when present
   - known wrapped-line or page-break edge cases
9. run the targeted unit tests first, then the broader extraction/import suite
10. refresh the source into a scratch state dir before touching the live DB, inspect structured JSON and SQL deltas, and confirm the parser is reducing true misses rather than only reshaping noise
11. after live refresh, record what improved, what remains unsupported, and whether the remaining gaps belong in a later parser chunk, supporting-document discovery, or screening rules

## Parser Acceptance Checks

Before considering a new parser family done, verify:

- the new family increases structured document or item coverage for the intended source
- `meeting_date` display text is preserved and `meeting_date_iso` is populated when confidently derivable
- minutes and supporting documents are not silently flattened into ordinary agenda rows without noting their document role or meeting relationship
- repeated headers and boilerplate do not leak into `cluster_name`, `section_title`, `title`, or `text_block`
- titles are cleaner without discarding substantive action language
- remaining misses are documented by family or artifact type rather than left as an undifferentiated backlog
- the live SQLite import path still works without duplicate or stale structured rows

## Next Improvements

The next useful upgrades would be:

1. infer departments more explicitly
2. split title versus subtitle more cleanly
3. map tags to the project taxonomy with stronger rules
4. carry meeting linkage, document-role metadata, and parliamentary action fields into structured outputs
