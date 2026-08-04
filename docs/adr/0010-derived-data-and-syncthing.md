# 0010: Derived Data and Syncthing

## Status

Accepted (2026-07-22) for the search index. The embedding cache half is a shape, not a commitment: nothing is built until embeddings exist.

## Context

The vault at `~/Sync/yak-shears` is a Syncthing folder. Until this change the DuckDB search index lived inside it, at `~/Sync/yak-shears/yak_shears_search.db`, because that was the default in `get_search_db_path()`. Production already overrode it with `--search-db-dir`, so the risk was local-only, but the default is what most machines get.

Two facts make that default wrong.

DuckDB keeps a `.wal` sidecar next to the database while a connection is open, and folds it into the main file only on close. Verified locally: opening a database and inserting a row produces `t.db` and `t.db.wal`, and the sidecar disappears on `close()`. So while the server is running, the `.db` on disk is not a complete database. A file-level copy of it alone is stale or torn.

Syncthing copies files, not transactions. It has no way to know a `.db` is mid-write, and the maintainers have never claimed otherwise. The [long-standing request to take file locks while syncing](https://github.com/syncthing/syncthing/issues/4242) exists precisely because Syncthing does not. Users syncing active SQLite files report [a database that generates a sync-conflict copy on every write cycle](https://forum.syncthing.net/t/sync-conflict-with-1-specific-sqlite-file-constantly/20836), which is the same failure mode.

The second machine makes it worse. Two devices both running the app each write their own copy of the same database file. Syncthing cannot merge two binary files, so it picks a winner and renames the loser to `*.sync-conflict-*`. Neither copy is a merge of both machines' indexing work.

Against that, there is a real argument for syncing *some* derived data. If embeddings are added (ROADMAP, "Semantic Search"), they cost API calls or GPU time to produce. Recomputing the same vectors on every machine is money and minutes spent to arrive at bytes another machine already has. So the question is not "sync derived data or not", it is which derived data.

## Decision

Split derived data by how expensive it is to recompute and by whether it can be merged.

1. The live search index is never synced. Default it to a machine-local state directory (`$XDG_STATE_HOME/yak-shears`, falling back to `~/.local/state/yak-shears`), which every machine rebuilds for itself. `SEARCH_DB_DIR` still overrides.
2. Doctor reports where the index resolved to, warns when that is inside the vault, and flags a stray `yak_shears_search.db` left behind by the old default.
3. No `.stignore` is written by the app. A file the app generates inside a folder the user configures in Syncthing is the user's to own. Doctor tells them what to add.
4. When embeddings arrive, they go in a content-addressed immutable cache that *is* synced, and never in the DuckDB file.

## Why the index is cheap to abandon and embeddings are not

The word index rebuilds from the vault in 1.7s for 600 files (measured after the CSV bulk-load change, ROADMAP "Search performance"). Syncing it would trade a guaranteed corruption class for saving under two seconds per machine. That is not a trade.

Embeddings invert both terms. They are expensive to produce and they are *reproducible*: the same text through the same pinned model gives the same vector, so a cache entry from another machine is exactly as valid as one computed locally. That is the property that makes syncing safe, and it is also what dictates the format.

## The shape of a sync-safe embedding cache

Store one immutable record per `(model, model_version, content_hash)`, laid out as files:

```
.embeddings/<model>-<version>/<hash[:2]>/<hash>.f32
```

Every property here is chosen against Syncthing's actual behaviour:

- Immutable and write-once. A file is created and never rewritten, so there is no mid-write window for a copy to land in
- Content-addressed. Two machines embedding the same note write the same bytes to the same path. A conflict is byte-identical, so either copy is correct
- Many small files rather than one index. A single Parquet or JSONL cache is rewritten on every append, which is the sync-conflict generator all over again
- Sharded by hash prefix, so no directory grows past a few thousand entries
- Model and version in the path. [Restoring a cache across an embedding-model change restores the old coordinate space](https://bh3r1th.medium.com/the-vector-embedding-cache-bug-that-costs-nothing-and-corrupts-everything-157be6c575e8), which is the bug this naming prevents: a new model simply cannot read the old model's entries

The live vector index (whatever serves nearest-neighbour queries) is built locally from the vault plus this cache, exactly like the word index. It is never synced.

## What testing would settle this

The claims above are testable, and two of them are worth testing rather than asserting. `tests/test_sync_safety.py` covers the first; the second is a benchmark script, not a test, because its answer is a number rather than a pass or fail.

**Does a mid-write copy actually break?** Write to the index continuously while copying the `.db` at random moments, the way Syncthing would, then try to open each copy and run a query. Record how many copies are unreadable, and how many open but return stale or partial data. The second number matters more: a database that fails loudly is a bad day, one that silently returns half an index is a bug report about search being wrong.

Run against this schema and DuckDB version, the answer is unambiguous: **20 of 20 copies taken while a writer held the database failed to open at all.** None were merely stale, and none were faithful. So a synced index does not degrade gracefully, it arrives dead, and the app falls back to reinitialising anyway. That is the good version of this failure and it is still a reason not to sync: the transfer is pure cost, and on a second machine it fights the local index for the same path.

**Is rebuilding cheaper than transferring?** Time a full index rebuild against the vault, and compare with the on-disk size of the index and the time to transfer it. The crossover decides whether an artifact is worth syncing at all. Run it again when embeddings land, where the inputs are an API bill and a GPU minute rather than a local CPU second.

Two more that only become answerable once embeddings exist:

**Is the same model deterministic across machines?** Embed the same text on two machines with the same pinned model and compare bytes. Identical means syncing is purely a cost optimisation. Not identical (batching or GPU kernel nondeterminism) means syncing also buys consistency, and the cache becomes more valuable, not less.

**Do concurrent writers actually stay conflict-free?** Have two processes embed overlapping sets of notes into the same cache directory, sync, and count `*.sync-conflict-*` files. The prediction is zero, or only byte-identical ones. A non-identical conflict would mean the content hash is not capturing everything that determines the vector, which would be a bug in the key.

## Logging

The index already logs per-search stage timings (`SEARCH query_len=... index_ms=... total_ms=...`). Two additions are worth having before any of this is tuned further:

- Index rebuilds log why they ran (interval elapsed, file changed, forced by Doctor), how many files were scanned, how many rows were written, and how long it took. Without the reason, a slow search is indistinguishable from a search that happened to trigger a rebuild, which is exactly the confusion that hid the float32 mtime bug for so long
- Doctor shows the resolved index path, whether it is inside the vault, and any stray copy. Location is the one piece of index state a user cannot discover from the app otherwise

When an embedding cache exists, add hit and miss counts per request. A miss rate that does not fall towards zero is the signal that the cache key is wrong.

## Consequences

Every machine rebuilds its own index on first run after this change, once, in seconds. Anyone whose index was in the vault has a stray file to delete and a `.stignore` line to add, both surfaced by Doctor. Nothing in the vault is authoritative that was not already, and the vault remains the only backup that matters.

## Sources

- [Syncthing: lock files with fcntl while syncing](https://github.com/syncthing/syncthing/issues/4242)
- [Syncthing forum: constant sync conflicts on one SQLite file](https://forum.syncthing.net/t/sync-conflict-with-1-specific-sqlite-file-constantly/20836)
- [Syncthing ignore-pattern reference](https://docs.syncthing.net/users/ignoring.html)
- [The vector embedding cache bug that costs nothing and corrupts everything](https://bh3r1th.medium.com/the-vector-embedding-cache-bug-that-costs-nothing-and-corrupts-everything-157be6c575e8)
- [ADR 0002](./0002-search-backend-strategy.md) for the backend seam this sits behind
