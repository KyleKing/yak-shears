"""Template rendering utilities."""

import hashlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from http import HTTPStatus
from pathlib import Path as SyncPath

from jinja2 import Environment, FileSystemLoader
from starlette.responses import HTMLResponse

from yak_shears._yak.categories import UNASSIGNED_COLOR


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
from yak_shears._templates._generated.yak_shears._templates.doctor.index_html_jinja import (  # noqa: E402
    render_index as render_doctor,
)
from yak_shears._templates._generated.yak_shears._templates.error_html_jinja import (  # noqa: E402
    render_error as _render_error,
)
from yak_shears._templates._generated.yak_shears._templates.search.search_html_jinja import render_search  # noqa: E402
from yak_shears._templates._generated.yak_shears._templates.search.search_results_html_jinja import (  # noqa: E402
    render_search_results,
)
from yak_shears._templates._generated.yak_shears._templates.settings.index_html_jinja import (  # noqa: E402
    render_index as render_settings,
)
from yak_shears._templates._generated.yak_shears._templates.yak._list_html_jinja import (  # noqa: E402
    render_list as render_list_fragment,
)
from yak_shears._templates._generated.yak_shears._templates.yak.benches_html_jinja import render_benches  # noqa: E402
from yak_shears._templates._generated.yak_shears._templates.yak.edit_html_jinja import (  # noqa: E402
    render_edit as render_yak_edit,
)
from yak_shears._templates._generated.yak_shears._templates.yak.habits_html_jinja import render_habits  # noqa: E402
from yak_shears._templates._generated.yak_shears._templates.yak.lists_html_jinja import render_lists  # noqa: E402
from yak_shears._templates._generated.yak_shears._templates.yak.new_html_jinja import render_new  # noqa: E402
from yak_shears._templates._generated.yak_shears._templates.yak.streams_html_jinja import render_streams  # noqa: E402
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


def render_error(message: str, status_code: HTTPStatus = HTTPStatus.BAD_REQUEST) -> HTMLResponse:
    """Render an error page with the given HTTP status."""
    response = _render_error(message=message)
    response.status_code = status_code
    return response


# Under mypy's strict no-implicit-reexport, a generated wrapper imported under a
# different name is not re-exported by that import alone, so every caller of one
# reads as an unknown attribute.
__all__ = (
    "ENV",
    "Recency",
    "SearchResult",
    "SortBy",
    "YakInfo",
    "color_lookup",
    "render_auth_login",
    "render_benches",
    "render_doctor",
    "render_error",
    "render_habits",
    "render_list_fragment",
    "render_lists",
    "render_new",
    "render_search",
    "render_search_results",
    "render_settings",
    "render_streams",
    "render_yak_edit",
    "render_yaks",
    "static_url",
)
