# Query Layer

## Goal

Expose imported structured items and dashboard summaries in a shape that works for CLI reporting now, a local operator dashboard next, and product APIs later.

## Design Direction

The query layer returns normalized item records rather than formatted terminal-only output.

That makes it easier to reuse the same code for:

- CLI commands
- a future local API
- a local dashboard
- future paid analytics surfaces

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

- `/dashboard/summary`
- `/sources/health`
- `/agendas/recent`
- `/items`
- `/findings`
- `/queues`
- `/topics`
- `/clusters`
- `/digest`

using the same query-layer functions.

The first dashboard should not depend on UI-only SQL. Add reusable Python query helpers first, then expose them through a local API and web UI.
