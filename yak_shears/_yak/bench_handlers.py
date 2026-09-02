"""HTTP handlers for the habit, list, and stream benches.

Kept apart from the modules that define their view models: the generated render
wrappers import those models at runtime, so a module that both defines one and
calls a wrapper closes an import cycle.
"""

import re
from collections.abc import Iterator
from datetime import UTC, datetime
from http import HTTPStatus
from urllib.parse import quote, urlencode

from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from yak_shears._templates import (
    render_error,
    render_habits,
    render_list_fragment,
    render_lists,
    render_streams,
)

from .board import BoardActionError, apply_action
from .categories import resolve_colors
from .habits import collect_habits, toggle_today
from .lists import collect_lists, toggle_item
from .request_utils import is_htmx_request
from .services import StaleYakError, YakPathError, get_yak_dir, read_leased, resolve_yak_path
from .streams import StreamInfo, TaskInfo, UndoInfo, collect_streams

# Only the actions inside the board grammar (and sane paths) may reach the undo toast.
_UNDO_ACTION_RE = re.compile(r"advance|lower|waiting|state:[a-z-]+|due:(?:clear|\d{4}-\d{2}-\d{2})|stream:[\w./-]+")


async def habits_handler(_request: Request) -> Response:
    """Handle requests to /habits.

    Returns:
        The rendered habit bench.
    """
    return render_habits(habits=await collect_habits())


async def habit_toggle_handler(request: Request) -> Response:
    """Record or retract today's completion for one habit.

    Returns:
        A redirect back to /habits, or an error page for a bad reference.
    """
    form = await request.form()
    rel_path = str(form.get("path", ""))
    yak_dir = await get_yak_dir()
    try:
        yak_path = await resolve_yak_path(yak_dir, rel_path)
    except YakPathError:
        return render_error("Invalid habit path")
    today = datetime.now(tz=UTC).date()
    try:
        content = await read_leased(yak_path, str(form.get("lease", "")) or None)
    except StaleYakError:
        return render_error(
            f"{rel_path} changed since this page loaded. Reload, then mark it again.", HTTPStatus.CONFLICT
        )
    await yak_path.write_text(toggle_today(content, today))
    return RedirectResponse("/habits", status_code=303)


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
        toggled = toggle_item(content, ordinal)
        if toggled is None:
            return render_error("Item not found; the note may have changed")
        content = toggled
    await yak_path.write_text(content)

    if is_htmx_request(request):
        refreshed = next((info for info in await collect_lists() if info.path == rel_path), None)
        if refreshed is not None:
            return render_list_fragment(info=refreshed)
    return RedirectResponse("/lists", status_code=303)


def _all_tasks(streams: list[StreamInfo], triage: list[TaskInfo]) -> Iterator[TaskInfo]:
    yield from triage
    for stream in streams:
        for reach in stream.reaches.values():
            yield from reach


async def streams_handler(request: Request) -> Response:
    """Handle requests to /streams.

    Returns:
        The rendered canal view for the focused stream.
    """
    streams, triage = await collect_streams()
    yak_dir = await get_yak_dir()
    category_colors = await resolve_colors(yak_dir, {stream.category for stream in streams})
    focused_key = request.query_params.get("stream", "")
    focused = next(
        (stream for stream in streams if stream.key == focused_key),
        max(streams, key=lambda stream: stream.wip, default=None),
    )
    undo = None
    undo_path = request.query_params.get("u_path", "")
    undo_action = request.query_params.get("u_action", "")
    if undo_path and ".." not in undo_path and _UNDO_ACTION_RE.fullmatch(undo_action):
        # The action that produced this toast just rewrote the file, so the lease has
        # to come from the read this render already did rather than from the redirect.
        undo_lease = next((task.lease for task in _all_tasks(streams, triage) if task.path == undo_path), "")
        undo = UndoInfo(
            path=undo_path,
            action=undo_action,
            reason=request.query_params.get("u_reason", ""),
            label=request.query_params.get("u_label", "undo"),
            lease=undo_lease,
        )
    return render_streams(
        streams=streams,
        focused=focused,
        triage=triage,
        category_colors=category_colors,
        undo=undo,
    )


async def board_act_handler(request: Request) -> Response:
    """Apply one command-deck action to a task note and redirect with undo.

    Returns:
        A 303 back to the focused canal carrying the inverse action, or an
        error page for a bad reference or inapplicable action.
    """
    form = await request.form()
    rel_path = str(form.get("path", ""))
    action = str(form.get("action", ""))
    reason = str(form.get("reason", "")).strip()
    focus = str(form.get("focus", ""))
    if action == "stream":
        action = f"stream:{form.get('to', '')}"

    yak_dir = await get_yak_dir()
    try:
        yak_path = await resolve_yak_path(yak_dir, rel_path)
    except YakPathError:
        return render_error("Invalid task path")

    if action.startswith("stream:") and action != "stream:clear":
        streams, _ = await collect_streams()
        if action.removeprefix("stream:") not in {stream.key for stream in streams}:
            return render_error("Unknown stream")

    # One form holds every strip on the canal, so the lease is keyed by path and the
    # latched radio picks which one applies.
    try:
        content = await read_leased(yak_path, str(form.get(f"lease:{rel_path}", "")) or None)
    except StaleYakError:
        return render_error(
            f"{rel_path} changed since this page loaded. Reload, then latch it again.", HTTPStatus.CONFLICT
        )
    try:
        result = apply_action(content, action, reason=reason, today=datetime.now(tz=UTC).date())
    except BoardActionError as err:
        return render_error(str(err))
    await yak_path.write_text(result.content)

    params = {"u_path": rel_path, "u_action": result.inverse, "u_label": result.label}
    if result.inverse_reason:
        params["u_reason"] = result.inverse_reason
    prefix = f"stream={quote(focus)}&" if focus else ""
    return RedirectResponse(f"/streams?{prefix}{urlencode(params)}", status_code=303)
