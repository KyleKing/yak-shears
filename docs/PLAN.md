# Yak Shears: Phased Implementation Plan

Single consolidated plan, merged from the 2026-07 code audit, the deferred follow-up list, the hosting notes, the raw CLI ideas (now in [ROADMAP.md](./ROADMAP.md)), and the 2026-07 feature brainstorm (folded in here from the former `NEXT_FEATURES.md`).

Priority order (2026-07-06 decision): **deploy first (Phase 1), then auth/data hardening (Phase 2), then the product features (the query-engine keystone and the views on top, Phases 3-7).** Infrastructure polish (media hardening, the search text-backend swap, the semantic CLI, lint) is opportunistic and slots around the product phases rather than blocking them. The workout planner is deferred pending a scope decision.

Status legend: each item lists the file to change and done-criteria so a session can start without re-deriving context.

## Phase 1: Deploy to Hetzner — done (2026-07-22)

Blockers found in `cloud-config.yaml` and `DEPLOYMENT.md` that would have made the branch fail or misbehave on a fresh VPS, all fixed pre-deploy:

- Added `ffmpeg` to the `packages:` list. The media feature shells out to ffmpeg for video transcode and poster frames.
- Fixed the GitOps branch (`origin/main` -> `origin/yak-shears-py`) so the auto-update timer actually fires.
- Fixed the port mismatch: the systemd unit now passes `--port 8084`, matching what Caddy proxies.
- Moved the search DB out of the Syncthing folder via `--search-db-dir /home/yakshears/.local/state/yak-shears`.
- Set `IN_TLS_CONTEXT=TRUE` in the systemd unit so the session cookie carries `Secure` behind Caddy.
- Secrets hygiene: `yak_shears/.yak-shears-users.json` confirmed gitignored and never committed; `UserStore._save` chmods it to 0600.
- Post-deploy smoke test: login, note edit/save/reload, image upload all confirmed working. **Still open**: video transcode, search-returns-results, and a CSP-violation console check haven't been exercised in production yet — do these before treating the deploy as fully verified.

Issues hit during the actual run (not caught by the pre-flight audit above; full detail in [DEPLOY_LOG.md](./DEPLOY_LOG.md)), now fixed in `cloud-config.yaml` and code:

- `runcmd` aborted partway through provisioning: `apt install caddy` hit an interactive dpkg prompt (conffile conflict with the `write_files`-written Caddyfile) with no TTY, so the RuntimeError killed everything after it in the script. Fixed with `DEBIAN_FRONTEND=noninteractive` + `--force-confdef --force-confold` on that install step.
- `AllowTcpForwarding no` in the SSH hardening drop-in silently blocked `ssh -L`, breaking the documented Syncthing-pairing tunnel. Changed to `AllowTcpForwarding local` (permits `-L`, still blocks `-R`).
- The user store (`_auth/storage.py`) was a module-level singleton loaded once at process start, so a user created via the `yak-shears-users` CLI (a separate process) was invisible to the already-running server until restart. Fixed properly: `authenticate_user` now checks the data file's mtime and reloads if it changed, so CLI-created users work without a manual restart.

Known hosting TODOs, now resolved or re-scoped:

- ufw rules resetting on boot: verified fixed — a full reboot on the live VPS kept ufw active with all rules intact.
- A script that snapshots manually-managed VPS files (Caddyfile, sshd_config, ufw state, systemd units) for version control: still not built: everything currently manageable lives in `cloud-config.yaml` (single source of truth re-applied only at provision time, not continuously reconciled), so drift between the file and the live box is possible after ad hoc SSH fixes like the ones above. Worth a `cloud-config.yaml` diff check next time the VPS is touched by hand.
- Logging/alerting strategy: decided and built (2026-08-16). [adr/0007-observability-strategy.md](./adr/0007-observability-strategy.md) records Option E: a daily journald export as JSONL into a send-only Syncthing folder, ntfy on deploy outcomes, and `yak-shears.kyleking.me` added to the existing external uptime monitor. Push-on-error is knowingly absent; the ADR says what would close it.
- Deploy safety: the GitOps timer checks CI before pulling, health-checks the restart, and rolls back a commit that does not answer. The scripts installed on the box were extracted from `cloud-config.yaml` rather than hand-edited in place, so the two match as of 2026-08-16.

