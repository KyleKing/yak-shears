"""Evidence for ADR 0010: why the search index must not be synced.

These assert properties of DuckDB-on-disk rather than of our own code, so they
double as a regression check on the assumption. If a future DuckDB makes a
mid-write file copy safe to open, the corruption test starts failing and the
ADR deserves rereading.
"""

import shutil
import threading
from pathlib import Path as SyncPath
from unittest.mock import patch

import duckdb
import pytest

from yak_shears._yak.database import (
    close_search_db,
    get_search_db_path,
    index_is_inside_vault,
    init_search_db,
    insert_words,
    search_words,
)

WAL_SUFFIX = ".wal"


def test_duckdb_keeps_a_wal_sidecar_while_open(tmp_path: SyncPath) -> None:
    """The premise of ADR 0010: the .db alone is incomplete while in use."""
    db_path = tmp_path / "index.db"
    con = duckdb.connect(str(db_path))
    try:
        con.execute("CREATE TABLE words (path TEXT, word TEXT)")
        con.execute("INSERT INTO words VALUES ('a.dj', 'hello')")
        sidecar = SyncPath(f"{db_path}{WAL_SUFFIX}")
        assert sidecar.exists(), "expected a .wal beside the open database"
    finally:
        con.close()

    # Closing checkpoints the sidecar away, which is why a copy taken while the
    # server is stopped is fine and one taken while it runs is not.
    assert not SyncPath(f"{db_path}{WAL_SUFFIX}").exists()


def _count(con: duckdb.DuckDBPyConnection) -> int:
    row = con.execute("SELECT COUNT(*) FROM words").fetchone()
    return int(row[0]) if row else 0


def _copy_like_syncthing(db_path: SyncPath, destination: SyncPath) -> None:
    """Copy only the .db, which is what a file-level sync of the vault sees."""
    shutil.copy2(db_path, destination)


@pytest.mark.parametrize("copies", [8])
def test_copying_a_live_database_loses_data(tmp_path: SyncPath, copies: int) -> None:
    """A .db copied mid-write is stale or unreadable, never a faithful snapshot.

    This is the measured version of "do not sync a live database". It asserts
    the weaker, more useful claim: not that every copy is corrupt, but that a
    copy is not guaranteed to carry the rows that were committed before it.
    """
    db_path = tmp_path / "index.db"
    con = duckdb.connect(str(db_path))
    con.execute("CREATE TABLE words (path TEXT, word TEXT)")

    snapshots: list[tuple[SyncPath, int]] = []
    stop = threading.Event()

    def write_forever() -> None:
        row = 0
        while not stop.is_set():
            con.execute("INSERT INTO words VALUES (?, ?)", (f"note-{row}.dj", f"word{row}"))
            row += 1

    writer = threading.Thread(target=write_forever)
    writer.start()
    try:
        for index in range(copies):
            committed = _count(con)
            destination = tmp_path / f"copy-{index}.db"
            _copy_like_syncthing(db_path, destination)
            snapshots.append((destination, committed))
    finally:
        stop.set()
        writer.join()
        con.close()

    unreadable = 0
    stale = 0
    for destination, committed_at_copy_time in snapshots:
        try:
            replica = duckdb.connect(str(destination), read_only=True)
        except duckdb.Error:
            unreadable += 1
            continue
        try:
            rows = _count(replica)
        except duckdb.Error:
            unreadable += 1
            continue
        finally:
            replica.close()
        if rows < committed_at_copy_time:
            stale += 1

    # Every copy either failed to open or came back missing committed rows.
    # A sync that propagates these is propagating a damaged index.
    assert unreadable + stale == len(snapshots), (
        f"{unreadable} unreadable, {stale} stale, out of {len(snapshots)} copies; "
        "if this now passes cleanly, revisit ADR 0010"
    )


def test_content_addressed_cache_entries_survive_a_concurrent_writer(tmp_path: SyncPath) -> None:
    """The property that makes an embedding cache safe to sync, unlike the index.

    Two writers producing the same entry write identical bytes to the same path,
    so a sync conflict between them carries no information loss.
    """
    cache = tmp_path / "embeddings"
    cache.mkdir()
    payload = b"\x00\x01\x02\x03"
    digest = "abc123"

    def write_entry(replica: str) -> SyncPath:
        # Each "machine" writes into its own tree, as it would before syncing.
        machine = cache / replica / digest[:2]
        machine.mkdir(parents=True)
        entry = machine / f"{digest}.f32"
        entry.write_bytes(payload)
        return entry

    first = write_entry("machine-a")
    second = write_entry("machine-b")

    assert first.read_bytes() == second.read_bytes()
    assert first.relative_to(cache / "machine-a") == second.relative_to(cache / "machine-b")


def test_default_index_location_is_outside_the_vault(tmp_path: SyncPath) -> None:
    """The fix itself: a fresh install does not put the index in the vault."""
    vault = tmp_path / "vault"
    vault.mkdir()
    env = {"YAK_SHEARS_DIR": str(vault), "XDG_STATE_HOME": str(tmp_path / "state")}
    with patch.dict("os.environ", env, clear=True):
        assert not index_is_inside_vault()
        assert vault not in get_search_db_path().parents


def test_index_rebuilds_from_the_vault_after_being_deleted(tmp_path: SyncPath) -> None:
    """Nothing is lost by refusing to sync it, because it is fully derivable."""
    db_dir = tmp_path / "state"
    db_dir.mkdir()
    with patch.dict("os.environ", {"SEARCH_DB_DIR": str(db_dir)}, clear=True):
        init_search_db()
        insert_words([("note.dj", 1, "reindexable")])
        assert search_words("reindexable")

        close_search_db()
        get_search_db_path().unlink()

        init_search_db()
        assert search_words("reindexable") == []
        insert_words([("note.dj", 1, "reindexable")])
        assert search_words("reindexable")
        close_search_db()
