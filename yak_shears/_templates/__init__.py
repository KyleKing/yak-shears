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

    backlink_count: int
    category: str
    last_modified: str
    link_count: int
    name: str
    path: str
    preview: str
    tags: list[str]
    truncated: bool
    word_count: int


@dataclass(frozen=True)
class SearchResult:
    """Search result for template rendering."""

    path: str
    line_num: int
    preview: str
    word: str
    first_line: str


TEMPLATE_DIR = SyncPath(__file__).parent

ENV = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=True,
)


_HASH_MASK = 2**31
_SATURATIONS = (25, 30, 35, 40, 45)
_LIGHTNESSES = (55, 60, 65, 70, 75)


def get_category_color(category: str) -> str:
    """Deterministic muted color for a category name.

    Ports the djb2-based HSL scheme from the user's WezTerm config so tab and
    category colors stay consistent: full-spectrum hue with constrained
    saturation/lightness for muted, readable accents.

    Returns:
        A CSS ``hsl(...)`` color string.
    """
    if not category:
        return "var(--color-border)"

    hash_val = 5381
    for char in category:
        hash_val = ((hash_val * 33) + ord(char)) % _HASH_MASK
    hash_val = ((hash_val * 31337) + 12345) % _HASH_MASK

    hue = hash_val % 360
    saturation = _SATURATIONS[(hash_val // 360) % len(_SATURATIONS)]
    lightness = _LIGHTNESSES[(hash_val // 1800) % len(_LIGHTNESSES)]
    return f"hsl({hue}, {saturation}%, {lightness}%)"


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
        get_category_color=get_category_color,
        current_route="yaks",
    )


def render_yak_edit(
    yak_path: str,
    content: str,
    category: str,
    frontmatter: dict[str, Any] | None = None,
    backlinks: list[tuple[str, str]] | None = None,
) -> HTMLResponse:
    """Render the yak editor page.

    Args:
        yak_path: Path of the yak being edited
        content: Current content of the yak
        category: Category name
        frontmatter: Frontmatter metadata dictionary
        backlinks: List of (source_path, link_type) tuples

    Returns:
        HTMLResponse with the yak editor template
    """
    yak_name = SyncPath(yak_path).name
    return _render_template(
        "yak/edit.html.jinja",
        yak_name=yak_name,
        yak_path=yak_path,
        content=content,
        category=(category or "root").title(),
        category_color=get_category_color(category or ""),
        frontmatter=frontmatter or {},
        backlinks=backlinks or [],
    )


def render_yak_new(categories: set[str]) -> HTMLResponse:
    """Render the new yak creation page.

    Args:
        categories: Set of available categories

    Returns:
        HTMLResponse with the new yak template
    """
    return _render_template("yak/new.html.jinja", categories=categories, current_route="new")


def render_search(results: list[SearchResult], query: str) -> HTMLResponse:
    """Render the search results page.

    Args:
        results: List of search results
        query: The search query

    Returns:
        HTMLResponse with the search template
    """
    return _render_template("search/search.html.jinja", results=results, query=query, current_route="search")