## Phase 2: Data integrity, auth, and runtime correctness

Verified defects and hardening, safe to do in parallel with Phase 1. The link-dedupe fix is the foundation for every link, related-notes, and grouping feature in Phases 3-6.

- Duplicate links wipe a note's index: fixed (2026-08-30). `extract_all_links` emits one tuple per occurrence, which violated the `yak_links` primary key in `replace_links`, and the swallowed failure left the note with no backlinks until the next full vault scan. `replace_links` now inserts with `INSERT OR IGNORE`, matching `update_index_batch` on the scan path, covered by `TestLinks::test_repeated_links_survive_the_primary_key`.
- Session persistence and expiry. `create_session`/`delete_session` (`_auth/storage.py:186-198`) never call `_save()`: restarts log everyone out and a deleted token can resurrect. Also store per-session expiry server-side (the 1-week lifetime lives only in the cookie). Previously judged "not worth it" for single-user; deployment changes that calculus.
- Make `/auth/logout` POST-only (`_auth/routes.py`) so a cross-origin `<img src>` cannot force logout.
- Login rate limiting on `login_handler` (`_auth/handlers.py`), or document fail2ban on the login route as the chosen control.
- Flip `start()`'s `no_auth` default to `False` (`server/_routes.py:130`); the fail-closed guard already exists, so this is now a small change. Make `debug` configurable and default off in `create_app`.
- Offload blocking work: wrap synchronous DuckDB and `rglob` calls in `search_handler` and metadata handlers with `anyio.to_thread`.
- Narrow swallowed exceptions in `get_frontmatter`, `get_backlinks`, `check_tables_exist`, `ensure_search_index_updated`, `_create_search_result` so corruption is distinguishable from empty results. `check_tables_exist` returning False on a DuckDB lock conflict is the sharp edge: `ensure_search_db_ready` reads it as corruption and unlinks the index, so any second process running while another holds the index open pays a full rebuild (reproduced 2026-09-02, 600 ms over 150 notes). This blocks the agent-facing search CLI below.
- Lower priority: raise PBKDF2 iterations toward ~600k or move to argon2id; dummy-hash unknown emails in `authenticate_user` to close timing-based user enumeration.

### Editor draft recovery (UI wiring pending)

Migrated from the stale `yak-shears-py` checkout (its commit `4b06c6a`). The edit page currently discards unsaved localStorage drafts silently (the old `TODO: Show UI for switching between server/local versions` in `editor.js:initEditor`). The template bar (`#draft-toggle` in `edit.html.jinja`, rendered `hidden`) and a skipped e2e test (`test_draft_toggle_recovers_local_changes`) are already committed; the JS/CSS could not land because `static/` was being reworked at migration time. To finish:

- In `initEditor`, replace the `console.log` in the `saved && saved !== serverContent` branch with `_setupDraftToggle(saved, serverContent)`, and hide the bar again on successful save (next to `localStorage.removeItem(storageKey)`)
- Add the helper (switching uses `jar.updateCode()`, which does not fire `jar.onUpdate()`, so previewing the server version never deletes the stored draft):

```js
function _setupDraftToggle(saved, serverContent) {
	const serverBtn = document.getElementById("draft-server-btn");
	const localBtn = document.getElementById("draft-local-btn");
	document.getElementById("draft-toggle").hidden = false;

	const applyVersion = (content, activeBtn, otherBtn) => {
		jar.updateCode(content);
		activeBtn.classList.add("active");
		otherBtn.classList.remove("active");
		updateSaveStatus(content === serverContent ? "Synced" : "Modified");
		if (currentView === "side-by-side" || currentView === "preview") {
			renderPreview(content);
		}
	};

	serverBtn.addEventListener("click", () => applyVersion(serverContent, serverBtn, localBtn));
	localBtn.addEventListener("click", () => applyVersion(saved, localBtn, serverBtn));
}
```

