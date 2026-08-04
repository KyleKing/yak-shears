# 0002: Search Backend Strategy

## Status

Accepted (2026-07)

## Context

Search shipped on a hand-rolled DuckDB word table with Levenshtein fuzzy matching. It works but is the weakest code in `_yak/database.py`: the index lives in the Syncthing-synced notes directory (corruption risk), freshness requires lazy-update plumbing, and the result-tuple shape leaks into the service layer.

An earlier exploration (`archive/djot-search-sqlite-exploration.md`) proposed SQLite FTS5 + sqlite-vec + sentence-transformers for hybrid keyword/semantic search. Adopting it inside the app would mean a second database engine alongside DuckDB and an ML pipeline coupled to the webserver, for a corpus of a few hundred short notes.

## Decision

1. Extract a `SearchBackend` protocol (`ensure_ready()`, `refresh()`, `search()`) so backends are swappable, and split the metadata/backlinks store from the text index.
2. In-app text search uses ripgrep as a subprocess backend (no index, no freshness problem) and/or DuckDB's FTS extension for ranked results, replacing the Levenshtein word table.
3. Semantic/hybrid search is out of scope for the app itself. It will be a separate general-purpose CLI (existing tool if one fits, otherwise built on the SQLite FTS5 + sqlite-vec design) that yak-shears invokes through the `SearchBackend` seam.

## Rationale

- ripgrep is exact-match but index-free: zero corruption or staleness risk, trivial to confine to the resolved notes root, fast at this corpus size
- DuckDB FTS reuses the engine and DB already pinned, rather than adding SQLite alongside it; tantivy-py was rejected (Rust wheel plus a second index lifecycle for no gain)
- A standalone semantic-search CLI is reusable beyond this project, keeps torch/sentence-transformers out of the webserver's dependency tree, and SQLite is the right storage for a standalone tool (single file, no server). Vectors stay on-box (fits a 4GB CX22); no hosted vector DB or FaaS at a few hundred documents

## Consequences

- Handlers must stop depending on DuckDB's `(path, line_num, word)` tuple shape before a second backend can exist
- `ripgrep` becomes a system dependency (cloud-config packages, mise config)
- Semantic search quality work happens in a separate repo/CLI with its own lifecycle
