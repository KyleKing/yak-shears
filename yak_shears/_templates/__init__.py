"""Template rendering utilities."""

from dataclasses import dataclass
from enum import StrEnum
from http import HTTPStatus
from pathlib import Path as SyncPath
from typing import Any

from jinja2 import Environment, FileSystemLoader
from starlette.responses import HTMLResponse


class SortBy(StrEnum):
    """Enum for yak sorting options."""

    NAME = "name"
    MODIFIED_DATE = "modified_date"


@dataclass(frozen=True)
class YakInfo:
    """Yak information for template rendering."""

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


def render_yaks(
    *,
    yaks: list[YakInfo],
    current_page: int,
    total_pages: int,
    total_yaks: int,
    yak_dir_label: str,
    sort_by: SortBy,
    current_category: str | None,
    categories: set[str],
) -> HTMLResponse:
    """Render the yaks listing page.

    Args:
        yaks: List of yaks and metadata
        current_page: Current page number
        total_pages: Total number of pages
        total_yaks: Total number of yaks
        yak_dir_label: name of the `YAK_SHEARS_DIR`
        sort_by: Criteria to sort yaks
        current_category: active category filter currently applied
        categories: set of available categories for filtering

    Returns:
        HTMLResponse with the yaks listing template
    """
    return _render_template(
        "yaks/index.html.jinja",
        yaks=yaks,
        current_page=current_page,
        total_pages=total_pages,
        total_yaks=total_yaks,
        yak_dir_label=yak_dir_label,
        sort_by=sort_by,
        current_category=current_category,
        categories=categories,
        current_route="yaks",
    )


def render_yak_edit(yak_path: str, content: str) -> HTMLResponse:
    """Render the yak editor page.

    Args:
        yak_path: Path of the yak being edited
        content: Current content of the yak

    Returns:
        HTMLResponse with the yak editor template
    """
    yak_name = SyncPath(yak_path).name
    return _render_template("yak/edit.html.jinja", yak_name=yak_name, yak_path=yak_path, content=content)
