# Item Extraction

## Goal

Convert extracted agenda text into structured agenda-item rows that are usable for downstream policy analysis.

## Current Output

For each extracted text file, the parser currently captures:

- cluster name
- meeting date
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

## Next Improvements

The next useful upgrades would be:

1. infer departments more explicitly
2. split title versus subtitle more cleanly
3. map tags to the project taxonomy with stronger rules
4. store extracted item rows in SQLite
