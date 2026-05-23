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

## Next Improvements

The next useful upgrades would be:

1. infer departments more explicitly
2. split title versus subtitle more cleanly
3. map tags to the project taxonomy with stronger rules
4. store extracted item rows in SQLite
