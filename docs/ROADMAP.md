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
5. **An instrument, not a document**: the interface is a console panel built from three materials, and every surface is scanned before it is read (see [DESIGN.md](./DESIGN.md))

## Completed

- Phase 0 foundation: Starlette/HTMX app, auth, listing, editor with live preview, DuckDB search
- The console design system with E2E coverage ([DESIGN.md](./DESIGN.md); the superseded Scandinavian-minimal system survives in `archive/IMPROVEMENTS.md`)
- Frontmatter parsing (YAML and Apple Notes export format), link extraction, backlinks storage
- Media upload with transcoding, thumbnails, and doctor view
- Hetzner deployment (PLAN.md Phase 1, 2026-07-22): live at `https://yak-shears.kyleking.me`; see [DEPLOY_LOG.md](./DEPLOY_LOG.md)

## Near Term

Priority order (2026-07-06): deploy first, then auth/data hardening, then product features, with infrastructure polish opportunistic around them. Sequenced in [PLAN.md](./PLAN.md): Hetzner deployment (Phase 1), data-integrity and auth hardening (2), link intelligence and related notes (3), the frontmatter query engine and store split (4), product views (5: prune queue, streams, backlog), grouping and network navigation (6), read-only external references (7). Media hardening, the search text-backend swap (ripgrep/DuckDB FTS), the semantic CLI, and lint are opportunistic infrastructure that slots between product phases.

### The keystone: query over notes-with-frontmatter

Most of the product roadmap reduces to one primitive: query and aggregate notes by frontmatter, sorted, filtered, and grouped, then render the result as a view. A backlog is a query, a stream board is that query grouped by state, a triage bucket is the query for notes missing state, the prune queue is a query over review dates. Build the query engine once ([PLAN.md](./PLAN.md) Phase 4) and each product feature is a thin view. Nothing becomes app-owned state that cannot be rebuilt from the vault; a "stream member" is a query result, not a stored list.

What each phase contains is in [PLAN.md](./PLAN.md), which sequences the work. This file stops at the reasoning behind it.

## Longer Term

### Grouping and network navigation, the anti-graph ([PLAN.md](./PLAN.md) Phase 6)

The Obsidian-style global force-directed graph is a hairball with no stable spatial memory and flat edges; the competitive research is clear that it is a diagnostic at best, never a navigation tool. The stance here is compute and surface, do not draw. Computed signals live only in the rebuildable index, and only a user-accepted action ever writes to a file.

### Search index health (opportunistic infrastructure)

The index default moved out of the vault (2026-07-22, [ADR 0010](./adr/0010-derived-data-and-syncthing.md)). It now resolves to `$XDG_STATE_HOME/yak-shears`, falling back to `~/.local/state/yak-shears`, and `SEARCH_DB_DIR` still overrides. Doctor shows where it landed and warns when it is inside the vault or when a stray copy from the old default is still there.

The measurement behind that: DuckDB keeps a `.wal` sidecar while a connection is open, and copying only the `.db` while a writer holds it produced **20 unreadable copies out of 20**. A synced index does not arrive degraded, it arrives dead. `tests/test_sync_safety.py` keeps that honest, so a future DuckDB that makes the copy safe will fail the test rather than quietly invalidate the ADR.

Embeddings are the case where syncing derived data does pay, because they cost API calls rather than a local second, and they are reproducible from a pinned model. ADR 0010 records the shape: a content-addressed immutable cache keyed on `(model, version, content_hash)`, one file per entry, never a database. Nothing is built until embeddings exist.

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

### Three-way merge on a refused save (deferred)

Saving now takes a lease (a digest of the content the page rendered from) and a
mismatch returns 409 rather than overwriting. The editor shows a line diff of the
saved note against the draft and offers keep-mine, take-theirs, resolve-by-hand, or
cancel. Resolve-by-hand loads both versions into the editor with git-style markers
around each run the two disagree on, and a guard refuses a save while any marker
remains. Nothing merges on its own.

The remaining step is the merge. All three versions are in reach at the moment of
the conflict, since the client holds the base it loaded and the draft, and the 409
carries what is on disk, so a standard diff3 could combine non-overlapping edits
and mark only the real conflicts. That is the nicest outcome when it works and the
worst when it silently produces text neither side wrote, which is the failure the
lease exists to prevent.

Deferred until hand resolution proves conflicts are frequent enough, and overlapping
enough, to be worth automating. Two things would decide it: how often a conflict
turns out to be non-overlapping (auto-merge would have been free), and whether the
conflicts are within a paragraph or across sections, since a line diff3 handles the
second well and the first badly. Marker runs that resolve to one side untouched
answer the first question directly, and counting them in the panel is the cheap way
to find out.

This is also the machinery offline editing needs, so the two should be decided
together rather than solved twice (see "Mobile and offline" above).

### Agent access to the vault (opportunistic infrastructure)

The `shears lsp` language server (see [PLAN.md](./PLAN.md)) gives nvim wikilink completion, go-to-definition, backlinks, and the streams bench over `workspace/executeCommand`. The obvious next question is whether a coding agent should search the vault through that same server. It should not, and the reasoning below is what settles it.

LSP is built around a buffer. Its methods take a document URI and a cursor position, and they assume a `didOpen` sync and an `initialize` handshake before any of that means anything. An agent has no buffer and no cursor, so every agent-facing call collapses onto `workspace/executeCommand`, which is LSP used as a bare RPC transport. The handshake, the document sync, and the position machinery all still cost something, and none of them do any work for a caller with no document. It also needs a client. An agent can call a CLI through its shell today, whereas talking to the server means writing or embedding an LSP client first.

The costs point the same way. Measured on the 150-note vault in 2026-09:

| Path | Cost |
| --- | --- |
| Import the service layer alone | 192 ms, of which duckdb is 147 ms |
| Import `yak_shears.lsp.server` | 703 ms, of which `lsprotocol.types` alone is 444 ms |
| Language server cold start, median | 832 ms |
| Language server warm round trip, p95 | 5.4 ms constant, 73 ms search |
| Cold `python -c` search, real time | 190-210 ms warm-cache, 97 hits |

The daemon exists to amortize a cost the editor pays hundreds of times per session on keystrokes. An agent runs a handful of searches per task, so 200 ms per invocation is invisible and 500 ms of protocol imports buys nothing. More than half the server's startup is a protocol the agent would not use.

This matches the position [PLAN.md](./PLAN.md) already took for the language server: no second transport, and a shell CLI wraps the same service functions rather than talking to the server.

#### The constraint that shapes it

DuckDB allows one writer or many readers, never both, and every read path here forces an index refresh, which takes the write lock. Two measurements, both reproducible:

- Four concurrent searches all succeed and serialize: one returns in 173 ms, the other three in roughly 930 ms. Contention degrades rather than fails
- A search running while any other process holds the index open deletes the entire index and rebuilds it. `check_tables_exist` returns False on any exception including a lock conflict, `ensure_search_db_ready` reads that as corruption, unlinks the file, and pays 600 ms to re-scan 150 notes. Nothing is lost, because the index is rebuildable and the vault is the source of truth, but with an editor holding the server open this fires on every single CLI search

The second one is a defect independent of any agent work, and it is why the swallowed-exception item in [PLAN.md](./PLAN.md) Phase 2 has to land before a concurrent CLI is worth having. Fixing it is the difference between agent search being free and agent search costing a full reindex each time.

#### If it should be a Tool rather than a shell call

Wrap the CLI in a thin MCP server exposing one read-only search tool. That keeps a single implementation behind both surfaces and keeps writes out of the agent's reach by construction, since search touches nothing the vault owns.

### Semantic Search (opportunistic infrastructure)

Hybrid keyword + vector search as a **separate general-purpose CLI**, integrated through the SearchBackend seam (ADR 0002). Also the seam that later feeds embedding similarity into the related-notes panel and the network-health digest. Blueprint preserved in `archive/djot-search-sqlite-exploration.md`.

### Data Models and Aggregation

The query engine, table view, and board view moved into the near-term product phases (PLAN.md Phases 4-5). What remains longer-term:
- Optional schema validation for known `type:` values (report-style, like the doctor view)
- Block references (`[[note#heading]]`), templates for new notes, export/import
- A cluster-by-cluster adjacency matrix as a "whole vault at a glance" view (stretch; stays legible where node-link tangles)

### Workout planner (deferred)

Decision pending (see [PLAN.md](./PLAN.md)). Modeled as dated notes with structured frontmatter so streaks and a calendar become views, with a possible sibling iOS app reading and writing the Syncthing vault directly rather than through a token API. The outline below came out of the 2026-08-03 streams session and is scoped but unscheduled; it exists so the decision has a concrete shape to accept or cut.

#### The three note shapes

Each workout is its own yak; a routine orders them; a session logs into a separate completion yak. All three are plain notes and every derived number is a query.

##### Workout (`type: workout`)

One unique movement or exercise. The body carries form notes, links, and media (the vault already handles attachments).

```yaml
type: workout
name: Goblet squat
equipment: kettlebell
```

##### Routine (`type: routine`)

An ordered program over workouts, with reps and rest. Order is the list order; bi-directionality (which routines use a workout) comes from the index, like streams.

```yaml
type: routine
name: Tuesday strength
schedule: 2/week
sequence:
  - workout: "[[2026-07-01T10_00_00Z]]"
    sets: 3
    reps: 8
    rest: 90
  - workout: "[[2026-07-01T10_02_00Z]]"
    sets: 3
    reps: 12
    rest: 60
```

`schedule` reuses the habits vocabulary verbatim, so a routine gets streaks, earned grace, and the heat row for free from the habits machinery. A routine is a habit whose completion happens to produce a log.

##### Session log (`type: workout-log`)

Created by finishing a timer run. One note per session, filename is the session instant as usual, so history is chronological by construction.

```yaml
type: workout-log
routine: "[[2026-06-30T09_00_00Z]]"
completed:
  - workout: "[[2026-07-01T10_00_00Z]]"
    sets: 3
    reps: [8, 8, 6]
    weight: 24
```

Actuals diverge from the plan freely (`reps` as a list, optional `weight`); the plan stays in the routine note and never mutates.

#### The timer

The routine page runs the session: current workout large, set counter, a rest countdown that starts when a set is marked done, next workout on deck. One press per set, matching the one-press habit key. Finishing writes the log yak and marks the routine's habit completion in the same action.

Timer state lives in the page (JS), never in files; abandoning a session writes nothing. This is the one surface where client-side state is genuinely required, and it still ends in a single file write.

#### Views

- Routine bench: routines with their habit-derived streaks and next-scheduled state, one press to start
- History: logs grouped by routine, actuals against plan (did reps trend up)
- A workout's page shows which routines use it and its recent actuals (backlinks plus a filtered log query)

#### Open questions

- Weights and progression: store per-set weight in logs only (above), or also a current working weight in the routine's sequence entries
- Rest semantics: per-entry `rest` (above) versus a routine-level default with overrides
- The iOS question from ROADMAP stands: a phone at the gym with flaky connectivity wants the vault-direct sibling app or offline support; the timer page is the first surface that genuinely suffers without it
- Whether `equipment` and similar workout fields deserve completion/validation (the Phase 3 frontmatter-key mechanic) or stay free text

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
