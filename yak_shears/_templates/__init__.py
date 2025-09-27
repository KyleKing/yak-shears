"""Template rendering utilities."""

from dataclasses import dataclass
from enum import StrEnum
from http import HTTPStatus
from pathlib import Path as SyncPath
from typing import Any

from jinja2 import Environment, FileSystemLoader
from starlette.responses import HTMLResponse


class SortBy(StrEnum):
    """Enum for file sorting options."""

    NAME = "name"
    MODIFIED_DATE = "modified_date"


@dataclass(frozen=True)
class FileInfo:
    """File information for template rendering."""

    category: str
    last_modified: str
    name: str
    path: str
    preview: str
    truncated: bool


TEMPLATE_DIR = SyncPath(__file__).parent

ENV = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=True,
)


def _render_template(template_name: str, *, status_code: HTTPStatus = HTTPStatus.OK, **context: Any) -> HTMLResponse:
    """Private render template by name.

    Args:
        template_name: The name of the template to render
        status_code: The HTTP status code to return
        **context: The context variables to pass to the template

    Returns:
        HTMLResponse with the rendered template
    """
    template = ENV.get_template(template_name)
    content = template.render(**context)
    return HTMLResponse(content, status_code=status_code)


def render_error(
    message: str,
    status_code: HTTPStatus = HTTPStatus.BAD_REQUEST,
) -> HTMLResponse:
    """Render an error page.

    Args:
        message: The error message to display
        status_code: The HTTP status code to return

    Returns:
        HTMLResponse with the error template
    """
    return _render_template("error.html.jinja", status_code=status_code, message=message)


def render_auth_login(redirect: str | None = None, error: str = "") -> HTMLResponse:
    """Render an error page.

    Args:
        error: optional error to display
        redirect: optional redirect path

    Returns:
        HTMLResponse with the error template
    """
    status_code = HTTPStatus.BAD_REQUEST if error else HTTPStatus.OK
    return _render_template("auth/login.html.jinja", redirect=redirect, error=error, status_code=status_code)


def render_files_list(
    *,
    files: list[FileInfo],
    current_page: int,
    total_pages: int,
    total_files: int,
    yak_dir_label: str,
    sort_by: SortBy,
    current_category: str | None,
    categories: set[str],
) -> HTMLResponse:
    """Render the files listing page.

    Args:
        files: List of files and metadata
        current_page: Current page number
        total_pages: Total number of pages
        total_files: Total number of files
        yak_dir_label: name of the `YAK_SHEARS_DIR`
        sort_by: Criteria to sort files
        current_category: active category filter currently applied
        categories: set of available categories for filtering

    Returns:
        HTMLResponse with the files listing template
    """
    return _render_template(
        "file/files_list.html.jinja",
        files=files,
        current_page=current_page,
        total_pages=total_pages,
        total_files=total_files,
        yak_dir_label=yak_dir_label,
        sort_by=sort_by,
        current_category=current_category,
        categories=categories,
    )


def render_file_edit(file_path: str, content: str) -> HTMLResponse:
    """Render the file editor page.

    Args:
        file_path: Path of the file being edited
        content: Current content of the file

    Returns:
        HTMLResponse with the file editor template
    """
    file_name = SyncPath(file_path).name
    return _render_template("file/edit.html.jinja", file_name=file_name, file_path=file_path, content=content)
