# Query Layer

## Goal

Expose imported structured items in a shape that works for both CLI reporting now and a visual interface later.

## Design Direction

The query layer returns normalized item records rather than formatted terminal-only output.

That makes it easier to reuse the same code for:

- CLI commands
- a future local API
- a future visual interface

## Current Commands

- `policy-tracker list-items`
- `policy-tracker weekly-digest`

## Current Filters

- topic
- cluster
- meeting date
- free-text search
- limit

## Current Output Shapes

`list-items` returns JSON with:

- filters
- count
- cluster summary
- topic summary
- item rows

`weekly-digest` returns:

- JSON digest, or
- Markdown digest

## Next UI-Friendly Step

The next frontend-oriented improvement would be a very small local read API that serves:

- `/items`
- `/topics`
- `/clusters`
- `/digest`

using the same query-layer functions.
