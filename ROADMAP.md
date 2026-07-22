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

### Search index health (opportunistic infrastructure)

The search index is a DuckDB file, rebuildable from the vault, and its default location is inside the vault itself (`~/Sync/yak-shears/yak_shears_search.db`, from `_yak/database.py:get_search_db_path()`). That default is a corruption risk and should change. Syncthing copies files at the file level with no idea that a `.db` is mid-write, so a sync that lands during a write can propagate a torn file, and two machines editing at once each write their own copy of the same database and then fight over it. The production deploy already passes `--search-db-dir /home/yakshears/.local/state/yak-shears` (PLAN.md Phase 1), so the fix is to make that the default rather than the override: put the index in a local state directory on every machine and let each rebuild its own from the vault. ADR 0002 already names this as one reason the current backend is the weakest code in `database.py`.

The rest is ordinary hygiene for any embedded database file, drawn from [Julia Evans' notes on running SQLite](https://jvns.ca/blog/2026/07/17/learning-about-running-sqlite) and translated to DuckDB:

- Keep query statistics current. Her 5-second full-text query dropped to ~0.05s after `ANALYZE`, and DuckDB's planner is also statistics-driven, so a periodic `ANALYZE` after a bulk index refresh is cheap insurance
- Batch large deletes. Her cleanup blew a 5-second write timeout and crashed workers. The index-refresh path here deletes and re-inserts per file, so keep it that way rather than growing one vault-wide transaction
- Compact after churn. Her backup step is `VACUUM INTO` a fresh file, which doubles as defragmentation. The equivalent for a rebuildable DuckDB index is deleting and rebuilding it, which is the cheapest option available precisely because nothing here is authoritative
- Split databases when the tables have nothing to do with each other. This is the same seam ADR 0002 already calls for (metadata/backlinks store separate from the text index)

Not applicable: her backup work (Restic snapshots, Litestream streaming replication) exists to protect authoritative data, and this index holds none. The vault is the backup. Journal/WAL-mode tuning and busy timeouts are SQLite knobs with no DuckDB equivalent to set here, though the underlying concern (one writer at a time, in-flight writes are not safe to copy) is exactly what the Syncthing point above is about. Concurrency and connection handling are already addressed: the process now keeps one DuckDB connection under a lock rather than opening one per query.

### Search performance: near-term and long-term

Near-term work (landing 2026-07-22) is all inside the existing backend: reuse one process-wide DuckDB connection instead of reconnecting per query, prefilter candidate words with a `LIKE` prefix match before running Levenshtein over the word table, walk the vault once per refresh instead of once per staleness check plus once per update, and emit per-stage timing logs so the next round of tuning starts from measurements rather than guesses.

Two defects found while measuring accounted for nearly all of the felt slowness, and both are worth remembering:

- `files.mtime` was declared `REAL`, which DuckDB stores as float32. A timestamp like `1753193031.123456` read back as `1753193088.0`, roughly a minute off, so every mtime comparison reported "changed" and every search past the 60-second guard re-indexed the whole vault. The column is now `DOUBLE`, with a migration for existing databases
- A full re-index spent essentially all its time in `executemany` over the word rows, at ~300µs per parameterized insert. Staging batches through a temp CSV and loading them with `read_csv` took a 600-file rebuild from 103s to 1.7s. Small batches still use `executemany` so saving one note stays cheap

The lesson for the backend swap below: measure before optimizing the query, because the query was never the expensive part.

Long-term is the backend swap already recorded in ADR 0002: replace the hand-rolled Levenshtein word table with DuckDB's FTS extension or a ripgrep subprocess behind the `SearchBackend` protocol, then add the semantic CLI through the same seam (see "Semantic Search" below). Caching repeated queries sits between the two and only makes sense once the timing logs show repeat queries are actually a cost.

### Mobile and offline (opportunistic infrastructure)

Two decisions recorded in 2026-07 after a round of iPhone bug reports:

- [ADR 0008](./adr/0008-mobile-text-entry-affordances.md) covers text entry on iOS. An in-page accessory toolbar positioned above the software keyboard, rather than an iOS custom keyboard extension (which cannot be scoped to one site and cannot ship without its own App Store app). Revisit if offline editing forces a native shell
- [ADR 0009](./adr/0009-ios-homescreen-app-and-offline.md) covers the homescreen web app. A manifest with `display: standalone` stops every navigation from bouncing into an in-app browser, and the server-rendered HTMX architecture (ADR 0006) stays. `hx-boost` is the cheap follow-up for app-like transitions. Offline stays open: a read-only service worker is the cheap first step, and offline *editing* is a conflict-resolution problem against Syncthing that ties back to the vault-direct sibling app in "Workout planner (deferred)" below

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