- CSS: style `.draft-toggle` like the `.view-toggle` group (surface-alt buttons, accent `.active`), constrained to the editor's 1200px column; include a `.draft-toggle[hidden] { display: none; }` rule since any `display: flex` on the class would defeat the `hidden` attribute
- Unskip `test_draft_toggle_recovers_local_changes`; done when it passes

## Phase 3: Link intelligence and related notes

The first product surface, and the foundation of the grouping story (Phase 6). Formerly the standalone "link intelligence" phase, now carrying the related-notes panel.

**Shipped**: the `[[` completion (`/api/links` ranks prefix matches first, then inbound links, then recency, and an empty query lists the most recent notes), its second trigger on the same resolver (Ctrl+K, and a `[[` key on the command panel, either one turning a selection into the query), and the related-notes panel in the editor's metadata pane. The vault scan now records outbound links, which it never did before, so a note that arrived over Syncthing rather than through the editor counts toward backlinks, ranking, and relatedness.

**Still open** in this phase:

- Fuzzy link resolution and broken-link detection (the media doctor view is the pattern to follow: report first, actions later).
- Editor completion help for frontmatter keys (same UI mechanics as `[[` autocomplete). This mechanic also drives the `color`/`stream`/`state` field completion in Phase 5.
- The patchbay: render links and backlinks as visible routing rather than as a count, on the editor first and then the rack. Described in [DESIGN.md](./DESIGN.md) under "Still open from the redesign".
- Widen the related-notes panel past the editor, and fold in embedding similarity once the semantic CLI lands (opportunistic infra). Ranking today is structural only (shared outbound links, shared tags, co-citation), capped at 8, computed in `_yak/related.py` over the whole edge list.

## Phase 4: Frontmatter query engine and store split (keystone)

The single primitive under Phases 5-6: query and aggregate notes by frontmatter, sorted, filtered, and grouped, rendered as views. Everything downstream (prune queue, streams, backlog, triage) is a thin view on this. Per the 2026-07-06 "couple them" decision, this phase also does the metadata/text store separation the old search-abstraction phase planned, because the query engine reads the frontmatter store and it should not be relocated twice.

- Build the query/aggregation surface over the frontmatter store: `select` by field, `filter`, `sort`, `group`. Results must be reconstructable from files, so no app-owned membership state (a "stream member" is a query result, not a stored list).
- Separate the metadata/backlinks store from the text index (carried from the old Phase 4). Swapping the text backend later (ripgrep/FTS, opportunistic) must not relocate the frontmatter/links store. Prerequisite noted previously: `_process_search_results` leaks DuckDB's `(path, line_num, word)` tuple shape into the service layer; clean that seam as part of the split.
- Done when a view can render "notes where `state in {backlog, queue}` ordered by modified" purely from the store, and when the text-search backend can be swapped without touching the frontmatter/links store.

## Phase 5: Product views (prune queue, streams, backlog)

Thin views on the Phase 4 engine. Nothing here introduces state that cannot be rebuilt from the vault.

**Shipped ahead of Phase 4**, reading frontmatter directly rather than through the query engine: the streams canal at `/streams` (three reaches, the latch and command deck, every write through `rewrite_frontmatter_field` with an inverse for undo), the habits bench at `/habits` (schedules, streaks, grace, makeup, heat rows), the lists rack at `/lists`, and the `/benches` hub. Each of those readers is what Phase 4 replaces, so the engine lands under working views instead of under a blank page. Design in [STREAMS-DESIGN.md](./STREAMS-DESIGN.md), vocabulary in [DESIGN.md](./DESIGN.md).

