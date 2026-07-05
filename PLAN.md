# Yak Shears: Phased Implementation Plan

Single consolidated plan, merged from the 2026-07 code audit (formerly `NEXT_SESSION_PLAN.md`), the deferred follow-up list, the hosting notes (now in `archive/`), and the raw CLI ideas (now in [ROADMAP.md](./ROADMAP.md) Future Ideas). Priority order per 2026-07-04 decision: **deploy to Hetzner first, then continue development.**

Status legend: each item lists the file to change and done-criteria so a session can start without re-deriving context.

## Phase 1: Deploy to Hetzner (top priority)

Blockers found in `cloud-config.yaml` and `DEPLOYMENT.md` that would make the current branch fail or misbehave on a fresh VPS:

- Add `ffmpeg` to the `packages:` list in `cloud-config.yaml`. The media feature (commit 6e240cd) shells out to ffmpeg for video transcode and poster frames; a fresh VPS has none. Done when a MOV upload works on the VPS.
- Fix the GitOps branch. `gitops-update.sh` polls `origin/main` (`cloud-config.yaml:87`), but the default branch is `yak-shears-py`, so the auto-update timer never fires. Done when a push to `yak-shears-py` deploys within one timer interval.
- Fix the port mismatch. The systemd unit runs `uv run --no-sync serve` with no `--port` (binds `:8080`) while Caddy proxies `localhost:8084` (`cloud-config.yaml:66,140`). Align the unit, the Caddyfile, and the `DEPLOYMENT.md` health check on one port.
- Move the search DB out of the Syncthing folder. `get_search_db_path()` defaults into `$YAK_SHEARS_DIR`, which Syncthing syncs and corrupts. Set `--search-db-dir` in the systemd unit to a non-synced path (e.g. `/home/yakshears/.local/state/yak-shears`).
- Set `IN_TLS_CONTEXT=TRUE` in the systemd unit so the session cookie carries `Secure` behind Caddy.
- Secrets hygiene: untrack `yak_shears/.yak-shears-users.json` (committed with a real hash), purge from history, and write it with mode 0600 in `UserStore._save`.
- Post-deploy smoke test: authenticated login, note save, media upload, search, and confirm the CSP headers don't break anything in auth mode (they've only been exercised in dev).
- Docs: `DEPLOYMENT.md` prerequisites now mention ffmpeg, and the backup section points at the real users-file path (`/home/yakshears/yak-shears/yak_shears/.yak-shears-users.json`, until relocated).

Known hosting TODOs carried from `archive/hosting-new.md`: ufw rules appear to reset on VPS boot (verify and persist); create a script that snapshots manually-managed VPS files (Caddyfile, sshd_config, ufw state, systemd units) for version control.

## Phase 2: Data integrity, auth, and runtime correctness

Verified defects and hardening, safe to do in parallel with Phase 1:

- Duplicate links wipe a note's index (still unfixed). `extract_all_links` (`links.py:104-125`) emits one tuple per occurrence, violating the `yak_links` primary key in `replace_links` (`_yak/database.py:235-248`); the failure is swallowed, leaving no backlinks. De-duplicate preserving first-seen order, or `INSERT OR IGNORE`. Done when a note with a repeated `[[wikilink]]` and repeated `#tag` indexes correctly, with a test.
- Session persistence and expiry. `create_session`/`delete_session` (`_auth/storage.py:186-198`) never call `_save()`: restarts log everyone out and a deleted token can resurrect. Also store per-session expiry server-side (the 1-week lifetime lives only in the cookie). Previously judged "not worth it" for single-user; deployment changes that calculus.
- Make `/auth/logout` POST-only (`_auth/routes.py`) so a cross-origin `<img src>` cannot force logout.
- Login rate limiting on `login_handler` (`_auth/handlers.py`), or document fail2ban on the login route as the chosen control.
- Flip `start()`'s `no_auth` default to `False` (`server/_routes.py:130`); the fail-closed guard already exists, so this is now a small change. Make `debug` configurable and default off in `create_app`.
- Offload blocking work: wrap synchronous DuckDB and `rglob` calls in `search_handler` and metadata handlers with `anyio.to_thread`.
- Narrow swallowed exceptions in `get_frontmatter`, `get_backlinks`, `check_tables_exist`, `ensure_search_index_updated`, `_create_search_result` so corruption is distinguishable from empty results.
- Lower priority: raise PBKDF2 iterations toward ~600k or move to argon2id; dummy-hash unknown emails in `authenticate_user` to close timing-based user enumeration.

