"""Handlers for Yak Shears."""

from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from os import getenv
from pathlib import Path
from typing import Self

from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from yak_shears.templates import FileInfo, SortBy, render_error, render_file_edit, render_files_list

PREVIEW_LENGTH = 200
"""Number of characters for content preview."""


@dataclass(frozen=True)
class FilesQueryParams:
    """Parameters for querying and paginating Djot files.

    Attributes:
        page: Current page number (1-based)
        sort_by: Sorting criteria (name or modified date)
        category: Optional category filter (parent directory name)
        page_size: Number of files per page (default: 30)
    """

    page: int
    sort_by: SortBy
    category: str | None
    page_size: int = 30  # Currently not configurable

    @classmethod
    def from_request(cls, request: Request, categories: set[str]) -> Self:
        """Parse and validate query parameters from HTTP request.

        Args:
            request: Starlette request object containing query parameters
            categories: Set of valid category names for validation

        Returns:
            FilesQueryParams instance with parsed and validated parameters.
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


def get_notes(pth: Path) -> list[Path]:
    """Return djot note paths.

    Args:
        pth: top-level directory to search

    Returns:
        List of djot notes
    """
    if not pth.exists() or not pth.is_dir():
        return []
    return [f for f in pth.rglob("*.dj") if f.is_file()]


def get_categories(all_paths: list[Path]) -> set[str]:
    """Get list of available categories (parent directories).

    Args:
        all_paths: paths to djot notes

    Returns:
        List of category names (parent directory names)
    """
    return {f.parent.name for f in all_paths if f.is_file()}


def get_djot_files(paths: list[Path], query_params: FilesQueryParams) -> tuple[list[Path], int, int]:
    """Get a paginated list of Djot files from the specified directory.

    Args:
        paths: paths to djot notes
        query_params: FilesQueryParams

    Returns:
        Tuple containing (list of file paths, total number of files, total pages)
    """
    if not paths:
        return [], 0, 0

    if query_params.category:
        paths = [f for f in paths if f.parent.name == query_params.category]

    if query_params.sort_by == SortBy.MODIFIED_DATE:
        paths = sorted(paths, key=lambda x: x.stat().st_mtime, reverse=True)
    else:
        paths = sorted(paths, key=lambda x: x.name.lower(), reverse=True)

    page_size = query_params.page_size
    total_files = len(paths)
    total_pages = (total_files + page_size - 1) // page_size

    start_idx = (query_params.page - 1) * page_size
    end_idx = min(start_idx + page_size, total_files)

    return paths[start_idx:end_idx], total_files, total_pages


def prepare_files(paths: list[Path]) -> list[FileInfo]:
    """Prepare file data for template rendering.

    Args:
        paths: List of file paths to process

    Returns:
        List of FileInfo objects containing file information for template
    """
    files = []
    for file_path in paths:
        file_stats = file_path.stat()
        last_modified = datetime.fromtimestamp(file_stats.st_mtime, tz=UTC).strftime("%Y-%m-%d %H:%M:%S")
        content = file_path.read_text(encoding="utf-8")
        preview = content[:PREVIEW_LENGTH].replace("\n", " ")

        info = FileInfo(
            category=file_path.parent.name,
            last_modified=last_modified,
            name=file_path.name,
            path=str(file_path),
            preview=preview,
            truncated=len(content) > PREVIEW_LENGTH,
        )
        files.append(info)

    return files


async def files_handler(request: Request) -> Response:  # noqa: RUF029
    """Handle requests to /files.

    Args:
        request: The incoming request

    Returns:
        Response with paginated file listing
    """
    directory_path = Path(getenv("YAK_SHEARS_DIR", "~/Sync/yak-shears")).expanduser()

    all_paths = get_notes(directory_path)
    categories = get_categories(all_paths)

    query_params = FilesQueryParams.from_request(request, categories)

    paths, total_files, total_pages = get_djot_files(all_paths, query_params=query_params)
    files = prepare_files(paths)
    yak_dir_label = "./" + directory_path.relative_to(directory_path.parents[1]).as_posix()
    return render_files_list(
        files=files,
        current_page=query_params.page,
        total_pages=total_pages,
        total_files=total_files,
        yak_dir_label=yak_dir_label,
        sort_by=query_params.sort_by,
        current_category=query_params.category,
        categories=categories,
    )


async def edit_file_handler(request: Request) -> Response:
    """Handle requests to /edit.

    Args:
        request: The incoming request

    Returns:
        Response with file editor or redirect
    """
    file_path_str = request.query_params.get("file")

    if not file_path_str:
        return render_error("No file specified")

    try:
        file_path = Path(file_path_str)
        if not file_path.exists() or not file_path.is_file():
            return render_error(f"File not found: {file_path}", status_code=HTTPStatus.NOT_FOUND)

        # If the request includes content, save the changes
        if request.method == "POST":
            form_data = await request.form()
            content = str(form_data.get("content", ""))
            file_path.write_text(content, encoding="utf-8")
            return RedirectResponse(url=f"/edit?file={file_path_str}", status_code=303)

        # Generate HTML editor
        content = file_path.read_text(encoding="utf-8")
        return render_file_edit(file_path.name, content)
    except Exception as e:
        return render_error(f"An error occurred: {e!s}", status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
