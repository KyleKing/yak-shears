# Yak Shears: Phased Implementation Plan

Derived from the three-part audit (correctness, security, architecture) of `yak_shears/`. Phases are ordered by risk and dependency: security and data-integrity fixes first, then the state model, then the search abstraction the roadmap depends on. Each item cites the file to change and a done-criteria so the next session can work without re-deriving context.

## Phase 0: Confirmed defects (do first)

These are verified bugs that cause silent data loss or arbitrary filesystem access. Both should ship with regression tests, since neither is currently covered.

- Path-traversal containment on all note operations. Add a single resolver used by `read_yak`/`save_yak`/`delete_yak` (`_yak/services.py:145-190`), `create_yak` (`_yak/services.py:128-142`, guards the `category` field), and `yak_preview_handler` (`_yak/handlers.py:203-210`). Logic: `full = (yak_dir / rel).resolve()` then reject when `not full.is_relative_to(yak_dir.resolve())`, reject `..` segments and leading `/`, and require the `.dj` suffix. Done when `../../etc/passwd` and `/etc/passwd` style inputs are rejected on read, write, delete, create, and preview, each with a test.
- Duplicate links no longer wipe a note's index. `extract_all_links` (`links.py:104-125`) emits one tuple per occurrence, which violates the `yak_links` primary key in `replace_links` (`_yak/database.py:234-248`); the failure is swallowed by `index_yak_metadata` (`_yak/services.py:208`), leaving the note with no backlinks. Fix by de-duplicating in `extract_all_links` (preserve first-seen order) or switching the insert to `INSERT OR IGNORE`. Done when a note with a repeated `[[wikilink]]` and repeated `#tag` indexes its links and a test asserts it.

## Phase 1: Auth and session correctness

- Persist session mutations. `create_session`/`delete_session` (`_auth/storage.py:186-198`) never call `_save()`, so restarts drop logins and a logged-out token can reload as valid. Call `_save()` on both, and add a regression test asserting a session survives a fresh `UserStore.load()` and that a deleted one does not.
- Server-side session expiry. Store an expiry timestamp per session and check it in `get_user_id_from_session`; today the 1-week lifetime lives only on the client cookie, so a captured token is valid indefinitely server-side.
- Cookie and logout hardening. Make `/auth/logout` POST-only (`_auth/routes.py:9`) so a cross-origin `<img src>` cannot force logout. Set `Environment=IN_TLS_CONTEXT=TRUE` in the systemd unit so the session cookie carries `Secure` behind Caddy.
- Login rate limiting. Add per-IP and per-account throttling/backoff on `login_handler` (`_auth/handlers.py:34-83`), or document fail2ban on the login route as the chosen control.
- Secrets hygiene. Untrack `yak_shears/.yak-shears-users.json` (currently committed with a real test hash), remove it from history, and write the file with mode 0600 in `_save` (`_auth/storage.py:64-71`).
- Lower-priority: raise PBKDF2 iterations toward ~600k or move to argon2id (`_auth/password.py:34`); run a dummy hash for unknown emails in `authenticate_user` to close the timing-based user-enumeration gap.

## Phase 2: Runtime hardening and deployment fixes

- Fix the port mismatch. The systemd unit runs `serve` with no `--port` (binds `:8080`) while Caddy reverse-proxies `:8084` (`cloud-config.yaml`). Pick one port and align the unit, the Caddyfile, and the `DEPLOYMENT.md` health check.
- Fix GitOps branch. `cloud-config.yaml` polls `origin/main`, but the default branch is `yak-shears-py`; the auto-update timer currently no-ops. Point it at the real branch.
- Make `debug` configurable and default it off in `create_app` (`server/_routes.py:35`); only the dev factory `create_app_without_auth` should enable it. Flip `start()`'s `no_auth` default to `False` (`server/_routes.py:61`) and enforce the reload requirement.
- Move the search DB out of the Syncthing folder by default. `get_search_db_path()` returns `$YAK_SHEARS_DIR/yak_shears_search.db`, which Syncthing then syncs between machines and corrupts. Default `SEARCH_DB_DIR` to a non-synced local path and set `--search-db-dir` in the systemd unit.
- Offload blocking work off the event loop. Wrap the synchronous DB and `rglob` work in `search_handler` and the metadata handlers with `anyio.to_thread`, since DuckDB and full-tree scans currently run on the request path.
- Narrow the swallowed exceptions in `get_frontmatter`, `get_backlinks`, `check_tables_exist` (`_yak/database.py`), `ensure_search_index_updated`, and `_create_search_result` (`_yak/services.py`) so genuine corruption is distinguishable from empty results.

