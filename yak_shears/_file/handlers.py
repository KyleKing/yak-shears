"""Handlers for Yak Shears."""

from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from operator import itemgetter
from os import getenv
from typing import Self

from anyio import Path
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from yak_shears._templates import SortBy, YakInfo, render_error, render_yak_edit, render_yaks_list

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
    return [f async for f in pth.rglob("*.dj") if await f.is_file()]


async def get_categories(all_paths: list[Path]) -> set[str]:
    """Get list of available categories (parent directories).

    Args:
        all_paths: paths to djot notes

    Returns:
        List of category names (parent directory names)
    """
    return {f.parent.name for f in all_paths if await f.is_file()}


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
        paths = [f for f in paths if f.parent.name == query_params.category]

    if query_params.sort_by == SortBy.MODIFIED_DATE:
        # Collect mtimes asynchronously, then sort DESC
        path_mtimes = [(pth, (await pth.stat()).st_mtime) for pth in paths]
        path_mtimes.sort(key=itemgetter(1), reverse=True)
        paths = [pth for pth, _ in path_mtimes]
    else:
        paths = sorted(paths, key=lambda pth: pth.name.lower(), reverse=True)

    page_size = query_params.page_size
    total_files = len(paths)
    total_pages = (total_files + page_size - 1) // page_size

    start_idx = (query_params.page - 1) * page_size
    end_idx = min(start_idx + page_size, total_files)

    return paths[start_idx:end_idx], total_files, total_pages


async def prepare_yaks(paths: list[Path]) -> list[YakInfo]:
    """Prepare yak data for template rendering.

    Args:
        paths: List of yak paths to process

    Returns:
        List of FileInfo objects containing yak information for template
    """
    files = []
    for file_path in paths:
        file_stats = await file_path.stat()
        last_modified = datetime.fromtimestamp(file_stats.st_mtime, tz=UTC).strftime("%Y-%m-%d %H:%M:%S")
        content = await file_path.read_text(encoding="utf-8")
        preview = content[:PREVIEW_LENGTH].replace("\n", " ")

        info = YakInfo(
            category=file_path.parent.name,
            last_modified=last_modified,
            name=file_path.name,
            path=str(file_path),
            preview=preview,
            truncated=len(content) > PREVIEW_LENGTH,
        )
        files.append(info)

    return files


async def yaks_handler(request: Request) -> Response:
    """Handle requests to /files.

    Args:
        request: The incoming request

    Returns:
        Response with paginated yak listing
    """
    directory_path = await Path(getenv("YAK_SHEARS_DIR", "~/Sync/yak-shears")).expanduser()

    all_paths = await get_yaks(directory_path)
    categories = await get_categories(all_paths)

    query_params = await YaksQueryParams.from_request(request, categories)

    paths, total_yaks, total_pages = await get_djot_yaks(all_paths, query_params=query_params)
    yaks = await prepare_yaks(paths)
    yak_dir_label = "./" + directory_path.relative_to(directory_path.parents[1]).as_posix()
    return render_yaks_list(
        yaks=yaks,
        current_page=query_params.page,
        total_pages=total_pages,
        total_yaks=total_yaks,
        yak_dir_label=yak_dir_label,
        sort_by=query_params.sort_by,
        current_category=query_params.category,
        categories=categories,
    )


async def edit_yak_handler(request: Request) -> Response:
    """Handle requests to /edit.

    Args:
        request: The incoming request

    Returns:
        Response with yak editor or redirect
    """
    # For HTMX requests, get yak from form data, otherwise from query params
    if request.headers.get("HX-Request") == "true":
        form_data = await request.form()
        yak_path_str = str(form_data.get("yak", ""))
    else:
        yak_path_str = request.query_params.get("yak") or ""

    if not yak_path_str:
        return render_error("No yak specified")

    try:
        yak_path = Path(yak_path_str)
        if not await yak_path.exists() or not await yak_path.is_file():
            return render_error(f"Yak not found: {yak_path}", status_code=HTTPStatus.NOT_FOUND)

        # If the request includes content, save the changes
        if request.method == "POST":
            form_data = await request.form()
            content = str(form_data.get("content", ""))
            await yak_path.write_text(content, encoding="utf-8")

            # Check if this is an HTMX request
            if request.headers.get("HX-Request") == "true":
                # Return empty response, JS handles the status update
                return HTMLResponse("")
            # Traditional form submission - redirect
            return RedirectResponse(url=f"/edit?yak={yak_path_str}", status_code=303)

        # Generate HTML editor
        content = await yak_path.read_text(encoding="utf-8")
        return render_yak_edit(str(yak_path), content)
    except Exception as e:
        return render_error(f"An error occurred: {e!s}", status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
