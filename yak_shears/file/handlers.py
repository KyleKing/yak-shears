"""Handlers for Yak Shears."""

from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path

from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from yak_shears.templates import render_error, render_file_edit, render_files_list

PREVIEW_LENGTH = 200
"""Number of characters for content preview."""


@dataclass(frozen=True)
class FilesQueryParams:
    """Query parameters for files listing endpoint."""

    page: int
    sort_by: str
    category: str | None
    page_size: int = 30

    @classmethod
    def from_request(cls, request: Request) -> "FilesQueryParams":
        """Parse query parameters from request.

        Returns:
            FilesQueryParams instance with parsed and validated parameters.
        """
        try:
            page = max(int(request.query_params.get("page", "1")), 1)
        except ValueError:
            page = 1

        # TODO: Validate against an enum rather than hardcoded string
        sort_by = request.query_params.get("sort_by", "name").lower()
        category = request.query_params.get("category")

        return cls(page=page, sort_by=sort_by, category=category)


def get_categories(directory_path: str) -> set[str]:
    """Get list of available categories (parent directories) from the specified directory.

    Args:
        directory_path: Path to the directory to scan for categories

    Returns:
        List of category names (parent directory names)
    """
    pth = Path(directory_path).expanduser()
    if not pth.exists() or not pth.is_dir():
        return set()
    return {f.parent.name for f in pth.rglob("*.dj") if f.is_file()}


# TODO: Evaluate at how many files a TTL cache would improve performance
def _paths(directory_path: str) -> list[Path]:
    """Return matching file paths."""
    pth = Path(directory_path).expanduser()
    if not pth.exists() or not pth.is_dir():
        return []
    return [f for f in pth.rglob("*.dj") if f.is_file()]


def get_djot_files(
    directory_path: str,
    query_params: FilesQueryParams,
) -> tuple[list[Path], int, int]:
    """Get a paginated list of Djot files from the specified directory.

    Args:
        directory_path: Path to the directory to list files from
        query_params: FilesQueryParams

    Returns:
        Tuple containing (list of file paths, total number of files, total pages)
    """
    if not (paths := _paths(directory_path)):
        return [], 0, 0

    if query_params.category:
        paths = [f for f in paths if f.parent.name == query_params.category]

    if query_params.sort_by == "date":
        paths = sorted(paths, key=lambda x: x.stat().st_mtime, reverse=True)
    else:
        paths = sorted(paths, key=lambda x: x.name.lower())

    page_size = query_params.page_size
    total_files = len(paths)
    total_pages = (total_files + page_size - 1) // page_size

    start_idx = (query_params.page - 1) * page_size
    end_idx = min(start_idx + page_size, total_files)

    return paths[start_idx:end_idx], total_files, total_pages


def prepare_files(paths: list[Path]) -> list[dict[str, str | bool]]:
    """Prepare file data for template rendering.

    Args:
        paths: List of file paths to process

    Returns:
        List of dictionaries containing file information for template
    """
    files = []
    for file_path in paths:
        file_stats = file_path.stat()
        last_modified = datetime.fromtimestamp(file_stats.st_mtime, tz=UTC).strftime("%Y-%m-%d %H:%M:%S")
        content = file_path.read_text(encoding="utf-8")
        preview = content[:PREVIEW_LENGTH].replace("\n", " ")

        info: dict[str, str | bool] = {
            "path": str(file_path),
            "name": file_path.name,
            "preview": preview,
            "truncated": len(content) > PREVIEW_LENGTH,
            "last_modified": last_modified,
        }
        files.append(info)

    return files


async def files_handler(request: Request) -> Response:  # noqa: RUF029
    """Handle requests to /files.

    Args:
        request: The incoming request

    Returns:
        Response with paginated file listing
    """
    directory_path = "~/Sync/yak-shears"

    query_params = FilesQueryParams.from_request(request)

    paths, total_files, total_pages = get_djot_files(directory_path, query_params=query_params)
    categories = get_categories(directory_path)
    files = prepare_files(paths)
    return render_files_list(
        files=files,
        current_page=query_params.page,
        total_pages=total_pages,
        total_files=total_files,
        directory_path=directory_path,
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
