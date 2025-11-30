"""HTTP request handlers for Yak Shears."""

from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path as SyncPath
from typing import Self
from urllib.parse import quote

from anyio import Path
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from yak_shears._log_utils import log
from yak_shears._templates import (
    SortBy,
    _render_template,
    render_error,
    render_search,
    render_yak_edit,
    render_yak_new,
    render_yaks,
)
from yak_shears._yak.database import get_backlinks, get_frontmatter
from yak_shears._yak.request_utils import extract_yak_path, is_htmx_request
from yak_shears._yak.services import (
    create_yak,
    delete_yak,
    ensure_search_db_ready,
    ensure_search_index_updated,
    get_categories,
    get_yak_dir,
    highlight_content,
    list_yak_paths,
    paginate_yaks,
    perform_search,
    prepare_yak_info,
    read_yak,
    save_yak,
)


@dataclass(frozen=True)
class YaksQueryParams:
    """Parameters for querying and paginating Djot yaks."""

    page: int
    sort_by: SortBy
    category: str | None
    page_size: int = 30

    @classmethod
    async def from_request(cls, request: Request, categories: set[str]) -> Self:
        """Parse and validate query parameters from HTTP request."""
        try:
            page = max(int(request.query_params.get("page", "1")), 1)
        except ValueError:
            page = 1

        try:
            sort_by = SortBy(request.query_params.get("sort_by", "").lower())
        except ValueError:
            sort_by = SortBy.NAME

        category = request.query_params.get("category") or None
        if category and category not in categories:
            category = None

        return cls(page=page, sort_by=sort_by, category=category)


# -----------------------------------------------------------------------------
# Handlers


async def yaks_handler(request: Request) -> Response:
    """Handle requests to /yaks."""
    yak_dir = await get_yak_dir()
    all_paths = await list_yak_paths(yak_dir)
    categories = await get_categories(all_paths)

    query_params = await YaksQueryParams.from_request(request, categories)

    result = await paginate_yaks(
        paths=all_paths,
        page=query_params.page,
        page_size=query_params.page_size,
        sort_by=query_params.sort_by,
        category=query_params.category,
    )
    yaks = await prepare_yak_info(result.paths, yak_dir)
    yak_dir_label = "./" + yak_dir.relative_to(yak_dir.parents[1]).as_posix()

    return render_yaks(
        yaks=yaks,
        current_page=query_params.page,
        total_pages=result.total_pages,
        total_yaks=result.total_count,
        yak_dir_label=yak_dir_label,
        sort_by=query_params.sort_by,
        current_category=query_params.category,
        categories=categories,
    )


async def new_yak_handler(request: Request) -> Response:
    """Handle requests to /new."""
    yak_dir = await get_yak_dir()
    all_paths = await list_yak_paths(yak_dir)
    categories = await get_categories(all_paths)

    if request.method == "POST":
        form_data = await request.form()
        category = str(form_data.get("new_category", "")).strip() or str(form_data.get("category", "")).strip()

        if not category:
            return render_error("Category is required")

        yak_path = await create_yak(yak_dir, category)
        relative_path = yak_path.relative_to(yak_dir).as_posix()
        return RedirectResponse(f"/edit?yak={relative_path}", status_code=HTTPStatus.SEE_OTHER)

    return render_yak_new(categories)


async def edit_yak_handler(request: Request) -> Response:
    """Handle requests to /edit."""
    yak_dir = await get_yak_dir()
    yak_path_str = await extract_yak_path(request)

    if not yak_path_str:
        return render_error("No `yak` path specified")

    try:
        if request.method == "POST":
            form_data = await request.form()
            content = str(form_data.get("content", ""))
            await save_yak(yak_dir, yak_path_str, content)
            return HTMLResponse("")

        content, category = await read_yak(yak_dir, yak_path_str)
        frontmatter = get_frontmatter(yak_path_str)
        backlinks = get_backlinks(yak_path_str)

        return render_yak_edit(yak_path_str, content, category, frontmatter=frontmatter, backlinks=backlinks)
    except FileNotFoundError:
        return render_error(f"Yak not found: {yak_path_str}", status_code=HTTPStatus.NOT_FOUND)
    except Exception as exc:
        return render_error(f"An error occurred: {exc!s}", status_code=HTTPStatus.INTERNAL_SERVER_ERROR)


async def search_handler(request: Request) -> Response:
    """Handle requests to /search."""
    query = request.query_params.get("query", "").strip()

    if not query:
        if is_htmx_request(request):
            return HTMLResponse('<div class="search-empty"><p>Start typing to search your yaks...</p></div>')
        return render_search([], query)

    await ensure_search_db_ready()

    yak_dir = await get_yak_dir()
    sync_yak_dir = SyncPath(yak_dir)

    ensure_search_index_updated(sync_yak_dir)

    try:
        results = perform_search(query, sync_yak_dir)
    except Exception as exc:
        log(f"ERROR: Search database query failed: {exc}")
        return render_error("Search is temporarily unavailable", status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

    if is_htmx_request(request):
        return _render_template("search/search_results.html.jinja", results=results, query=query)

    return render_search(results, query)


async def delete_yak_handler(request: Request) -> Response:
    """Handle requests to delete a yak."""
    yak_dir = await get_yak_dir()
    yak_path_str = await extract_yak_path(request)

    if not yak_path_str:
        return render_error("No `yak` path specified")

    try:
        await delete_yak(yak_dir, yak_path_str)
        return Response("", status_code=HTTPStatus.OK, headers={"HX-Redirect": "/yaks"})
    except FileNotFoundError:
        return render_error(f"Yak not found: {yak_path_str}", status_code=HTTPStatus.NOT_FOUND)
    except Exception as exc:
        return render_error(f"An error occurred: {exc!s}", status_code=HTTPStatus.INTERNAL_SERVER_ERROR)


async def yak_preview_handler(request: Request) -> Response:
    """Handle requests for yak preview."""
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
    except Exception as exc:
        log(f"ERROR: Failed to read file {yak_path}: {exc}")
        return JSONResponse({"error": "Failed to read file"}, status_code=500)

    highlighted_content = highlight_content(content, query)
    edit_url = f"/edit?yak={quote(path)}&query={quote(query)}"

    html = (
        f'<div class="search-preview-header">'
        f'<a href="{edit_url}" class="button button--primary">Edit</a>'
        f"</div>"
        f'<pre class="search-preview-content">{highlighted_content}</pre>'
    )

    return JSONResponse({"html": html})


# Re-export for backwards compatibility with tests
get_search_db_path = __import__("yak_shears._yak.database", fromlist=["get_search_db_path"]).get_search_db_path