## Phase 3: Media hardening

The upload/transcode/doctor feature shipped without automated coverage:

- pytest coverage for `_yak/media.py` and the media routes (upload validation, dedupe-by-hash, HEIC and video transcode paths can be unit-tested with small fixtures; route auth).
- Doctor view: add a delete action for orphaned attachments (currently report-only).
- Known edge case: `execCommand insertText` collapses surrounding newlines when inserting at offset 0 of a note.
- Deferred by choice: drag-drop upload (paste + toolbar button only, per 2026-07-04 decision).

## Phase 4: Search abstraction and ripgrep backend

Depends on Phase 1's search-DB relocation and Phase 2's event-loop offload.

- Extract a `SearchBackend` Protocol in `_yak/services.py`: `ensure_ready()`, `refresh(yak_dir)`, `search(query) -> list[SearchResult]`. Prerequisite: `_process_search_results` currently leaks DuckDB's `(path, line_num, word)` tuple shape into the service layer.
- Separate the metadata/backlinks store from the text index (they share one DuckDB file; swapping search backends must not relocate frontmatter/links).
- Add a ripgrep subprocess backend: `anyio.run_process` with `shell=False` and the `--` guard (`["rg", "--json", ..., "--", query]`), search root pinned to the resolved `yak_dir`. Add `ripgrep` to `cloud-config.yaml` packages and mise config.
- Replace the Levenshtein word-table with DuckDB's FTS extension for ranked/fuzzy results (removes the weakest code in `database.py`; preferred over tantivy-py at this corpus size).

See [adr/0002-search-backend-strategy.md](./adr/0002-search-backend-strategy.md).

## Phase 5: Link intelligence

ROADMAP Phase 3, unblocked once the backlinks store is stable (Phase 2 dedupe fix, Phase 4 store split):

- `[[` autocomplete in the editor (prefix match, then recent, then frequent).
- Fuzzy link resolution and broken-link detection (the media doctor view is the pattern to follow: report first, actions later).
- Link preview on hover.
- Editor completion help for frontmatter keys (deferred idea from the frontmatter decision, same UI mechanics as autocomplete).

## Phase 6: Semantic search (separate general-purpose CLI)

Direction per 2026-07-04 discussion: build or adopt this **outside** yak-shears as a general-purpose document-search CLI, integrated later via the Phase 4 `SearchBackend` seam as a subprocess. Rationale in [adr/0002](./adr/0002-search-backend-strategy.md).

- First, evaluate existing tools before building (the space moves fast; check current options for local hybrid search CLIs).
- If building: the SQLite FTS5 + sqlite-vec + small-embedding-model design in `archive/djot-search-sqlite-exploration.md` is the blueprint. SQLite is the right call for a standalone CLI (single file, no server, easiest install); its phases 1-3 (BM25, vectors with all-MiniLM-L6-v2, incremental ingestion) fit the 4GB CX22. Stop before its phases 4-5 (chunking, query expansion) at a few-hundred-doc corpus.
- Do not stand up a hosted vector DB or FaaS at this scale; embeddings run on-box or via a hosted embedding API at index time only.

## Phase 7: Lint debt and code pruning (opportunistic)

- Burn down the ~51 project-wide ruff findings (DOC201, RUF067, the lazy import in `highlight_content`).
- Fix undefined `--space-1` CSS var usage in `main.css` (~line 1403/1684).
- Prune dead code once confirmed unused: `write_frontmatter`/`update_frontmatter`/`remove_frontmatter_field` (`frontmatter.py`, intentionally unwired per the frontmatter ADR; `update_frontmatter` also has a verified blank-line-accumulation bug, so fix it if ever wired in rather than deleting silently), `resolve_link` (`links.py`), and unused `database.py` helpers (`delete_files`, `delete_words_for_paths`, `upsert_file`, `insert_words`).
- Editor caret fragility (known, low priority): rAF-based `_setCursorPosition` races if Tab/Shift+Tab arrive faster than one frame; fine at human speed.

## Sequencing

Phase 1 first (user priority). Phase 2 in parallel where it doesn't touch deployment files. Phase 3 anytime. Phase 4 depends on Phases 1-2 as noted; Phase 5 on Phases 2/4; Phase 6 on Phase 4's seam. Phase 7 is filler work between phases.
