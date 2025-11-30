"""Database operations for Yak search indexing.

Centralizes all DuckDB operations for the search index, including:
- Database initialization and schema management
- File metadata tracking (paths, modification times)
- Word indexing for full-text search
- Frontmatter and link storage for metadata queries
"""

import json
import os
import time
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path as SyncPath

import duckdb

from yak_shears._log_utils import log

MAX_WORD_LENGTH = 1000
INDEX_UPDATE_INTERVAL_SECONDS = 60


def get_search_db_path() -> SyncPath:
    """Get the path to the search database."""
    search_db_dir = os.getenv("SEARCH_DB_DIR")
    if search_db_dir:
        return SyncPath(search_db_dir) / "yak_shears_search.db"
    yak_dir = SyncPath(os.getenv("YAK_SHEARS_DIR", "~/Sync/yak-shears")).expanduser()
    return yak_dir / "yak_shears_search.db"


@contextmanager
def get_search_db() -> Generator[duckdb.DuckDBPyConnection, None, None]:
    """Get connection to search database."""
    con = duckdb.connect(str(get_search_db_path()))
    try:
        yield con
    finally:
        con.close()


def init_search_db() -> None:
    """Initialize search database schema."""
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
                mtime REAL
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


def upsert_file(path: str, mtime: float) -> None:
    """Insert or update a file's modification time."""
    with get_search_db() as con:
        con.execute("INSERT OR REPLACE INTO files (path, mtime) VALUES (?, ?)", (path, mtime))


# -----------------------------------------------------------------------------
# Word indexing operations


def delete_words_for_paths(paths: list[str]) -> None:
    """Delete words for the given file paths."""
    if not paths:
        return
    with get_search_db() as con:
        placeholders = ",".join("?" for _ in paths)
        con.execute(f"DELETE FROM words WHERE path IN ({placeholders})", paths)  # noqa: S608


def insert_words(words_data: list[tuple[str, int, str]]) -> None:
    """Insert word data into the database."""
    if not words_data:
        return
    with get_search_db() as con:
        con.executemany("INSERT INTO words (path, line_num, word) VALUES (?, ?, ?)", words_data)


