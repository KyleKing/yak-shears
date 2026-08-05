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

from yak_shears._yak.categories import UNASSIGNED_COLOR

if TYPE_CHECKING:
    from yak_shears._yak.habits import HabitInfo
    from yak_shears._yak.lists import ListInfo
    from yak_shears._yak.streams import StreamInfo, TaskInfo, UndoInfo


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
    kind: str
    last_modified: str
    link_count: int
    name: str
    open_ordinals: list[int]
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

# Generated wrappers import ENV from this module, so they must be imported below its
# definition to avoid a circular import against this still-initializing module.
from yak_shears._templates._generated.yak_shears._templates.auth.login_html_jinja import (  # noqa: E402
    render_login as render_auth_login,
)
from yak_shears._templates._generated.yak_shears._templates.error_html_jinja import (  # noqa: E402
    render_error as _render_error,
)
from yak_shears._templates._generated.yak_shears._templates.search.search_html_jinja import render_search  # noqa: E402
from yak_shears._templates._generated.yak_shears._templates.settings.index_html_jinja import (  # noqa: E402
    render_index as render_settings,
)
from yak_shears._templates._generated.yak_shears._templates.yak.edit_html_jinja import (  # noqa: E402
    render_edit as render_yak_edit,
)
from yak_shears._templates._generated.yak_shears._templates.yak.new_html_jinja import render_new  # noqa: E402
from yak_shears._templates._generated.yak_shears._templates.yaks.index_html_jinja import (  # noqa: E402
    render_index as render_yaks,
)


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


def render_error(message: str, status_code: HTTPStatus = HTTPStatus.BAD_REQUEST) -> HTMLResponse:
    """Render an error page with the given HTTP status."""
    response = _render_error(message=message)
    response.status_code = status_code
    return response


def render_benches(
    *,
    done_today: int,
    habits_count: int,
    in_progress_count: int,
    lists_count: int,
    open_items: int,
    streams_count: int,
    triage_count: int,
) -> HTMLResponse:
    """Render the benches hub.

    Returns:
        HTMLResponse with the benches template
    """
    return _render_template(
        "yak/benches.html.jinja",
        done_today=done_today,
        habits_count=habits_count,
        in_progress_count=in_progress_count,
        lists_count=lists_count,
        open_items=open_items,
        streams_count=streams_count,
        triage_count=triage_count,
        current_route="benches",
    )


def render_habits(*, habits: list["HabitInfo"]) -> HTMLResponse:
    """Render the habit bench.

    Returns:
        HTMLResponse with the habits template
    """
    return _render_template("yak/habits.html.jinja", habits=habits, current_route="habits")


def render_list_fragment(*, info: "ListInfo") -> HTMLResponse:
    """Render one list card for an HTMX swap.

    Returns:
        HTMLResponse with the list fragment template
    """
    return _render_template("yak/_list.html.jinja", info=info)


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
    undo: "UndoInfo | None" = None,
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
        undo=undo,
        current_route="streams",
    )


