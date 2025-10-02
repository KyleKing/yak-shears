"""Handlers for Yak Shears."""

import os
import re
import time
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from operator import itemgetter
from pathlib import Path as SyncPath
from typing import Self
from urllib.parse import quote

import duckdb  # type: ignore[import-untyped]
from anyio import Path
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from yak_shears._log_utils import log
from yak_shears._templates import (
    SearchResult,
    SortBy,
    YakInfo,
    _render_template,
    render_error,
    render_search,
    render_yak_edit,
    render_yak_new,
    render_yaks,
)

MAX_WORD_LENGTH = 1000
INDEX_UPDATE_INTERVAL_SECONDS = 60


# Search database functions
def get_search_db_path() -> SyncPath:
    """Get the path to the search database.

    Returns:
        The path to the search database file.
    """
    yak_dir = SyncPath(os.getenv("YAK_SHEARS_DIR", "~/Sync/yak-shears")).expanduser()
    return yak_dir / "yak_shears_search.db"


@contextmanager
def get_search_db() -> Generator[duckdb.DuckDBPyConnection, None, None]:
    """Get connection to search database.

    Yields:
        A DuckDB connection to the search database.
    """
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


def get_last_update_time() -> float:
    """Get the last update timestamp.

    Returns:
        The last update timestamp as a float.
    """
    with get_search_db() as con:
        result = con.execute("SELECT value FROM metadata WHERE key = 'last_update'").fetchone()
    return float(result[0]) if result else 0


def set_last_update_time(timestamp: float) -> None:
    """Set the last update timestamp."""
    with get_search_db() as con:
        con.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES ('last_update', ?)", (str(timestamp),))


def get_stored_files() -> dict[str, float]:
    """Get dict of path -> mtime from database.

    Returns:
        Dictionary mapping file paths to modification times.
    """
    with get_search_db() as con:
        result = con.execute("SELECT path, mtime FROM files").fetchall()
    return {row[0]: row[1] for row in result}


def _process_file_words(dj_file: SyncPath, rel_path: str) -> list[tuple[str, int, str]]:
    """Process a single file and return list of (path, line_num, word) tuples.

    Returns:
        List of tuples (path, line_num, word) for each word in the file.
    """
    words_data: list[tuple[str, int, str]] = []
    try:
        content = dj_file.read_text(encoding="utf-8")
        lines = content.splitlines()
        for line_num, line in enumerate(lines, 1):
            raw_words = set(line.split())  # Use set to deduplicate
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

    # Scan all .dj files
    for dj_file in yak_dir.rglob("*.dj"):
        if dj_file.is_file():
            rel_path = dj_file.relative_to(yak_dir).as_posix()
            mtime = dj_file.stat().st_mtime
            current_files[rel_path] = mtime

    with get_search_db() as con:
        con.execute("BEGIN")

        # Remove deleted files
        stored_paths = set(stored_files.keys())
        current_paths = set(current_files.keys())
        deleted_paths = stored_paths - current_paths
        if deleted_paths:
            placeholders = ",".join("?" for _ in deleted_paths)
            con.execute(f"DELETE FROM files WHERE path IN ({placeholders})", list(deleted_paths))  # noqa: S608
            con.execute(f"DELETE FROM words WHERE path IN ({placeholders})", list(deleted_paths))  # noqa: S608

        # Identify changed/new files
        changed_paths = []
        for path, mtime in current_files.items():
            stored_mtime = stored_files.get(path)
            if stored_mtime != mtime:
                changed_paths.append(path)

        # Remove old words for changed files
        if changed_paths:
            placeholders = ",".join("?" for _ in changed_paths)
            con.execute(f"DELETE FROM words WHERE path IN ({placeholders})", changed_paths)  # noqa: S608

        # Process and insert words for changed/new files
        words_data = []
        for path in changed_paths:
            dj_file = yak_dir / path
            words_data.extend(_process_file_words(dj_file, path))

        if words_data:
            con.executemany("INSERT INTO words (path, line_num, word) VALUES (?, ?, ?)", words_data)

        # Update files table
        for path, mtime in current_files.items():
            con.execute("INSERT OR REPLACE INTO files (path, mtime) VALUES (?, ?)", (path, mtime))

        con.execute("COMMIT")

    set_last_update_time(time.time())