def search_words(query: str) -> list[tuple[str, int, str]]:
    """Search for words using Levenshtein distance.

    Args:
        query: The search query

    Returns:
        List of (path, line_num, word) tuples ordered by relevance.
    """
    with get_search_db() as con:
        threshold = max(1, len(query) // 4)
        sql = """
            SELECT path, line_num, word
            FROM words
            WHERE levenshtein(word, lower(?)) <= ?
            ORDER BY levenshtein(word, lower(?))
            LIMIT 1000
        """
        return con.execute(sql, (query, threshold, query)).fetchall()


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
        return True
    except Exception:
        return False


# -----------------------------------------------------------------------------
# Frontmatter operations


def upsert_frontmatter(rel_path: str, frontmatter: dict[str, object]) -> None:
    """Insert or update frontmatter for a yak file."""
    with get_search_db() as con:
        if frontmatter:
            con.execute(
                "INSERT OR REPLACE INTO yak_frontmatter (path, frontmatter_json, updated_at) VALUES (?, ?, ?)",
                (rel_path, json.dumps(frontmatter), datetime.now(UTC)),
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
                "INSERT INTO yak_links (source_path, target_path, link_type) VALUES (?, ?, ?)",
                links_data,
            )


def get_backlinks(yak_path: str) -> list[tuple[str, str]]:
    """Get backlinks for a yak file.

    Returns:
        List of (source_path, link_type) tuples
    """
    try:
        with get_search_db() as con:
            result = con.execute(
                "SELECT source_path, link_type FROM yak_links WHERE target_path = ? OR target_path = ?",
                (yak_path, yak_path.replace(".dj", "")),
            ).fetchall()
        return result
    except Exception:
        return []


# -----------------------------------------------------------------------------
# Batch operations for index updates


def update_index_batch(
    deleted_paths: list[str],
    changed_paths: list[str],
    words_data: list[tuple[str, int, str]],
    file_mtimes: dict[str, float],
) -> None:
    """Perform a batch update of the search index within a transaction.

    Args:
        deleted_paths: Paths to remove from the index
        changed_paths: Paths whose words need to be re-indexed
        words_data: New word data to insert
        file_mtimes: Updated file modification times
    """
    with get_search_db() as con:
        con.execute("BEGIN")
        try:
            if deleted_paths:
                placeholders = ",".join("?" for _ in deleted_paths)
                con.execute(f"DELETE FROM files WHERE path IN ({placeholders})", deleted_paths)  # noqa: S608
                con.execute(f"DELETE FROM words WHERE path IN ({placeholders})", deleted_paths)  # noqa: S608

            if changed_paths:
                placeholders = ",".join("?" for _ in changed_paths)
                con.execute(f"DELETE FROM words WHERE path IN ({placeholders})", changed_paths)  # noqa: S608

            if words_data:
                con.executemany("INSERT INTO words (path, line_num, word) VALUES (?, ?, ?)", words_data)

            for path, mtime in file_mtimes.items():
                con.execute("INSERT OR REPLACE INTO files (path, mtime) VALUES (?, ?)", (path, mtime))

            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise

    set_last_update_time(time.time())


# -----------------------------------------------------------------------------
# Index maintenance


def _process_file_words(dj_file: SyncPath, rel_path: str) -> list[tuple[str, int, str]]:
    """Process a single file and return list of (path, line_num, word) tuples."""
    words_data: list[tuple[str, int, str]] = []
    try:
        content = dj_file.read_text(encoding="utf-8")
        lines = content.splitlines()
        for line_num, line in enumerate(lines, 1):
            raw_words = set(line.split())
            unique_words = set()
            for raw_word in raw_words:
                word = raw_word.lower().strip(".,!?;:\"'")
                if len(word) > MAX_WORD_LENGTH:
                    word = word[:MAX_WORD_LENGTH]
                if word:
                    unique_words.add(word)
            words_data.extend((rel_path, line_num, word) for word in unique_words)
    except Exception as exc:
        log(f"WARNING: Skipping unreadable file {dj_file}: {exc}")
    return words_data


def update_search_index(yak_dir: SyncPath) -> None:
    """Update the search index with current files."""
    current_files = {}
    stored_files = get_stored_files()

    for dj_file in yak_dir.rglob("*.dj"):
        if dj_file.is_file():
            rel_path = dj_file.relative_to(yak_dir).as_posix()
            mtime = dj_file.stat().st_mtime
            current_files[rel_path] = mtime

    stored_paths = set(stored_files.keys())
    current_paths = set(current_files.keys())
    deleted_paths = list(stored_paths - current_paths)

    changed_paths = [
        path for path, mtime in current_files.items() if stored_files.get(path) != mtime
    ]

    words_data = []
    for path in changed_paths:
        dj_file = yak_dir / path
        words_data.extend(_process_file_words(dj_file, path))

    update_index_batch(deleted_paths, changed_paths, words_data, current_files)


def should_update_index(yak_dir: SyncPath) -> bool:
    """Check if search index should be updated."""
    now = time.time()
    last_update = get_last_update_time()

    if now - last_update < INDEX_UPDATE_INTERVAL_SECONDS:
        return False

    stored_files = get_stored_files()
    for dj_file in yak_dir.rglob("*.dj"):
        if dj_file.is_file():
            rel_path = dj_file.relative_to(yak_dir).as_posix()
            current_mtime = dj_file.stat().st_mtime
            stored_mtime = stored_files.get(rel_path)
            if stored_mtime != current_mtime:
                return True

    current_paths = {dj_file.relative_to(yak_dir).as_posix() for dj_file in yak_dir.rglob("*.dj") if dj_file.is_file()}
    stored_paths = set(stored_files.keys())
    return current_paths != stored_paths
