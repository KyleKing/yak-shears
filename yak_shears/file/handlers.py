"""Handlers for Yak Shears."""

from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path

from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from yak_shears.templates import render_error, render_file_edit, render_files_list

PREVIEW_LENGTH = 200
"""Number of characters for content preview."""


def get_djot_files(
    directory_path: str,
    page: int = 1,
    page_size: int = 30,
    sort_by: str = "name",
) -> tuple[list[Path], int, int]:
    """Get a paginated list of Djot files from the specified directory.

    Args:
        directory_path: Path to the directory to list files from
        page: Current page number (1-indexed)
        page_size: Number of files per page
        sort_by: Criteria to sort files, either 'name' or 'date'

    Returns:
        Tuple containing (list of file paths, total number of files, total pages)
    """
    pth = Path(directory_path).expanduser()
    if not pth.exists() or not pth.is_dir():
        return [], 0, 0

    # TODO: Also need to include the parent directory folder
    all_files = [f for f in pth.rglob("*.dj") if f.is_file()]
    # sort files by name or date
    if sort_by == "date":
        all_files = sorted(all_files, key=lambda x: x.stat().st_mtime, reverse=True)
    else:
        all_files = sorted(all_files, key=lambda x: x.name.lower())
    total_files = len(all_files)
    total_pages = (total_files + page_size - 1) // page_size

    start_idx = (page - 1) * page_size
    end_idx = min(start_idx + page_size, total_files)

    return all_files[start_idx:end_idx], total_files, total_pages


def prepare_file_data(files: list[Path]) -> list[dict[str, str | bool]]:
    """Prepare file data for template rendering.

    Args:
        files: List of file paths to process

    Returns:
        List of dictionaries containing file information for template
    """
    file_data = []
    for file_path in files:
        file_stats = file_path.stat()
        last_modified = datetime.fromtimestamp(file_stats.st_mtime, tz=UTC).strftime("%Y-%m-%d %H:%M:%S")
        content = file_path.read_text(encoding="utf-8")
        preview = content[:PREVIEW_LENGTH].replace("\n", " ")

        data: dict[str, str | bool] = {
            "path": str(file_path),
            "name": file_path.name,
            "preview": preview,
            "truncated": len(content) > PREVIEW_LENGTH,
            "last_modified": last_modified,
        }
        file_data.append(data)

    return file_data


async def files_handler(request: Request) -> Response:  # noqa: RUF029
    """Handle requests to /files.

    Args:
        request: The incoming request

    Returns:
        Response with paginated file listing
    """
    directory_path = "~/Sync/yak-shears"

    # Get page and sort order from query parameters
    try:
        page = int(request.query_params.get("page", "1"))
        page = max(page, 1)
    except ValueError:
        page = 1
    sort_by = request.query_params.get("sort_by", "name").lower()

    # Get files with pagination
    files, total_files, total_pages = get_djot_files(directory_path, page, sort_by=sort_by)

    # Prepare file data for template
    file_data = prepare_file_data(files)

    # Render template
    return render_files_list(file_data, page, total_pages, total_files, directory_path, sort_by)


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
