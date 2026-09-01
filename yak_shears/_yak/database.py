"""Database operations for Yak search indexing.

Centralizes all DuckDB operations for the search index, including:
- Database initialization and schema management
- File metadata tracking (paths, modification times)
- Word indexing for full-text search
- Frontmatter and link storage for metadata queries
"""

import csv
import json
import os
import tempfile
import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path as SyncPath

import duckdb

from yak_shears._log_utils import log
from yak_shears.frontmatter import parse_frontmatter
from yak_shears.links import extract_all_links

MAX_WORD_LENGTH = 1000
INDEX_UPDATE_INTERVAL_SECONDS = 60
SEARCH_RESULT_LIMIT = 1000
CHEAP_SEARCH_TARGET_ROWS = 20
BULK_INSERT_THRESHOLD = 500


@dataclass
class _ConnectionCache:
    """The single DuckDB connection shared by this process."""

    connection: duckdb.DuckDBPyConnection | None = None
    path: str | None = None


_CACHE = _ConnectionCache()
_DB_LOCK = threading.RLock()


SEARCH_DB_FILENAME = "yak_shears_search.db"


def default_search_db_dir() -> SyncPath:
    """Local state directory for the search index, honouring `XDG_STATE_HOME`."""
    state_home = os.getenv("XDG_STATE_HOME")
    base = SyncPath(state_home).expanduser() if state_home else SyncPath("~/.local/state").expanduser()
    return base / "yak-shears"


def get_search_db_path() -> SyncPath:
    """Get the path to the search database.

    Defaults to a machine-local state directory rather than the notes vault.
    The index is a rebuildable derivative, and DuckDB keeps a `.wal` sidecar
    while open, so a file-level sync landing mid-write copies a torn database
    and two machines writing produce conflicting copies of it (see ADR 0010).
    """
    search_db_dir = os.getenv("SEARCH_DB_DIR")
    base = SyncPath(search_db_dir).expanduser() if search_db_dir else default_search_db_dir()
    return base / SEARCH_DB_FILENAME


def index_is_inside_vault() -> bool:
    """Whether the resolved index sits inside the notes vault (a sync hazard)."""
    yak_dir = SyncPath(os.getenv("YAK_SHEARS_DIR", "~/Sync/yak-shears")).expanduser()
    db_path = get_search_db_path()
    try:
        return yak_dir.resolve() in db_path.resolve().parents
    except OSError:
        return False


def stray_vault_index() -> SyncPath | None:
    """An index file left behind inside the vault by an older default, if any."""
    yak_dir = SyncPath(os.getenv("YAK_SHEARS_DIR", "~/Sync/yak-shears")).expanduser()
    stray = yak_dir / SEARCH_DB_FILENAME
    return stray if stray.exists() and stray.resolve() != get_search_db_path().resolve() else None


def close_search_db() -> None:
    """Close the process-wide search connection, if any.

    Callers must invoke this before deleting or replacing the database file.
    """
    with _DB_LOCK:
        if _CACHE.connection is not None:
            _CACHE.connection.close()
        _CACHE.connection = None
        _CACHE.path = None


@contextmanager
def get_search_db() -> Generator[duckdb.DuckDBPyConnection, None, None]:
    """Yield the process-wide search connection, holding the connection lock.

    DuckDB connections are not thread-safe and opening one is expensive, so a
    single connection is cached per resolved database path and serialized by a
    re-entrant lock. Do not retain the connection past the `with` block.
    """
    with _DB_LOCK:
        resolved = get_search_db_path()
        db_path = str(resolved)
        if _CACHE.connection is None or _CACHE.path != db_path or not resolved.exists():
            close_search_db()
            # The state directory is ours to create; the vault always existed.
            resolved.parent.mkdir(parents=True, exist_ok=True)
            _CACHE.connection = duckdb.connect(db_path)
            _CACHE.path = db_path
        yield _CACHE.connection


def _migrate_schema(con: duckdb.DuckDBPyConnection) -> None:
    columns = dict(
        con.execute(
            "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'files'"
        ).fetchall()
    )
    if "title" not in columns:
        con.execute("ALTER TABLE files ADD COLUMN title TEXT")
    if columns.get("mtime") == "FLOAT":
        con.execute("ALTER TABLE files ALTER mtime TYPE DOUBLE")