def should_update_index(yak_dir: SyncPath) -> bool:
    """Check if search index should be updated.

    Returns:
        True if the index should be updated, False otherwise.
    """
    now = time.time()
    last_update = get_last_update_time()

    # Don't update more than once per minute
    if now - last_update < INDEX_UPDATE_INTERVAL_SECONDS:
        return False

    # Check if any files have changed
    stored_files = get_stored_files()
    for dj_file in yak_dir.rglob("*.dj"):
        if dj_file.is_file():
            rel_path = dj_file.relative_to(yak_dir).as_posix()
            current_mtime = dj_file.stat().st_mtime
            stored_mtime = stored_files.get(rel_path)
            if stored_mtime != current_mtime:
                return True

    # Check for new or deleted files
    current_paths = {dj_file.relative_to(yak_dir).as_posix() for dj_file in yak_dir.rglob("*.dj") if dj_file.is_file()}
    stored_paths = set(stored_files.keys())
    return current_paths != stored_paths


PREVIEW_LENGTH = 200
"""Number of characters for content preview."""


@dataclass(frozen=True)
class YaksQueryParams:
    """Parameters for querying and paginating Djot yaks.

    Attributes:
        page: Current page number (1-based)
        sort_by: Sorting criteria (name or modified date)
        category: Optional category filter (parent directory name)
        page_size: Number of yaks per page (default: 30)
    """

    page: int
    sort_by: SortBy
    category: str | None
    page_size: int = 30  # Currently not configurable

    @classmethod
    async def from_request(cls, request: Request, categories: set[str]) -> Self:
        """Parse and validate query parameters from HTTP request.

        Args:
            request: Starlette request object containing query parameters
            categories: Set of valid category names for validation

        Returns:
            YaksQueryParams instance with parsed and validated parameters.
        """
        try:
            # Must be positive integer
            page = max(int(request.query_params.get("page", "1")), 1)
        except ValueError:
            page = 1

        try:
            sort_by = SortBy(request.query_params.get("sort_by", "").lower())
        except ValueError:
            sort_by = SortBy.NAME

        if (category := request.query_params.get("category") or None) and category not in categories:
            # TODO: Bind the ignored category to logs
            category = None

        return cls(page=page, sort_by=sort_by, category=category)


async def get_yaks(pth: Path) -> list[Path]:
    """Return djot yak paths.

    Args:
        pth: top-level directory to search

    Returns:
        List of djot yaks
    """
    if not await pth.exists() or not await pth.is_dir():
        return []
    return [_f async for _f in pth.rglob("*.dj") if await _f.is_file()]


async def get_categories(all_paths: list[Path]) -> set[str]:
    """Get list of available categories (parent directories).

    Args:
        all_paths: paths to djot notes

    Returns:
        List of category names (parent directory names)
    """
    return {_f.parent.name for _f in all_paths if await _f.is_file()}


async def get_djot_yaks(paths: list[Path], query_params: YaksQueryParams) -> tuple[list[Path], int, int]:
    """Get a paginated list of Djot yaks from the specified directory.

    Args:
        paths: paths to djot yaks
        query_params: YaksQueryParams

    Returns:
        Tuple containing (list of yak paths, total number of yaks, total pages)
    """
    if not paths:
        return [], 0, 0

    if query_params.category:
        paths = [_f for _f in paths if _f.parent.name == query_params.category]

    if query_params.sort_by == SortBy.MODIFIED_DATE:
        # Collect mtimes asynchronously, then sort DESC
        path_mtimes = [(pth, (await pth.stat()).st_mtime) for pth in paths]
        path_mtimes.sort(key=itemgetter(1), reverse=True)
        paths = [pth for pth, _ in path_mtimes]
    else:
        paths = sorted(paths, key=lambda pth: pth.name.lower(), reverse=True)

    page_size = query_params.page_size
    total_yaks = len(paths)
    total_pages = (total_yaks + page_size - 1) // page_size

    start_idx = (query_params.page - 1) * page_size
    end_idx = min(start_idx + page_size, total_yaks)

    return paths[start_idx:end_idx], total_yaks, total_pages