**Still open** in this phase: the prune queue below, and the palette and completion work under Work Streams.

### Daily prune / review queue

- Surface a few old notes per day on a spaced interval for re-read, edit, merge, or prune (the note-rot-fighting idea, flashcard framing dropped). Frontmatter `last-reviewed` plus a review interval, a little date math, and a view. Pairs with the Phase 3 related-notes panel: surface a stale note together with its neighbors so a review can end in a merge or a new link. Build this first as the smallest thin view that proves the pattern.

### Work Streams and Backlog

Board and table views over task-notes. A stream is a note; a task is a note that names a stream by id. Bi-directionality (which tasks belong to a stream) comes from the index, not a list inside the stream note.

- Stream note frontmatter: `type: stream`, `id` (short slug tasks reference), `name` (display), `color` (one palette name), optional `wip-limit`.
- Task note frontmatter: `state` (`backlog | queue | in-progress | complete | not-planned`, no `on-hold` per the lifecycle decision), optional `stream` id, optional `soft-deadline` / `hard-deadline`.
- Views: board (group task-notes by `state`, filtered by `stream`), backlog table (same data, sortable), triage bucket (task-notes with no `stream` or no `state`).
- Named color palette as a single schema artifact driving `color:` completion, swatch rendering, and the Doctor validity check. Draft palette (validate light/dark contrast before locking, may extend toward ~18): fjord, teal, moss, sage, amber, clay, rust, rose, plum, slate. Lock these against the console's anodize band (58-82% saturation, 48-68% lightness per DESIGN.md) rather than picking them free-hand, or stream chips and category caps will read as two unrelated color systems. Note that `amber` collides with the panel's one lit color, which means armed; rename it or accept that a stream can look like a live control.
- In-editor completion/validation (Phase 3 mechanic): `color:` from the palette (with swatches), `stream:` from existing stream-note ids, `state:` from the enum, `type:` offering `stream`. Advisory highlight, never blocks a save (files stay plain text per ADR 0003).
- Doctor checks: stream-reference integrity (task referencing a missing stream), color validity (a `color` not in the palette), WIP-limit warnings (stream over its `wip-limit`), alongside the existing broken-link and orphan checks.
- The small-active-set WIP limit (tiled, space-limited streams ordered by recency/blocked) is a **view** constraint, not a data cap.

## Phase 6: Grouping and network navigation (the anti-graph)

Design stance from the competitive research (folded from `NEXT_FEATURES.md`): **compute and surface, do not draw.** The Obsidian-style global force-directed graph is a hairball with no stable spatial memory and flat edges; it is a diagnostic at best, never a navigation tool. Value lives in computed clusters, hubs, bridges, and gaps delivered as explainable lists. The global graph is demoted to a diagnostics tab or skipped.

- The Phase 3 inline related-notes panel is the primary day-to-day navigation surface (stated there, foundational here).
- Bounded local graph (current note plus 1-2 hops) as the only picture drawn. Encode note type, state, and recency as color and size so it carries operational meaning. It never hairballs because the visible set is bounded.
- Living hub notes (`type: hub`, reusing the streams `type:` machinery): a hub declares a query and the index resolves current members, so membership is **derived** and a new note joins its hubs automatically (this is your central "node note" idea done so it cannot go stale). Auto-draft a candidate hub per detected cluster, seeded by the cluster's most central notes, for the user to curate. Distinguish **structural** backlinks (a hub indexing this note) from incidental **mentions**.
- Network-health digest (scheduled, Doctor-adjacent): emergent themes via Leiden community detection diffed week over week; bridge notes via betweenness centrality (each naming the two clusters it joins); a hub leaderboard via PageRank (flag hubs grown enough to promote into a `type: hub`); orphans via a zero-backlink query, each shown with top-N suggested connections. Batch compute in `networkx` or `python-igraph` (sub-second at this corpus size); add the dependency to `cloud-config.yaml`/mise. Leiden over Louvain (guarantees connected communities, faster).
- Hard rule that keeps this file-first: computed signals (cluster ids, centrality, similarity edges) live only in the rebuildable index, never written into notes. Only explicit user actions (accepting a drafted hub, accepting a suggested link) mutate `.dj` files, so a vault checked out elsewhere still round-trips verbatim.
- Embedding similarity for the related-notes panel and orphan suggestions rides in when the semantic CLI lands (opportunistic infra), through the same seam.

