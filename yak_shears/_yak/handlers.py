"""Handlers for Yak Shears."""

import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from operator import itemgetter
from pathlib import Path as SyncPath
from typing import Self
from urllib.parse import quote

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
from yak_shears._yak.database import (
    check_tables_exist,
    get_backlinks,
    get_frontmatter,
    get_search_db_path,
    get_word_count,
    init_search_db,
    replace_links,
    search_words,
    should_update_index,
    update_search_index,
    upsert_frontmatter,
)
from yak_shears.frontmatter import parse_frontmatter
from yak_shears.links import extract_all_links


def index_yak_metadata(yak_path: SyncPath, yak_dir: SyncPath) -> None:
    """Index frontmatter and links from a yak file.

    Args:
        yak_path: Full path to the yak file
        yak_dir: Base directory for relative paths
    """
    try:
        rel_path = yak_path.relative_to(yak_dir).as_posix()
        content = yak_path.read_text(encoding="utf-8")

        frontmatter, body = parse_frontmatter(content)
        links = extract_all_links(body)

        upsert_frontmatter(rel_path, frontmatter)
        replace_links(rel_path, links)
    except Exception as exc:
        log(f"WARNING: Failed to index metadata for {yak_path}: {exc}")


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

            # Index frontmatter and links
            sync_yak_path = SyncPath(yak_path)
            sync_yak_dir = SyncPath(yak_dir)
            index_yak_metadata(sync_yak_path, sync_yak_dir)

            return HTMLResponse("")  # Return empty response, JS handles the status update

        content = await yak_path.read_text(encoding="utf-8")
        relative_path = yak_path.relative_to(yak_dir).as_posix()
        category = yak_path.parent.name if yak_path.parent != yak_dir else ""

        # Get frontmatter and backlinks for metadata panel
        frontmatter = get_frontmatter(relative_path)
        backlinks = get_backlinks(relative_path)

        return render_yak_edit(relative_path, content, category, frontmatter=frontmatter, backlinks=backlinks)
    except Exception as exc:
        return render_error(f"An error occurred: {exc!s}", status_code=HTTPStatus.INTERNAL_SERVER_ERROR)


def _ensure_search_index_updated(sync_yak_dir: SyncPath) -> None:
    """Ensure the search index is up to date."""
    try:
        if should_update_index(sync_yak_dir) or get_word_count() == 0:
            update_search_index(sync_yak_dir)
    except Exception as exc:
        log(f"WARNING: Failed to update search index: {exc}")


def _process_search_results(search_results: list[tuple[str, int, str]], sync_yak_dir: SyncPath) -> list[SearchResult]:
    """Process raw search results into SearchResult objects, grouped by file.

    Returns:
        List of SearchResult objects with previews, one per file (best match).
    """
    results = []
    seen_paths = set()
    for path, line_num, word in search_results:
        if path not in seen_paths:
            seen_paths.add(path)
            file_path = sync_yak_dir / path
            try:
                content = file_path.read_text(encoding="utf-8")
                lines = content.splitlines()
                if 1 <= line_num <= len(lines):
                    preview = lines[line_num - 1].strip()
                    first_line = lines[0].strip() if lines else ""
                    results.append(
                        SearchResult(path=path, line_num=line_num, preview=preview, word=word, first_line=first_line)
                    )
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
    db_path = get_search_db_path()
    if not await Path(db_path).exists():
        init_search_db()
    elif not check_tables_exist():
        log("WARNING: Search database appears corrupted, reinitializing")
        await Path(db_path).unlink(missing_ok=True)
        init_search_db()

    yak_dir = await get_yak_dir()
    sync_yak_dir = SyncPath(yak_dir)

    # Ensure index is updated
    _ensure_search_index_updated(sync_yak_dir)

    # Perform search
    try:
        search_results = search_words(query)
    except Exception as exc:
        log(f"ERROR: Search database query failed: {exc}")
        return render_error("Search is temporarily unavailable", status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

    # Process results
    results = _process_search_results(search_results, sync_yak_dir)

    if is_htmx:
        return _render_template("search/search_results.html.jinja", results=results, query=query)

    return render_search(results, query)


async def delete_yak_handler(request: Request) -> Response:
    """Handle requests to delete a yak.

    Args:
        request: The incoming request

    Returns:
        Response with HX-Redirect to /yaks after deletion
    """
    yak_dir = await get_yak_dir()

    if request.method == "POST":
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

        # Delete the file
        await yak_path.unlink()

        # Redirect to yaks page using HTMX
        return Response("", status_code=HTTPStatus.OK, headers={"HX-Redirect": "/yaks"})
    except Exception as exc:
        return render_error(f"An error occurred: {exc!s}", status_code=HTTPStatus.INTERNAL_SERVER_ERROR)


async def yak_preview_handler(request: Request) -> Response:
    """Handle requests for yak preview.

    Args:
        request: The incoming request

    Returns:
        JSON response with preview HTML
    """
    path = request.query_params.get("path", "")
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

    # Highlight matches in full content
    def highlight_line(content_line: str) -> str:
        highlighted = content_line
        if query:
            query_words = query.lower().split()
            for word in query_words:
                if word.strip():
                    pattern = re.compile(re.escape(word), re.IGNORECASE)
                    highlighted = pattern.sub(
                        lambda m: f'<span class="search-highlight">{m.group(0)}</span>', highlighted
                    )
        return highlighted

    highlighted_content = "\n".join(highlight_line(line) for line in lines)

    edit_url = f"/edit?yak={quote(path)}&query={quote(query)}"
    html = (
        f'<div class="search-preview-header">'
        f'<a href="{edit_url}" class="button button--primary">Edit</a>'
        f"</div>"
        f'<pre class="search-preview-content">{highlighted_content}</pre>'
    )

    return JSONResponse({"html": html})
