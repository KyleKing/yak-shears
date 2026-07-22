# Roadmap

Vision and long-term direction for Yak Shears. For concrete sequenced work, see [PLAN.md](./PLAN.md); for current state, see [STATUS.md](./STATUS.md).

## Vision

A flexible, file-based knowledge management system supporting:
- Structured metadata via frontmatter (edited as plain text, rendered read-only; see ADR 0003)
- Wiki-style bi-directional linking with auto-suggestions
- Media attachments that live inside the synced vault (see ADR 0004)
- Aggregated views over note metadata

## Design Principles

1. **File-first**: Djot files are source of truth; files round-trip verbatim
2. **Optional metadata**: Notes work without frontmatter
3. **No lock-in**: Files work without Yak Shears
4. **Progressive enhancement**: Basic notes work, advanced features optional
5. **Scandinavian minimalism**: Clean, functional, subtle design

## Completed

- Phase 0 foundation: Starlette/HTMX app, auth, listing, editor with live preview, DuckDB search
- Scandinavian minimal design system with E2E coverage (see `archive/IMPROVEMENTS.md`)
- Frontmatter parsing (YAML and Apple Notes export format), link extraction, backlinks storage
- Media upload with transcoding, thumbnails, and doctor view
- Hetzner deployment (PLAN.md Phase 1, 2026-07-22): live at `https://yak-shears.kyleking.me`; see [DEPLOY_LOG.md](./DEPLOY_LOG.md)

## Near Term

Priority order (2026-07-06): deploy first, then auth/data hardening, then product features, with infrastructure polish opportunistic around them. Sequenced in [PLAN.md](./PLAN.md): Hetzner deployment (Phase 1), data-integrity and auth hardening (2), link intelligence and related notes (3), the frontmatter query engine and store split (4), product views (5: prune queue, streams, backlog), grouping and network navigation (6), read-only external references (7). Media hardening, the search text-backend swap (ripgrep/DuckDB FTS), the semantic CLI, and lint are opportunistic infrastructure that slots between product phases.

### The keystone: query over notes-with-frontmatter

Most of the product roadmap reduces to one primitive: query and aggregate notes by frontmatter, sorted, filtered, and grouped, then render the result as a view. A backlog is a query, a stream board is that query grouped by state, a triage bucket is the query for notes missing state, the prune queue is a query over review dates. Build the query engine once (PLAN.md Phase 4) and each product feature is a thin view. Nothing becomes app-owned state that cannot be rebuilt from the vault; a "stream member" is a query result, not a stored list.

### Link Intelligence and related notes (PLAN.md Phase 3)

- `[[` autocomplete in editor (prefix, recent, frequent) and a search-to-select cross-linking modal on the same resolver
- Fuzzy link resolution and broken-link detection (doctor-style report first)
- Link preview on hover
- Frontmatter key completion in the editor (also drives `color`/`stream`/`state` completion for streams)
- Inline, explainable related-notes panel per note (ranked by shared links, shared tags, co-citation; embeddings later)

### Work Streams, Backlog, and the prune queue (PLAN.md Phase 5)

Personal organization as views over task-notes, not a separate task store. A stream is a note (`type: stream`) with a short id, display name, palette color, and optional WIP limit; a task is a note with `state` and an optional `stream`. The board groups tasks by state within a stream, the backlog is the same data as a table, and the triage bucket catches task-notes missing a stream or state. A curated named palette (fjord, teal, moss, ...) is the schema artifact that drives in-editor color completion, swatches, and Doctor validity checks. WIP limits are a forcing function on attention, so they live in the view, not the data. A daily prune/review queue resurfaces stale notes on a spaced interval to fight note rot.

## Longer Term

### Grouping and network navigation, the anti-graph (PLAN.md Phase 6)