## Phase 7: External references (read-only)

- A note references an external item in frontmatter (`linear: ENG-123`, `github: owner/repo#45`), rendered as a badge/link. Optional read-only status enrichment much later. Never two-way sync: it breaks file-first and no-lock-in, needs secrets on the VPS, and is a maintenance tax as those APIs change.

## Opportunistic infrastructure

Lower priority per the 2026-07-06 product-first decision. Do these between product phases; none blocks the product work except where noted.

### Media hardening (formerly Phase 3)

The upload/transcode/doctor feature shipped without automated coverage:

- pytest coverage for `_yak/media.py` and the media routes (upload validation, dedupe-by-hash, HEIC and video transcode paths can be unit-tested with small fixtures; route auth).
- Doctor view: add a delete action for orphaned attachments (currently report-only).
- Known edge case: `execCommand insertText` collapses surrounding newlines when inserting at offset 0 of a note.
- Deferred by choice: drag-drop upload (paste + toolbar button only, per 2026-07-04 decision).

### Search text-backend swap (formerly Phase 4 remainder)

The metadata/text store split moved into Phase 4 (the keystone). What remains is the swappable text backend:

- Extract a `SearchBackend` Protocol in `_yak/services.py`: `ensure_ready()`, `refresh(yak_dir)`, `search(query) -> list[SearchResult]`.
- Add a ripgrep subprocess backend: `anyio.run_process` with `shell=False` and the `--` guard (`["rg", "--json", ..., "--", query]`), search root pinned to the resolved `yak_dir`. Add `ripgrep` to `cloud-config.yaml` packages and mise config.
- Replace the Levenshtein word-table with DuckDB's FTS extension for ranked/fuzzy results (removes the weakest code in `database.py`; preferred over tantivy-py at this corpus size).

See [adr/0002-search-backend-strategy.md](./adr/0002-search-backend-strategy.md).

### Semantic search as a separate CLI (formerly Phase 6)

Direction per 2026-07-04 discussion: build or adopt this **outside** yak-shears as a general-purpose document-search CLI, integrated via the Phase 4 store seam as a subprocess. This is also the seam that later feeds embedding similarity into the Phase 3 related-notes panel and the Phase 6 network digest.

- First, evaluate existing tools before building (the space moves fast; check current options for local hybrid search CLIs).
- If building: the SQLite FTS5 + sqlite-vec + small-embedding-model design in `archive/djot-search-sqlite-exploration.md` is the blueprint. SQLite is the right call for a standalone CLI (single file, no server, easiest install); its phases 1-3 (BM25, vectors with all-MiniLM-L6-v2, incremental ingestion) fit the 4GB CX22. Stop before its phases 4-5 (chunking, query expansion) at a few-hundred-doc corpus.
- Do not stand up a hosted vector DB or FaaS at this scale; embeddings run on-box or via a hosted embedding API at index time only.

### Agent-facing search CLI

Reasoning and the measurements behind it are in [ROADMAP.md](./ROADMAP.md) ("Agent access to the vault"). The short version: a coding agent should read the vault through a short-lived CLI rather than the `shears lsp` language server, because LSP's abstractions are buffer-centric, an agent has no buffer, and the daemon's 832 ms cold start amortizes a keystroke cost an agent never pays.

Ordered, because the first item is a prerequisite rather than a preference:

