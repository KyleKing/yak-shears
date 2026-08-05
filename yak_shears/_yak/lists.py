"""Reference lists: `type: list` notes rendered live with checkable items.

The quick-reference scene from STREAMS-DESIGN.md (groceries in the store).
Reading scans the vault directly; the only write is flipping one task item
marker in place, so files round-trip verbatim otherwise.
"""

import re
from dataclasses import dataclass, field
from http import HTTPStatus

from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from yak_shears._templates import render_error, render_list_fragment, render_lists
from yak_shears.frontmatter import parse_frontmatter

from .request_utils import is_htmx_request
from .services import (
    StaleYakError,
    YakPathError,
    get_yak_dir,
    list_yak_paths,
    read_leased,
    resolve_yak_path,
    yak_lease,
)

_ITEM_RE = re.compile(r"^(\s*[-*+]\s+)\[( |x|X)\]\s+(.*)$")


@dataclass(frozen=True)
class ListItem:
    """One checkable task item; ordinal is its index among the file's items."""

    ordinal: int
    checked: bool
    text: str


@dataclass(frozen=True)
class ListSection:
    """Items under one heading (or the unheaded lead)."""

    heading: str
    items: list[ListItem]


@dataclass(frozen=True)
class ListInfo:
    """One `type: list` note."""

    name: str
    path: str
    lease: str
    sections: list[ListSection] = field(default_factory=list)

    @property
    def open_count(self) -> int:
        return sum(1 for section in self.sections for item in section.items if not item.checked)


def _parse_sections(body: str) -> list[ListSection]:
    sections: list[ListSection] = []
    current = ListSection(heading="", items=[])
    ordinal = 0
    for line in body.splitlines():
        if line.startswith("#"):
            heading = line.lstrip("# ").strip()
            if current.items:
                sections.append(current)
            current = ListSection(heading=heading, items=[])
        elif match := _ITEM_RE.match(line):
            current.items.append(ListItem(ordinal=ordinal, checked=match[2] in "xX", text=match[3]))
            ordinal += 1
    if current.items:
        sections.append(current)
    return sections


async def collect_lists() -> list[ListInfo]:
    """Scan the vault for `type: list` notes.

    Returns:
        Lists ordered by name; a list's own title heading never counts as a
        section.
    """
    yak_dir = await get_yak_dir()
    lists = []
    for yak_path in sorted(await list_yak_paths(yak_dir), key=str):
        content = await yak_path.read_text()
        meta, body = parse_frontmatter(content)
        if meta.get("type") != "list":
            continue
        rel_path = yak_path.relative_to(yak_dir).as_posix()
        name = str(meta.get("name") or rel_path)
        sections = [section for section in _parse_sections(body) if section.items]
        lists.append(ListInfo(name=name, path=rel_path, lease=yak_lease(content), sections=sections))
    return sorted(lists, key=lambda info: info.name)


def _toggle_item(content: str, ordinal: int) -> str | None:
    lines = content.splitlines(keepends=True)
    seen = 0
    for index, line in enumerate(lines):
        match = _ITEM_RE.match(line.rstrip("\n"))
        if not match:
            continue
        if seen == ordinal:
            marker = " " if match[2] in "xX" else "x"
            newline = "\n" if line.endswith("\n") else ""
            lines[index] = f"{match[1]}[{marker}] {match[3]}{newline}"
            return "".join(lines)
        seen += 1
    return None


async def lists_handler(_request: Request) -> Response:
    """Handle requests to /lists.

    Returns:
        The rendered reference lists page.
    """
    return render_lists(lists=await collect_lists())


async def list_toggle_handler(request: Request) -> Response:
    """Toggle task items in a list note, identified by item ordinal.

    Accepts one or more ``ordinal`` fields so the rack's arm-and-apply key
    can commit a batch in a single write.

    Returns:
        A redirect back to /lists, or an error page for a bad reference.
    """
    form = await request.form()
    rel_path = str(form.get("path", ""))
    try:
        ordinals = [int(str(raw)) for raw in form.getlist("ordinal")]
    except ValueError:
        ordinals = []
    if not ordinals:
        return render_error("Missing or invalid item ordinal")

    yak_dir = await get_yak_dir()
    try:
        yak_path = await resolve_yak_path(yak_dir, rel_path)
    except YakPathError:
        return render_error("Invalid list path")
    try:
        content = await read_leased(yak_path, str(form.get("lease", "")) or None)
    except StaleYakError:
        return render_error(
            f"{rel_path} changed since this page loaded. Reload, then tick it again.", HTTPStatus.CONFLICT
        )
    for ordinal in ordinals:
        toggled = _toggle_item(content, ordinal)
        if toggled is None:
            return render_error("Item not found; the note may have changed")
        content = toggled
    await yak_path.write_text(content)

    if is_htmx_request(request):
        refreshed = next((info for info in await collect_lists() if info.path == rel_path), None)
        if refreshed is not None:
            return render_list_fragment(info=refreshed)
    return RedirectResponse("/lists", status_code=303)