The Obsidian-style global force-directed graph is a hairball with no stable spatial memory and flat edges; the competitive research is clear that it is a diagnostic at best, never a navigation tool. The stance here is compute and surface, do not draw. Navigation runs on an explainable related-notes panel and a bounded local graph (1-2 hops, with type/state/recency encoded). Grouping runs on living hub notes (`type: hub`) whose membership is a derived query rather than a hand-maintained list, auto-drafted from detected clusters for the user to curate (this is the "central node note" idea done so it cannot go stale). Understanding the network runs on a scheduled network-health digest: emergent themes (Leiden community detection diffed over time), bridge notes (betweenness), hub leaderboard (PageRank), and orphans with suggested connections. Computed signals live only in the rebuildable index; only user-accepted actions ever write to files.

### Semantic Search (opportunistic infrastructure)

Hybrid keyword + vector search as a **separate general-purpose CLI**, integrated through the SearchBackend seam (ADR 0002). Also the seam that later feeds embedding similarity into the related-notes panel and the network-health digest. Blueprint preserved in `archive/djot-search-sqlite-exploration.md`.

### Data Models and Aggregation

The query engine, table view, and board view moved into the near-term product phases (PLAN.md Phases 4-5). What remains longer-term:
- Optional schema validation for known `type:` values (report-style, like the doctor view)
- Block references (`[[note#heading]]`), templates for new notes, export/import
- A cluster-by-cluster adjacency matrix as a "whole vault at a glance" view (stretch; stays legible where node-link tangles)

### Workout planner (deferred)

Decision pending (see PLAN.md). Likely modeled as dated notes with structured frontmatter so streaks and a calendar become views, with a possible sibling iOS app reading and writing the Syncthing vault directly rather than through a token API.

### CLI Ideas (from 2026-07 planning notes)

A possible `shears` companion CLI over the same vault:
- `shears new (evergreen|personal|work)?` with the category ("yak pen") set via env var or argument; or reconsider one flat directory with category as metadata
- `shears list -order=(created|modified|count-links|...)` defaulting to most recently modified
- Note state lifecycle: no state initially, manually promoted to `Atomic` once reviewed; tasks are notes with `state: backlog|queue|in-progress|complete|not-planned` (no `on-hold`: partially complete subtasks self-document and return to `queue`)
- `shears split <name>?` / `shears merge <from>? <to>?` with interactive selection, recording `split-from` / `merged-from` frontmatter so links to deleted/moved notes stay resolvable
- `shears link <from?> <to?>` managing a `links:` list (bi-directionality comes from the database, not the file)
- Planning metadata for time-sensitive tasks: `start-date`, `soft-deadline`, `hard-deadline`
- Bookmarklet notes managed by a browser extension, to archive tabs instead of cluttering the bookmarks bar
- Trip-planning note type (location, cost, must-see, category, best time, dates) enabling dynamic calendar scheduling and nearby lookups

### Layout Container Ownership (from the stale yak-shears-py checkout)

That checkout's final commit moved the `.container` div out of `base.html.jinja` into each page template so routes own their width. The current design kept `.container` in base (1200px cap) and works around it per-page: pinned-panel CSS drops the inner `.editor-container` cap to claim space within the outer cap, and `body[data-route]` offers per-route overrides without moving markup. Revisit if a route ever needs true full-width (e.g. side-by-side editing plus pinned metadata on wide screens); the options are the sub-template move, a base-template block that suppresses the wrapper, or a `data-route` width override.

### Visual Regression Testing (survey from the stale yak-shears-py checkout)

A prior tool survey concluded: Playwright's built-in `to_have_screenshot` diffing is the fit here (free, already the e2e harness); Percy/Applitools/Chromatic add paid dashboards this single-user project doesn't need; BackstopJS/Loki add a second harness for no gain. The e2e suite already captures README screenshots via `maybe_screenshot`, so adoption is mostly baseline management and CI storage for diffs.

## Performance Targets

- Parse 1000 files in <500ms (validated: 0.318ms/file)
- Backlinks query <50ms (validated: 2-3ms)
- Related notes query <100ms
- UI render <100ms

## References

- `adr/` — decision records
- `archive/METADATA_LINKING_PLAN.md` — original detailed architecture (partially superseded by ADR 0003)
- The `spikes/` directory was removed in 2026-07 (all spikes validated and integrated); results survive in git history and the numbers above