async def prepare_yaks(paths: list[Path], yak_dir: Path) -> list[YakInfo]:
    """Prepare yak data for template rendering.

    Args:
        paths: List of yak paths to process
        yak_dir: Base directory for computing relative paths

    Returns:
        List of YakInfo objects containing yak information for template
    """
    yaks = []
    for yak_path in paths:
        yak_stats = await yak_path.stat()
        last_modified = datetime.fromtimestamp(yak_stats.st_mtime, tz=UTC).strftime("%Y-%m-%d %H:%M:%S")
        content = await yak_path.read_text(encoding="utf-8")
        preview = content[:PREVIEW_LENGTH].replace("\n", " ")

        info = YakInfo(
            category=yak_path.parent.name,
            last_modified=last_modified,
            name=yak_path.name,
            path=yak_path.relative_to(yak_dir).as_posix(),
            preview=preview,
            truncated=len(content) > PREVIEW_LENGTH,
        )
        yaks.append(info)

    return yaks


async def get_yak_dir() -> Path:
    """Returns the `YAK_SHEARS_DIR` of fallback."""
    return await Path(os.getenv("YAK_SHEARS_DIR", "~/Sync/yak-shears")).expanduser()


async def yaks_handler(request: Request) -> Response:
    """Handle requests to /yaks.

    Args:
        request: The incoming request

    Returns:
        Response with paginated yak listing
    """
    yak_dir = await get_yak_dir()

    all_paths = await get_yaks(yak_dir)
    categories = await get_categories(all_paths)

    query_params = await YaksQueryParams.from_request(request, categories)

    paths, total_yaks, total_pages = await get_djot_yaks(all_paths, query_params=query_params)
    yaks = await prepare_yaks(paths, yak_dir)
    yak_dir_label = "./" + yak_dir.relative_to(yak_dir.parents[1]).as_posix()
    return render_yaks(
        yaks=yaks,
        current_page=query_params.page,
        total_pages=total_pages,
        total_yaks=total_yaks,
        yak_dir_label=yak_dir_label,
        sort_by=query_params.sort_by,
        current_category=query_params.category,
        categories=categories,
    )


async def new_yak_handler(request: Request) -> Response:
    """Handle requests to /new.

    Args:
        request: The incoming request

    Returns:
        Response with new yak form or redirect to edit
    """
    yak_dir = await get_yak_dir()

    all_paths = await get_yaks(yak_dir)
    categories = await get_categories(all_paths)

    if request.method == "POST":
        form_data = await request.form()
        category = str(form_data.get("new_category", "")).strip() or str(form_data.get("category", "")).strip()

        if not category:
            return render_error("Category is required")

        # Create category directory if it doesn't exist
        category_dir = yak_dir / category
        await category_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename based on current timestamp
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}.dj"
        yak_path = category_dir / filename

        # Create empty file
        await yak_path.write_text("", encoding="utf-8")

        # Redirect to edit
        relative_path = yak_path.relative_to(yak_dir).as_posix()
        return RedirectResponse(f"/edit?yak={relative_path}", status_code=HTTPStatus.SEE_OTHER)

    return render_yak_new(categories)


async def edit_yak_handler(request: Request) -> Response:
    """Handle requests to /edit.

    Args:
        request: The incoming request

    Returns:
        Response with yak editor or redirect
    """
    yak_dir = await get_yak_dir()

    if request.headers.get("HX-Request") == "true":  # POST logic
        form_data = await request.form()
        yak_path_str = str(form_data.get("yak", ""))
        _query = str(form_data.get("q", ""))  # Not used yet
    else:
        yak_path_str = request.query_params.get("yak") or ""
        _query = request.query_params.get("query", "")  # Not used yet

    if not yak_path_str:
        return render_error("No `yak` path specified")

    try:
        yak_path = yak_dir / yak_path_str

        if not await yak_path.is_file():
            return render_error(f"Yak not found: {yak_path}", status_code=HTTPStatus.NOT_FOUND)

        if request.method == "POST":
            form_data = await request.form()
            content = str(form_data.get("content", ""))
            await yak_path.write_text(content, encoding="utf-8")
            return HTMLResponse("")  # Return empty response, JS handles the status update

        content = await yak_path.read_text(encoding="utf-8")
        relative_path = yak_path.relative_to(yak_dir).as_posix()
        category = yak_path.parent.name if yak_path.parent != yak_dir else ""
        return render_yak_edit(relative_path, content, category)
    except Exception as exc:
        return render_error(f"An error occurred: {exc!s}", status_code=HTTPStatus.INTERNAL_SERVER_ERROR)


