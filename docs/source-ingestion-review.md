# Source Ingestion Review Notes

## County CEO Agenda Archive

Reviewed on: 2026-06-02. Activated on: 2026-06-03.

### Current Source Shape

The County CEO agendas page now renders agenda data through a frontend search component:

- landing page: `https://ceo.lacounty.gov/agendas/`
- data endpoint: `https://ceo.lacounty.gov/wp-json/blade-child/v1/agenda-data`
- script revealing endpoint: `wp-content/themes/blade-child/features/agenda-search/agenda-search.js`

The older static `<h4>` section parser is no longer sufficient by itself. It should remain as a fallback, but the API endpoint is now the primary discovery source.

### Automation Result

The new agenda-first web check ran successfully:

- source: `la_county_ceo_agendas_archive`
- discovery method: `agenda_data_api`
- date window: `2026-05-03` through `2026-06-16`
- agenda PDFs downloaded: `23`
- structured documents imported by refresh: `21`
- agenda item rows imported by refresh: `109`
- topic rows imported by refresh: `165`
- latest structured CEO meeting date after run: `2026-06-03`

The daily incremental manifest is now separate:

- `local/downloads/la_county_ceo_agendas/ceo_incremental_manifest.json`

The historical manifest is preserved:

- `local/downloads/la_county_ceo_agendas/ceo_last_12_months_manifest.json`

### Important Finding

Supporting documents should not be downloaded in the daily agenda check. The prior attempt timed out because the downloader coupled agenda refresh with supporting-document retrieval. The correct operating model is:

1. Daily agenda-first check.
2. Refresh canonical agenda text into structured items.
3. Separate supporting-document backfill/review job.

### Remaining Gaps

- Commission and packet variants still need parser expansion.
- Supporting-document ingestion needs its own queue, timeout policy, and review status.
- Source log freshness should be updated after each successful scheduled run.

## Next Source Reviews

### BOS

Reviewed on: 2026-06-02

#### Current Source Shape

The live BOS agenda page is a Nuxt-rendered public page:

- live page: `https://bos.lacounty.gov/board-meeting-agendas/`
- agenda artifacts: `assets-us-01.kc-usercontent.com` HTML and PDF links
- existing historical backfill: Wayback snapshots of the same live page
- existing proceedings source: Algolia-backed Statement of Proceedings index

The live page currently includes server-rendered agenda cards, so it can be
parsed without browser automation. The existing BOS snapshot parser successfully
identified current regular and supplemental agenda HTML/PDF links from the live
HTML.

#### Automation Result

A live-page downloader is now wired into the source-log check path:

- source: `la_county_bos_live_agenda_page`
- adapter: `la_county_bos_current_page`
- manifest: `local/downloads/la_county_board_agendas/bos_current_manifest.json`
- discovery method: `live_bos_agenda_page`

The current check stores agenda HTML/PDF artifacts and preserves source URL,
meeting date, label, file path, text path, SHA-256 hash, and document ID.

Run result:

- date window: `2026-02-02` through `2026-06-02`
- agenda artifacts discovered: `36`
- agenda artifacts downloaded: `36`
- meeting dates covered: `2026-03-03` through `2026-05-19`
- refresh mode: download-only

#### Important Finding

The live BOS page is suitable for current discovery, but it is not enough for
historical coverage. The Statement of Proceedings source remains the better
repeatable historical/outcomes source. The live agenda page should be treated as
current-window ingestion plus packet/supporting-document expansion.

The first full refresh attempt failed because the source config declares
`lacounty_govdelivery_email`, but that parser is not registered and is not the
right long-term parser family for BOS agenda HTML/PDF text. Download-only mode
now lets the system collect current artifacts while parser work remains open.

#### Remaining Gaps

- The active `la_county_board_agendas` source config still uses the
  `lacounty_govdelivery_email` parser, which is not a true BOS page/parser
  family.
- Supporting-document expansion beyond the listed agenda and supplemental
  agenda links needs a separate design.
- BOS agenda packet item extraction should be reviewed before treating imported
  item counts as analytically complete.

Recommended source order:

1. Statement of Proceedings archive, because it is already reliable for historical records.
2. Live BOS agenda page, because it is needed for current packets and supporting documents.
3. GovDelivery Gmail notices, kept as alert/backstop.

The key question is no longer whether browser automation is required for the
current page; it is not required for the visible agenda cards. The next question
is parser quality.

### LAHSA

Reviewed on: 2026-06-02

#### Current Source Shape

LAHSA exposes a public document library:

- library: `https://www.lahsa.org/documents`
- sampled scope: `https://www.lahsa.org/documents?scope=106`
- sample detail page:
  `https://www.lahsa.org/documents?id=9678-fy2025-26-lahsa-budget-adoption.pdf`
- direct download shape:
  `https://www.lahsa.org/item.ashx?id=9678-fy2025-26-lahsa-budget-adoption.pdf&dl=true`

The library is an ASP.NET WebForms page with scope browsing and postback
filters. Detail pages are much more ingestion-friendly: they include JSON-LD,
an iframe PDF viewer, a direct download link, and explicit metadata fields for
document type, project scope, published date, available-until date, and last
modified timestamp.

The sampled Finance scope returned budget reports and budget adoption PDFs.
The page also exposes project filters including Commission, CES, Continuum of
Care, Measure H, and other homelessness-program categories.

#### Automation Result

LAHSA is now active in `configs/source_log.yaml`:

- body: `lahsa`
- source: `lahsa_document_library`
- active source config: `lahsa_documents`
- activation stage: `active`
- status: `active`
- local root: `local/downloads/lahsa_documents`

First production run:

- tracked scopes: Finance (`106`) and Policy (`107`)
- keywords: agenda, minutes, commission, board, budget, policy, governance
- visible documents discovered: `40`
- documents selected: `16`
- documents downloaded: `16`
- fetch failures: `0`
- structured documents written: `16`
- structured items written: `16`
- topics imported: `70`
- manifest:
  `local/downloads/lahsa_documents/lahsa_documents_manifest.json`

The raw `documents` table now carries LAHSA-published dates from detail-page
metadata. The generic supporting-document parser can still derive different
structured dates from document body text, so LAHSA-specific parsing remains a
quality step before using structured dates analytically.

#### Remaining Gaps

- Add WebForms pagination/postback support so scope pages are not limited to
  visible first-page results.
- Inventory project filters, especially Commission.
- Decide whether LAHSA should remain one broad document-library source or split
  into narrower active sources, such as Commission agendas and budget documents.
- Replace the generic supporting-document parser with LAHSA-specific metadata
  and item extraction once enough samples accumulate.

Recommended source order:

1. Identify agenda/minutes/document portals.
2. Determine whether documents are indexed by meeting body, committee, date, or document category.
3. Separate board/commission agenda materials from broad document-library records.
4. Add candidate source-log entries before building ingestion.

The key question is still whether LAHSA agendas/minutes are first-class document
types or only searchable titles inside the broader library.

## Pipeline Review

The emerging ingestion pattern should be:

1. Source log as control plane.
2. Discovery adapter per source shape.
3. Canonical agenda/proceedings artifact download.
4. Separate supporting-document expansion queue.
5. Text extraction and source-specific item parsing.
6. SQLite import with source/document provenance.
7. Findings generation after parser quality is known.

The main architectural split is daily canonical ingestion versus slower
supporting-document review. CEO proved this: agenda-first refresh is fast and
stable, while coupling supporting documents into the daily check can time out.
BOS likely needs the same split. LAHSA now has a first active document-library
ingestion path, but it should remain treated as broad public-document ingestion
until agenda/minutes-bearing subsets are confirmed.