## Phase 3: Search abstraction and ripgrep backend

This is the roadmap's headline feature and the reason the earlier phases matter (a swappable backend is only safe once state and path handling are sound).

- Extract a `SearchBackend` Protocol in `_yak/services.py`: `ensure_ready()`, `refresh(yak_dir)`, `search(query) -> list[SearchResult]`. Handlers already call three service functions, so the seam is close; the prerequisite cleanup is that `_process_search_results` currently leaks DuckDB's `(path, line_num, word)` tuple shape into the service layer.
- Separate the metadata/backlinks store from the text index. They share one DuckDB file today, so "swap the search backend" also means "relocate frontmatter/links." Split them before adding a second backend.
- Add a ripgrep subprocess backend (the stated preference). Use `anyio.run_process` with `shell=False` and the `--` guard: `["rg", "--json", ..., "--", query]` so a query beginning with `-` cannot be parsed as flags, and pin the search root to the resolved `yak_dir`. Add `ripgrep` to `cloud-config.yaml`'s package list and the mise config. No index freshness logic needed, which is the point.
- Replace the Levenshtein word-table with DuckDB's FTS extension for ranked/fuzzy results. DuckDB 1.4.2 is already pinned and the DB plus lazy-update plumbing exist, so this removes the weakest code in `database.py` rather than adding a parallel system. Prefer this over tantivy-py, which adds a Rust wheel and a second index lifecycle for no gain at this corpus size.

## Phase 4: Later (embeddings and semantic search)

- Keep vectors on-box: DuckDB VSS or sqlite-vec, per the sizing in `wip-djot-search-implementation.md` (fits the 4GB CX22).
- Generate embeddings either with sentence-transformers on the VPS or a hosted embedding API called only at index time. Do not stand up a hosted vector database at a few hundred documents, and do not build FaaS: the corpus lives on the VPS disk, cold starts lose to a local subprocess, and a function would need a second data pipeline to receive the notes.

## Phase 5: Docs and repo hygiene (low urgency, do opportunistically)

- Rewrite `ARCHITECTURE.md`: it currently describes the unrelated `agent-research-platform/` subproject, not Yak Shears. Same for `wip-review-1.md`.
- Delete or clearly quarantine `DEPLOYMENT_PLUS/hosting-gemini.md` (raw LLM output; contradicts `DEPLOYMENT.md` on Cloudflare proxying).
- Reconcile `wip-djot-search-implementation.md` (SQLite FTS5 + sqlite-vec) with the shipped DuckDB implementation, or mark it as a superseded exploration.
- Correct the documented users-file backup path in `DEPLOYMENT.md` (the file lives inside the package dir, not `~/.yak-shears-users.json`).
- Prune dead code once confirmed unused in production: `write_frontmatter`/`update_frontmatter`/`remove_frontmatter_field` (`frontmatter.py`), `resolve_link` (`links.py`), and the unused `database.py` helpers (`delete_files`, `delete_words_for_paths`, `upsert_file`, `insert_words`). Note `update_frontmatter` also has a verified blank-line-accumulation bug, so fix it if you wire it in rather than deleting.

## Sequencing notes

Phase 0 is independent and should land first. Phase 1 and Phase 2 can proceed in parallel. Phase 3 depends on Phase 2's search-DB relocation and event-loop offload being in place, plus Phase 0's path resolver (the ripgrep backend must confine its search root the same way). Phase 4 depends on Phase 3's `SearchBackend` seam existing. Phase 5 is unblocked at any point.
