"""Template rendering utilities."""

import hashlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from http import HTTPStatus
from pathlib import Path as SyncPath
from typing import TYPE_CHECKING, Any

from jinja2 import Environment, FileSystemLoader
from starlette.responses import HTMLResponse

from yak_shears._yak.categories import PALETTE, UNASSIGNED_COLOR

if TYPE_CHECKING:
    from yak_shears._yak.lists import ListInfo
    from yak_shears._yak.streams import StreamInfo, TaskInfo


class SortBy(StrEnum):
    """Enum for yak sorting options."""

    CREATED_AT = "created_at"
    MODIFIED_DATE = "modified_date"


class Recency(StrEnum):
    """How recently a yak was edited, as a lamp state rather than a duration."""

    LIVE = "live"
    RECENT = "recent"
    IDLE = "idle"
    COLD = "cold"


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
    recency: Recency
    tags: list[str]
    truncated: bool


@dataclass(frozen=True)
class SearchResult:
    """Search result for template rendering."""

    path: str
    line_num: int
    preview: str
    word: str
    first_line: str


TEMPLATE_DIR = SyncPath(__file__).parent
STATIC_DIR = TEMPLATE_DIR.parent / "static"

ENV = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=True,
)


_static_versions: dict[str, tuple[float, str]] = {}


def static_url(path: str) -> str:
    """Versioned URL for a static asset so edits and deploys bust browser caches.

    The token is a content hash, cached per file and refreshed when the file's
    mtime changes, so local edits bust immediately while production only changes
    the URL when the bytes change (letting the asset be cached long and hard).
    """
    asset = STATIC_DIR / path
    try:
        mtime = asset.stat().st_mtime
    except OSError:
        return f"/static/{path}"
    cached = _static_versions.get(path)
    if cached is None or cached[0] != mtime:
        token = hashlib.sha256(asset.read_bytes()).hexdigest()[:8]
        _static_versions[path] = (mtime, token)
    else:
        token = cached[1]
    return f"/static/{path}?v={token}"


ENV.globals["static_url"] = static_url


def color_lookup(colors: Mapping[str, str]) -> Callable[[str], str]:
    """Build the template's category-to-color accessor over a resolved mapping.

    Returns:
        A callable that maps a category name to a CSS color string.
    """

    def lookup(category: str) -> str:
        return colors.get(category, UNASSIGNED_COLOR)

    return lookup


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
    category_colors: Mapping[str, str],
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
        category_colors: resolved category to CSS color mapping

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
        get_category_color=color_lookup(category_colors),
        current_route="yaks",
    )


def render_new(*, categories: set[str], category_colors: Mapping[str, str]) -> HTMLResponse:
    """Render the new-yak page.

    Args:
        categories: set of categories a note can be filed under
        category_colors: resolved category to CSS color mapping

    Returns:
        HTMLResponse with the new yak template
    """
    return _render_template(
        "yak/new.html.jinja",
        categories=categories,
        get_category_color=color_lookup(category_colors),
        current_route="new",
    )


def render_yak_edit(
    yak_path: str,
    content: str,
    category: str,
    category_color: str,
    frontmatter: dict[str, Any] | None = None,
    backlinks: list[tuple[str, str]] | None = None,
) -> HTMLResponse:
    """Render the yak editor page.

    Args:
        yak_path: Path of the yak being edited
        content: Current content of the yak
        category: Category name
        category_color: CSS color assigned to the category
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
        category_color=category_color,
        frontmatter=frontmatter or {},
        backlinks=backlinks or [],
        current_route="edit",
    )


def render_settings(*, assignments: list[tuple[str, str]], owners: Mapping[str, list[str]], saved: bool) -> HTMLResponse:
    """Render the category color settings page.

    Args:
        assignments: (category, slot name) pairs in display order
        owners: slot name to the categories currently assigned to it
        saved: whether the page follows a successful save

    Returns:
        HTMLResponse with the settings template
    """
    return _render_template(
        "settings/index.html.jinja",
        assignments=assignments,
        palette=PALETTE,
        owners=owners,
        saved=saved,
        current_route="settings",
    )


def render_lists(*, lists: list["ListInfo"]) -> HTMLResponse:
    """Render the reference lists page.

    Returns:
        HTMLResponse with the lists template
    """
    return _render_template("yak/lists.html.jinja", lists=lists, current_route="lists")


def render_streams(
    *,
    streams: list["StreamInfo"],
    focused: "StreamInfo | None",
    triage: list["TaskInfo"],
    category_colors: Mapping[str, str],
) -> HTMLResponse:
    """Render the streams canal prototype.

    Returns:
        HTMLResponse with the streams template
    """
    return _render_template(
        "yak/streams.html.jinja",
        streams=streams,
        focused=focused,
        triage=triage,
        category_colors=category_colors,
        current_route="streams",
    )


def render_search(results: list[SearchResult], query: str) -> HTMLResponse:
    """Render the search results page.

    Args:
        results: List of search results
        query: The search query

    Returns:
        HTMLResponse with the search template
    """
    return _render_template("search/search.html.jinja", results=results, query=query, current_route="search")