def _ensure_search_index_updated(sync_yak_dir: SyncPath) -> None:
    """Ensure the search index is up to date."""
    try:
        if should_update_index(sync_yak_dir):
            update_search_index(sync_yak_dir)
        else:
            # Also update if database has no words (e.g., after reset)
            with get_search_db() as con:
                result = con.execute("SELECT COUNT(*) FROM words").fetchone()
            if result and result[0] == 0:
                update_search_index(sync_yak_dir)
    except Exception as exc:
        log(f"WARNING: Failed to update search index: {exc}")


def _perform_search(query: str) -> list[tuple[str, int, str]]:
    """Perform the search query and return raw results.

    Returns:
        List of tuples containing path, line number, and matched word.
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


def _process_search_results(search_results: list[tuple[str, int, str]], sync_yak_dir: SyncPath) -> list[SearchResult]:
    """Process raw search results into SearchResult objects.

    Returns:
        List of SearchResult objects with previews.
    """
    results = []
    seen = set()
    for path, line_num, word in search_results:
        key = (path, line_num)
        if key not in seen:
            seen.add(key)
            file_path = sync_yak_dir / path
            try:
                content = file_path.read_text(encoding="utf-8")
                lines = content.splitlines()
                if 1 <= line_num <= len(lines):
                    preview = lines[line_num - 1].strip()
                    results.append(SearchResult(path=path, line_num=line_num, preview=preview, word=word))
            except Exception as exc:
                log(f"WARNING: Error reading file {file_path}: {exc}")
    return results


async def search_handler(request: Request) -> Response:
    """Handle requests to /search.

    Args:
        request: The incoming request

    Returns:
        Response with search results
    """
    query = request.query_params.get("query", "").strip()
    is_htmx = request.headers.get("HX-Request") == "true"

    if not query:
        if is_htmx:
            return HTMLResponse('<div class="search-empty"><p>Start typing to search your yaks...</p></div>')
        return render_search([], query)

    # Initialize database if needed
    if not await Path(get_search_db_path()).exists():
        init_search_db()

    yak_dir = await get_yak_dir()
    sync_yak_dir = SyncPath(yak_dir)

    # Ensure index is updated
    _ensure_search_index_updated(sync_yak_dir)

    # Perform search
    try:
        search_results = _perform_search(query)
    except Exception as exc:
        log(f"ERROR: Search database query failed: {exc}")
        return render_error("Search is temporarily unavailable", status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

    # Process results
    results = _process_search_results(search_results, sync_yak_dir)

    if is_htmx:
        return _render_template("search/search_results.html.jinja", results=results, query=query)

    return render_search(results, query)


async def yak_preview_handler(request: Request) -> Response:
    """Handle requests for yak preview.

    Args:
        request: The incoming request

    Returns:
        JSON response with preview HTML
    """
    path = request.query_params.get("path", "")
    line = int(request.query_params.get("line", "1"))
    query = request.query_params.get("query", "")

    if not path:
        return JSONResponse({"error": "Path required"}, status_code=400)

    yak_dir = await get_yak_dir()
    yak_path = yak_dir / path

    if not await yak_path.exists():
        return JSONResponse({"error": "File not found"}, status_code=404)

    try:
        content = await yak_path.read_text(encoding="utf-8")
        lines = content.splitlines()
    except Exception as exc:
        log(f"ERROR: Failed to read file {yak_path}: {exc}")
        return JSONResponse({"error": "Failed to read file"}, status_code=500)

    # Get context around the matching line
    start_line = max(0, line - 6)
    end_line = min(len(lines), line + 5)
    preview_lines = lines[start_line:end_line]

    # Highlight matches
    def highlight_line(preview_line: str) -> str:
        highlighted = preview_line
        if query:
            query_words = query.lower().split()
            for word in query_words:
                if word.strip():
                    pattern = re.compile(re.escape(word), re.IGNORECASE)
                    highlighted = pattern.sub(
                        lambda m: f'<span class="search-highlight">{m.group(0)}</span>', highlighted
                    )
        return highlighted

    highlighted_lines = [
        f"{' >' if i == line else '  '}{i:4d}: {highlight_line(preview_line)}"
        for i, preview_line in enumerate(preview_lines, start_line + 1)
    ]

    edit_url = f"/edit?yak={quote(path)}&query={quote(query)}"
    html = (
        f'<div class="search-preview-header">'
        f'<a href="{edit_url}" class="button button--primary">Edit</a>'
        f"</div>"
        f'<pre class="search-preview-content">' + "\n".join(highlighted_lines) + "</pre>"
    )

    return JSONResponse({"html": html})