- **Prerequisite.** Fix the lock-conflict-reads-as-corruption path (Phase 2's swallowed-exception item). Until then, every CLI search run while an editor holds the server open deletes and rebuilds the index. Done when a search running against a held index returns results without the `Search database appears corrupted` warning, covered by a test that opens a second connection and asserts the index file's inode survives.
- Add `shears search <query>` to the `shears` dispatcher in `yak_shears/shears.py`, next to the existing `lsp` subcommand. It calls `ensure_search_db_ready`, `ensure_search_index_updated`, and `perform_search` directly, then `close_search_db` before exit. No import of `yak_shears.lsp` and no import of the web layer, so the 192 ms service-layer floor is what a search costs.
- Give it `--json` emitting one object per hit (path, title, score, the matched excerpt) so an agent parses rather than scrapes, with the human-readable form as the default. Cap results with `--limit`, defaulting low enough that a wide query does not flood an agent's context.
- Add `shears backlinks <path>` over `get_backlinks`, asking under both the vault-relative path and the bare stem the way `_all_backlinks` in `yak_shears/lsp/server.py` already does. This is the same one-line trap the language server hit, so share the helper rather than writing it twice.
- Keep the whole surface read-only. Writes stay behind `rewrite_frontmatter_field` and the leased save path, and an agent that needs to edit a note edits the file, which the vault already treats as the source of truth.
- Document the commands in `AGENTS.md` so an agent working in this repo finds them without being told.

Deferred until the CLI exists and is used: wrapping it in an MCP server so the search shows up as a tool rather than a shell call. It adds a process and a dependency, and a shell call is already reachable from every agent harness, so it only pays once shell invocation proves to be the friction.

### Lint debt and code pruning (formerly Phase 7)

- Burn down the ~51 project-wide ruff findings (DOC201, RUF067, the lazy import in `highlight_content`).
- Fix undefined `--space-1` CSS var usage in `main.css` (~line 1403/1684).
- Prune dead code once confirmed unused: `write_frontmatter`/`update_frontmatter`/`remove_frontmatter_field` (`frontmatter.py`, intentionally unwired per the frontmatter ADR; `update_frontmatter` also has a verified blank-line-accumulation bug, so fix it if ever wired in rather than deleting silently), `resolve_link` (`links.py`), and unused `database.py` helpers (`delete_files`, `delete_words_for_paths`, `upsert_file`, `insert_words`).
- Editor caret fragility (known, low priority): rAF-based `_setCursorPosition` races if Tab/Shift+Tab arrive faster than one frame; fine at human speed.

## Deferred: Workout planner

Decision pending; not a knowledge-management feature (streaks, earned breaks, a calendar, a dedicated iOS app with a token API describe a fitness app sharing this app's auth and hosting). Two framings on record for when it is revisited:

- Model a workout as a dated note with structured frontmatter (exercises, sets, completed-at), so the streak and calendar become views and the vault gives sync, search, and no-lock-in for free.
- The Syncthing vault is already a sync layer and an API. A phone app that reads and writes `.dj` files into the vault needs no yak-shears HTTP API and no token; the token-authenticated API is only required for what the file layer cannot do (server-side queries, transcoding, a device remote from the vault), which defers an entire auth surface.

## Sequencing

Phase 1 first (user priority). Phase 2 in parallel where it does not touch deployment files; its link-dedupe fix is the foundation for Phases 3-6. Then product-first: Phase 3 (link intelligence, unblocked by the dedupe fix), Phase 4 (the query-engine keystone plus the coupled store split), Phase 5 (the prune queue, and moving the shipped stream, habit, and list views onto the engine), Phase 6 (grouping and the anti-graph navigation), Phase 7 (read-only external references). Opportunistic infrastructure slots between product phases; the semantic CLI unlocks the embedding-similarity enhancements in Phases 3 and 6. The workout planner stays deferred until its scope decision is made.
