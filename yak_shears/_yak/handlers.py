"""Handlers for Yak Shears."""

import os
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from operator import itemgetter
from pathlib import Path as SyncPath
from typing import Self

import duckdb
from anyio import Path
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

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

# Search database functions
SEARCH_DB_PATH = SyncPath("yak_shears_search.db")


def get_search_db():
    """Get connection to search database."""
    return duckdb.connect(str(SEARCH_DB_PATH))


def init_search_db():
    """Initialize search database schema."""
    con = get_search_db()
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
    con.close()


def get_last_update_time():
    """Get the last update timestamp."""
    con = get_search_db()
    result = con.execute("SELECT value FROM metadata WHERE key = 'last_update'").fetchone()
    con.close()
    return float(result[0]) if result else 0


def set_last_update_time(timestamp):
    """Set the last update timestamp."""
    con = get_search_db()
    con.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES ('last_update', ?)", (str(timestamp),))
    con.close()


def get_stored_files():
    """Get dict of path -> mtime from database."""
    con = get_search_db()
    result = con.execute("SELECT path, mtime FROM files").fetchall()
    con.close()
    return {row[0]: row[1] for row in result}


def update_search_index(yak_dir: SyncPath):
    """Update the search index with current files."""
    current_files = {}
    words_data = []

    # Scan all .dj files
    for dj_file in yak_dir.rglob("*.dj"):
        if dj_file.is_file():
            rel_path = dj_file.relative_to(yak_dir).as_posix()
            mtime = dj_file.stat().st_mtime
            current_files[rel_path] = mtime

            # Read content and extract words
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
                    for word in unique_words:
                        words_data.append((rel_path, line_num, word))
            except Exception:
                # Skip files that can't be read
                continue

    con = get_search_db()
    con.execute("BEGIN")

    # Remove deleted files
    stored_paths = set(con.execute("SELECT path FROM files").fetchall())
    stored_paths = {row[0] for row in stored_paths}
    current_paths = set(current_files.keys())
    deleted_paths = stored_paths - current_paths
    if deleted_paths:
        placeholders = ",".join("?" for _ in deleted_paths)
        con.execute(f"DELETE FROM files WHERE path IN ({placeholders})", list(deleted_paths))
        con.execute(f"DELETE FROM words WHERE path IN ({placeholders})", list(deleted_paths))

    # Update files table
    for path, mtime in current_files.items():
        con.execute("INSERT OR REPLACE INTO files (path, mtime) VALUES (?, ?)", (path, mtime))

    # Clear and reinsert words for updated files
    # For simplicity, clear all words and reinsert (could be optimized)
    con.execute("DELETE FROM words")
    if words_data:
        con.executemany("INSERT INTO words (path, line_num, word) VALUES (?, ?, ?)", words_data)

    con.execute("COMMIT")
    con.close()

    set_last_update_time(time.time())


def should_update_index(yak_dir: SyncPath):
    """Check if search index should be updated."""
    now = time.time()
    last_update = get_last_update_time()

    # Don't update more than once per minute
    if now - last_update < 60:
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
    if current_paths != stored_paths:
        return True

    return False


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
    else:
        yak_path_str = request.query_params.get("yak") or ""

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
    except Exception as e:
        return render_error(f"An error occurred: {e!s}", status_code=HTTPStatus.INTERNAL_SERVER_ERROR)


async def search_handler(request: Request) -> Response:
    """Handle requests to /search.

    Args:
        request: The incoming request

    Returns:
        Response with search results
    """
    query = request.query_params.get("q", "").strip()
    is_htmx = request.headers.get("HX-Request") == "true"

    if not query:
        if is_htmx:
            return HTMLResponse('<div class="search-empty"><p>Start typing to search your yaks...</p></div>')
        return render_search([], query)

    # Initialize database if needed
    if not await Path(SEARCH_DB_PATH).exists():
        init_search_db()

    yak_dir = await get_yak_dir()
    sync_yak_dir = SyncPath(yak_dir)

    # Check if we need to update the index
    if should_update_index(sync_yak_dir):
        update_search_index(sync_yak_dir)

    # Search the database
    con = get_search_db()
    threshold = max(1, len(query) // 4)
    sql = """
        SELECT path, line_num, word
        FROM words
        WHERE levenshtein(word, lower(?)) <= ?
        ORDER BY levenshtein(word, lower(?))
        LIMIT 1000
    """
    search_results = con.execute(sql, (query, threshold, query)).fetchall()
    con.close()

    # Group by path and line_num, take first match per line
    results = []
    seen = set()
    for path, line_num, word in search_results:
        key = (path, line_num)
        if key not in seen:
            seen.add(key)
            # Get the line content (simplified - could cache this)
            try:
                file_path = sync_yak_dir / path
                content = file_path.read_text(encoding="utf-8")
                lines = content.splitlines()
                if 1 <= line_num <= len(lines):
                    preview = lines[line_num - 1].strip()
                    results.append(SearchResult(path=path, line_num=line_num, preview=preview, word=word))
            except Exception:
                continue

    if is_htmx:
        return _render_template("search_results.html.jinja", results=results, query=query)

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
    query = request.query_params.get("q", "")

    if not path:
        return JSONResponse({"error": "Path required"}, status_code=400)

    yak_dir = await get_yak_dir()
    yak_path = yak_dir / path

    if not await yak_path.exists():
        return JSONResponse({"error": "File not found"}, status_code=404)

    content = await yak_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    # Get context around the matching line
    start_line = max(0, line - 6)
    end_line = min(len(lines), line + 5)
    preview_lines = lines[start_line:end_line]

    # Highlight matches
    highlighted_lines = []
    for i, preview_line in enumerate(preview_lines, start_line + 1):
        highlighted_line = preview_line
        if query:
            # Split query into words and highlight each
            query_words = query.lower().split()
            for word in query_words:
                if word.strip():
                    # Use regex to find matches case-insensitively
                    pattern = re.compile(re.escape(word), re.IGNORECASE)
                    highlighted_line = pattern.sub(
                        lambda m: f'<span class="search-highlight">{m.group(0)}</span>', highlighted_line
                    )

        line_marker = ">" if i == line else " "
        line_prefix = f"{line_marker}{i:4d}: "
        highlighted_lines.append(f"{line_prefix}{highlighted_line}")

    html = '<pre class="search-preview-content">' + "\n".join(highlighted_lines) + "</pre>"

    return JSONResponse({"html": html})