def init_search_db() -> None:
    """Initialize search database schema, migrating an existing database in place."""
    with get_search_db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS files (
                path TEXT PRIMARY KEY,
                mtime DOUBLE,
                title TEXT
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS words (
                path TEXT,
                line_num INTEGER,
                word TEXT,
                PRIMARY KEY (path, line_num, word)
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS yak_frontmatter (
                path TEXT PRIMARY KEY,
                frontmatter_json TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS yak_links (
                source_path TEXT,
                target_path TEXT,
                link_type TEXT DEFAULT 'wikilink',
                PRIMARY KEY (source_path, target_path, link_type)
            )
        """)
        con.execute("""
            CREATE INDEX IF NOT EXISTS idx_links_target
            ON yak_links(target_path)
        """)
        con.execute("""
            CREATE INDEX IF NOT EXISTS idx_links_source
            ON yak_links(source_path)
        """)
        con.execute("""
            CREATE INDEX IF NOT EXISTS idx_words_word
            ON words(word)
        """)
        _migrate_schema(con)


# -----------------------------------------------------------------------------
# Metadata operations


def get_last_update_time() -> float:
    """Get the last update timestamp."""
    with get_search_db() as con:
        result = con.execute("SELECT value FROM metadata WHERE key = 'last_update'").fetchone()
    return float(result[0]) if result else 0.0


def set_last_update_time(timestamp: float) -> None:
    """Set the last update timestamp."""
    with get_search_db() as con:
        con.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES ('last_update', ?)", (str(timestamp),))


# -----------------------------------------------------------------------------
# File tracking operations


def get_stored_files() -> dict[str, float]:
    """Get dict of path -> mtime from database."""
    with get_search_db() as con:
        result = con.execute("SELECT path, mtime FROM files").fetchall()
    return {row[0]: row[1] for row in result}


def delete_files(paths: list[str]) -> None:
    """Delete files and their associated words from the database."""
    if not paths:
        return
    with get_search_db() as con:
        placeholders = ",".join("?" for _ in paths)
        con.execute(f"DELETE FROM files WHERE path IN ({placeholders})", paths)  # noqa: S608
        con.execute(f"DELETE FROM words WHERE path IN ({placeholders})", paths)  # noqa: S608
        con.execute(f"DELETE FROM yak_frontmatter WHERE path IN ({placeholders})", paths)  # noqa: S608
        con.execute(f"DELETE FROM yak_links WHERE source_path IN ({placeholders})", paths)  # noqa: S608


def upsert_file(path: str, mtime: float, title: str | None = None) -> None:
    """Insert or update a file's modification time, keeping any stored title."""
    with get_search_db() as con:
        _upsert_file_row(con, path, mtime, title)


def get_file_titles(paths: list[str]) -> dict[str, str]:
    """Get the indexed title for each of the given paths, skipping any not yet indexed."""
    if not paths:
        return {}
    placeholders = ",".join("?" for _ in paths)
    try:
        with get_search_db() as con:
            rows = con.execute(
                f"SELECT path, title FROM files WHERE path IN ({placeholders})",  # noqa: S608
                paths,
            ).fetchall()
    except Exception:
        return {}
    return {row[0]: row[1] for row in rows if row[1]}


def _upsert_file_row(con: duckdb.DuckDBPyConnection, path: str, mtime: float, title: str | None) -> None:
    con.execute(
        """
        INSERT INTO files (path, mtime, title) VALUES (?, ?, ?)
        ON CONFLICT (path) DO UPDATE
        SET mtime = excluded.mtime, title = COALESCE(excluded.title, files.title)
        """,
        (path, mtime, title),
    )


# -----------------------------------------------------------------------------
# Word indexing operations


def delete_words_for_paths(paths: list[str]) -> None:
    """Delete words for the given file paths."""
    if not paths:
        return
    with get_search_db() as con:
        placeholders = ",".join("?" for _ in paths)
        con.execute(f"DELETE FROM words WHERE path IN ({placeholders})", paths)  # noqa: S608


def _insert_words(con: duckdb.DuckDBPyConnection, words_data: list[tuple[str, int, str]]) -> None:
    """Insert word rows, staging large batches through a CSV file.

    DuckDB spends ~300 microseconds per parameterized single-row INSERT, so a
    full vault re-index costs minutes; loading the same rows with `read_csv`
    takes milliseconds.
    """
    if not words_data:
        return
    if len(words_data) < BULK_INSERT_THRESHOLD:
        con.executemany("INSERT INTO words (path, line_num, word) VALUES (?, ?, ?)", words_data)
        return

    with tempfile.TemporaryDirectory() as tmp_dir:
        csv_path = SyncPath(tmp_dir) / "words.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            csv.writer(handle).writerows(words_data)
        con.execute(
            """
            INSERT INTO words (path, line_num, word)
            SELECT * FROM read_csv(
                ?,
                header = false,
                columns = {'path': 'TEXT', 'line_num': 'INTEGER', 'word': 'TEXT'}
            )
            """,
            (str(csv_path),),
        )


def insert_words(words_data: list[tuple[str, int, str]]) -> None:
    """Insert word data into the database."""
    if not words_data:
        return
    with get_search_db() as con:
        _insert_words(con, words_data)


def _escape_like(word: str) -> str:
    for char in ("\\", "%", "_"):
        word = word.replace(char, f"\\{char}")
    return word


def _prefix_matches(con: duckdb.DuckDBPyConnection, word: str) -> list[tuple[int, str, int, str]]:
    sql = """
        SELECT distance, path, line_num, word
        FROM (
            SELECT path, line_num, word, levenshtein(word, ?) AS distance
            FROM words
            WHERE word LIKE ? || '%' ESCAPE '\\'
        )
        ORDER BY distance, path, line_num
        LIMIT ?
    """
    return con.execute(sql, (word, _escape_like(word), SEARCH_RESULT_LIMIT)).fetchall()


def _fuzzy_matches(con: duckdb.DuckDBPyConnection, word: str, limit: int) -> list[tuple[int, str, int, str]]:
    threshold = max(1, len(word) // 4)
    sql = """
        SELECT distance, path, line_num, word
        FROM (
            SELECT path, line_num, word, levenshtein(word, ?) AS distance
            FROM words
        )
        WHERE distance <= ?
        ORDER BY distance, path, line_num
        LIMIT ?
    """
    return con.execute(sql, (word, threshold, limit)).fetchall()


@dataclass(frozen=True)
class WordMatch:
    """One indexed word hit; the text backend's only outward shape."""

    path: str
    line_num: int
    word: str


def search_words(query: str) -> list[WordMatch]:
    """Search for words, preferring exact and prefix matches over fuzzy matching.

    The Levenshtein scan reads every indexed word, so it only runs when prefix
    matching returns too few rows to fill a result page. Both tiers score by the
    same edit distance and break ties on (path, line_num), so the combined
    ranking is a total order that does not depend on storage order.

    Args:
        query: The search query

    Returns:
        Matches ordered by relevance.
    """
    word = query.lower()
    with get_search_db() as con:
        scored = _prefix_matches(con, word)
        if len(scored) < CHEAP_SEARCH_TARGET_ROWS:
            seen = set(scored)
            remaining = SEARCH_RESULT_LIMIT - len(scored)
            scored.extend(row for row in _fuzzy_matches(con, word, remaining) if row not in seen)

    scored.sort()
    return [WordMatch(path, line_num, matched) for _, path, line_num, matched in scored[:SEARCH_RESULT_LIMIT]]


def get_word_count() -> int:
    """Get the total number of indexed words."""
    with get_search_db() as con:
        result = con.execute("SELECT COUNT(*) FROM words").fetchone()
    return result[0] if result else 0


def check_tables_exist() -> bool:
    """Check if the required tables exist and are accessible."""
    try:
        with get_search_db() as con:
            con.execute("SELECT 1 FROM metadata LIMIT 1")
            con.execute("SELECT 1 FROM words LIMIT 1")
    except Exception:
        return False
    else:
        return True


# -----------------------------------------------------------------------------
# Frontmatter operations


def _frontmatter_json(frontmatter: dict[str, object]) -> str:
    """Serialize frontmatter, rendering the dates YAML parsed back as ISO text.

    Returns:
        A JSON string; values JSON cannot hold fall back to their `str`.
    """
    return json.dumps(
        frontmatter, default=lambda value: value.isoformat() if hasattr(value, "isoformat") else str(value)
    )


def upsert_frontmatter(rel_path: str, frontmatter: dict[str, object]) -> None:
    """Insert or update frontmatter for a yak file."""
    with get_search_db() as con:
        if frontmatter:
            con.execute(
                "INSERT OR REPLACE INTO yak_frontmatter (path, frontmatter_json, updated_at) VALUES (?, ?, ?)",
                (rel_path, _frontmatter_json(frontmatter), datetime.now(UTC)),
            )
        else:
            con.execute("DELETE FROM yak_frontmatter WHERE path = ?", (rel_path,))


def get_frontmatter(yak_path: str) -> dict[str, object]:
    """Get frontmatter for a yak file."""
    try:
        with get_search_db() as con:
            result = con.execute(
                "SELECT frontmatter_json FROM yak_frontmatter WHERE path = ?",
                (yak_path,),
            ).fetchone()
        if result:
            return json.loads(result[0])
    except Exception:
        pass
    return {}


# -----------------------------------------------------------------------------
# Link operations


def replace_links(source_path: str, links: list[tuple[str, str]]) -> None:
    """Replace all links for a source file.

    Args:
        source_path: The relative path of the source file
        links: List of (target_path, link_type) tuples
    """
    with get_search_db() as con:
        con.execute("DELETE FROM yak_links WHERE source_path = ?", (source_path,))
        if links:
            links_data = [(source_path, target, link_type) for target, link_type in links]
            con.executemany(
                "INSERT OR IGNORE INTO yak_links (source_path, target_path, link_type) VALUES (?, ?, ?)",
                links_data,
            )


@dataclass(frozen=True)
class LinkCandidate:
    """A note offered as the target of a wikilink."""

    path: str
    target: str
    title: str
    inbound: int


def search_link_candidates(prefix: str, limit: int = 8, exclude: str | None = None) -> list[LinkCandidate]:
    """Rank notes as wikilink targets: prefix matches first, then substring, each by inbound links then recency."""
    needle = prefix.strip().lower()
    like = f"%{needle}%"
    try:
        with get_search_db() as con:
            rows = con.execute(
                r"""
                WITH inbound AS (
                    SELECT target_path, COUNT(*) AS n FROM yak_links GROUP BY target_path
                )
                SELECT f.path,
                       COALESCE(f.title, f.path) AS title,
                       COALESCE(i.n, 0) AS inbound,
                       CASE
                           WHEN ? = '' THEN 1
                           WHEN LOWER(regexp_extract(f.path, '([^/]+)\.dj$', 1)) LIKE ? THEN 0
                           WHEN LOWER(COALESCE(f.title, '')) LIKE ? THEN 0
                           ELSE 1
                       END AS rank
                FROM files f
                LEFT JOIN inbound i ON i.target_path = f.path
                WHERE f.path <> COALESCE(?, '')
                  AND (? = '' OR LOWER(f.path) LIKE ? OR LOWER(COALESCE(f.title, '')) LIKE ?)
                ORDER BY rank, CASE WHEN ? = '' THEN 0 ELSE inbound END DESC, f.mtime DESC
                LIMIT ?
                """,
                (needle, f"{needle}%", f"{needle}%", exclude, needle, like, like, needle, limit),
            ).fetchall()
    except Exception as exc:
        log(f"ERROR: Link candidate query failed: {exc}")
        return []
    return [
        LinkCandidate(path=path, target=SyncPath(path).stem, title=title, inbound=inbound)
        for path, title, inbound, _rank in rows
    ]


def all_links() -> list[tuple[str, str, str]]:
    """Every indexed edge as (source path, target, link type)."""
    try:
        with get_search_db() as con:
            return con.execute("SELECT source_path, target_path, link_type FROM yak_links").fetchall()
    except Exception as exc:
        log(f"ERROR: Link scan failed: {exc}")
        return []


def all_titles() -> dict[str, str]:
    """Indexed title per path, falling back to the path itself."""
    try:
        with get_search_db() as con:
            rows = con.execute("SELECT path, COALESCE(title, path) FROM files").fetchall()
    except Exception as exc:
        log(f"ERROR: Title scan failed: {exc}")
        return {}
    return dict(rows)


def get_backlinks(yak_path: str) -> list[tuple[str, str]]:
    """Get backlinks for a yak file.

    Returns:
        List of (source_path, link_type) tuples
    """
    try:
        with get_search_db() as con:
            return con.execute(
                "SELECT source_path, link_type FROM yak_links WHERE target_path = ? OR target_path = ?",
                (yak_path, yak_path.replace(".dj", "")),
            ).fetchall()
    except Exception:
        return []


# -----------------------------------------------------------------------------
# Batch operations for index updates


def update_index_batch(
    deleted_paths: list[str],
    changed_paths: list[str],
    words_data: list[tuple[str, int, str]],
    file_mtimes: dict[str, float],
    file_titles: dict[str, str] | None = None,
    file_links: dict[str, list[tuple[str, str]]] | None = None,
    file_frontmatter: dict[str, dict[str, object]] | None = None,
) -> None:
    """Perform a batch update of the search index within a transaction.

    Args:
        deleted_paths: Paths to remove from the index
        changed_paths: Paths whose words need to be re-indexed
        words_data: New word data to insert
        file_mtimes: Updated file modification times
        file_titles: Derived titles for re-indexed paths; missing entries keep the stored title
        file_links: Outbound links for re-indexed paths, replacing whatever was stored
        file_frontmatter: Parsed frontmatter for re-indexed paths, replacing whatever was stored
    """
    titles = file_titles or {}
    links = file_links or {}
    frontmatter = file_frontmatter or {}
    with get_search_db() as con:
        con.execute("BEGIN")
        try:
            if deleted_paths:
                placeholders = ",".join("?" for _ in deleted_paths)
                con.execute(f"DELETE FROM files WHERE path IN ({placeholders})", deleted_paths)  # noqa: S608
                con.execute(f"DELETE FROM words WHERE path IN ({placeholders})", deleted_paths)  # noqa: S608
                con.execute(f"DELETE FROM yak_frontmatter WHERE path IN ({placeholders})", deleted_paths)  # noqa: S608
                con.execute(f"DELETE FROM yak_links WHERE source_path IN ({placeholders})", deleted_paths)  # noqa: S608

            if changed_paths:
                placeholders = ",".join("?" for _ in changed_paths)
                con.execute(f"DELETE FROM words WHERE path IN ({placeholders})", changed_paths)  # noqa: S608
                con.execute(
                    f"DELETE FROM yak_links WHERE source_path IN ({placeholders})",  # noqa: S608
                    changed_paths,
                )
                con.execute(
                    f"DELETE FROM yak_frontmatter WHERE path IN ({placeholders})",  # noqa: S608
                    changed_paths,
                )

            _insert_words(con, words_data)
            link_rows = [(path, target, link_type) for path, edges in links.items() for target, link_type in edges]
            if link_rows:
                con.executemany(
                    "INSERT OR IGNORE INTO yak_links (source_path, target_path, link_type) VALUES (?, ?, ?)",
                    link_rows,
                )

            frontmatter_rows = [
                (path, _frontmatter_json(meta), datetime.now(UTC)) for path, meta in frontmatter.items() if meta
            ]
            if frontmatter_rows:
                con.executemany(
                    "INSERT OR REPLACE INTO yak_frontmatter (path, frontmatter_json, updated_at) VALUES (?, ?, ?)",
                    frontmatter_rows,
                )

            for path, mtime in file_mtimes.items():
                _upsert_file_row(con, path, mtime, titles.get(path))

            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise

    set_last_update_time(time.time())


# -----------------------------------------------------------------------------
# Index maintenance


def derive_title(content: str, rel_path: str) -> str:
    """Derive a human-readable title from frontmatter, a heading, or the filename."""
    frontmatter, body = parse_frontmatter(content)
    title = frontmatter.get("title") or frontmatter.get("name")
    if isinstance(title, str) and title.strip():
        return title.strip()
    for line in body.splitlines():
        if stripped := line.strip():
            return stripped.lstrip("#").strip() or stripped
    return SyncPath(rel_path).name


@dataclass(frozen=True)
class FileIndex:
    """Indexable content extracted from a single yak file."""

    words: list[tuple[str, int, str]]
    title: str
    links: list[tuple[str, str]]
    frontmatter: dict[str, object]


@dataclass(frozen=True)
class VaultScan:
    """Result of a single walk over the vault."""

    file_mtimes: dict[str, float]
    changed_paths: list[str]
    deleted_paths: list[str]

    @property
    def has_changes(self) -> bool:
        """Whether the vault differs from what is indexed."""
        return bool(self.changed_paths or self.deleted_paths)


def _extract_line_words(line: str) -> set[str]:
    words = set()
    for raw_word in set(line.split()):
        word = raw_word.lower().strip(".,!?;:\"'")
        if word:
            words.add(word[:MAX_WORD_LENGTH])
    return words


def _process_file(dj_file: SyncPath, rel_path: str) -> FileIndex:
    """Read a file once and return its words and derived title."""
    try:
        content = dj_file.read_text(encoding="utf-8")
    except Exception as exc:
        log(f"WARNING: Skipping unreadable file {dj_file}: {exc}")
        return FileIndex(words=[], title=SyncPath(rel_path).name, links=[], frontmatter={})

    words_data = [
        (rel_path, line_num, word)
        for line_num, line in enumerate(content.splitlines(), 1)
        for word in _extract_line_words(line)
    ]
    frontmatter, body = parse_frontmatter(content)
    return FileIndex(
        words=words_data,
        title=derive_title(content, rel_path),
        links=extract_all_links(body),
        frontmatter=frontmatter,
    )


def scan_vault(yak_dir: SyncPath) -> VaultScan:
    """Walk the vault once and compare it against the indexed files."""
    stored_files = get_stored_files()
    file_mtimes = {
        dj_file.relative_to(yak_dir).as_posix(): dj_file.stat().st_mtime
        for dj_file in yak_dir.rglob("*.dj")
        if dj_file.is_file()
    }
    return VaultScan(
        file_mtimes=file_mtimes,
        changed_paths=[path for path, mtime in file_mtimes.items() if stored_files.get(path) != mtime],
        deleted_paths=sorted(set(stored_files) - set(file_mtimes)),
    )


def apply_vault_scan(yak_dir: SyncPath, scan: VaultScan) -> None:
    """Write the results of a vault scan into the search index."""
    words_data: list[tuple[str, int, str]] = []
    file_titles: dict[str, str] = {}
    file_links: dict[str, list[tuple[str, str]]] = {}
    file_frontmatter: dict[str, dict[str, object]] = {}
    for path in scan.changed_paths:
        file_index = _process_file(yak_dir / path, path)
        words_data.extend(file_index.words)
        file_titles[path] = file_index.title
        file_links[path] = file_index.links
        file_frontmatter[path] = file_index.frontmatter

    update_index_batch(
        scan.deleted_paths,
        scan.changed_paths,
        words_data,
        scan.file_mtimes,
        file_titles,
        file_links,
        file_frontmatter,
    )


def update_search_index(yak_dir: SyncPath) -> None:
    """Update the search index with current files."""
    apply_vault_scan(yak_dir, scan_vault(yak_dir))


def refresh_search_index(yak_dir: SyncPath, *, force: bool = False) -> bool:
    """Update the index if the guard interval has elapsed and the vault changed.

    Returns:
        Whether the index was rewritten.
    """
    if not force and time.time() - get_last_update_time() < INDEX_UPDATE_INTERVAL_SECONDS:
        return False

    started = time.perf_counter()
    scan = scan_vault(yak_dir)
    if not force and not scan.has_changes:
        return False

    apply_vault_scan(yak_dir, scan)

    # Log why a rebuild ran, not just that it did. A search that happens to
    # trigger one is otherwise indistinguishable from a slow search, which is
    # what hid the float32 mtime bug that re-indexed the vault on every query.
    log(
        f"INDEX reason={'forced' if force else 'changed'} "
        f"scanned={len(scan.file_mtimes)} changed={len(scan.changed_paths)} "
        f"deleted={len(scan.deleted_paths)} elapsed_ms={(time.perf_counter() - started) * 1000:.1f}"
    )
    return True


def should_update_index(yak_dir: SyncPath) -> bool:
    """Check if search index should be updated."""
    if time.time() - get_last_update_time() < INDEX_UPDATE_INTERVAL_SECONDS:
        return False
    return scan_vault(yak_dir).has_changes
