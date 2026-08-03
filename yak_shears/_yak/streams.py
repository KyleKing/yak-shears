"""Read-only /streams prototype over vault frontmatter (STREAMS-DESIGN.md).

Throwaway proof of the canal view: scans the vault directly instead of the
Phase 4 query engine, and writes nothing.
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from starlette.requests import Request
from starlette.responses import Response

from yak_shears._templates import render_streams
from yak_shears.frontmatter import parse_frontmatter

from .categories import resolve_colors, slot_css
from .services import get_yak_dir, list_yak_paths

CANAL_STATES = ("in-progress", "queue", "backlog")
DRAIN_STATES = ("complete", "not-planned")
TASK_STATES = frozenset(CANAL_STATES) | frozenset(DRAIN_STATES)


@dataclass(frozen=True)
class TaskInfo:
    """One task-note strip."""

    title: str
    path: str
    state: str
    due: str
    flex: int
    urgency: str
    waiting: str


@dataclass
class StreamInfo:
    """One stream note plus its member tasks grouped by state."""

    key: str
    name: str
    category: str
    color: str
    wip_limit: int
    reaches: dict[str, list[TaskInfo]] = field(default_factory=lambda: {state: [] for state in CANAL_STATES})
    drained: int = 0

    @property
    def wip(self) -> int:
        return len(self.reaches["in-progress"])

    @property
    def over_wip(self) -> bool:
        return 0 < self.wip_limit < self.wip


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            return None
    return None


def _urgency(due: date | None, flex: int, today: date) -> str:
    if due is None:
        return ""
    if (due - today).days + flex < 0:
        return "overdue"
    if (due - today).days <= flex:
        return "pressing"
    return "scheduled"


def _task_info(meta: dict[str, Any], body: str, path: str, today: date) -> TaskInfo:
    title = next((line.lstrip("# ").strip() for line in body.splitlines() if line.strip()), path)
    due = _as_date(meta.get("due"))
    flex = int(meta.get("flex") or 0)
    return TaskInfo(
        title=title,
        path=path,
        state=str(meta.get("state", "")),
        due=due.isoformat() if due else "",
        flex=flex,
        urgency=_urgency(due, flex, today),
        waiting=str(meta.get("waiting") or ""),
    )


async def collect_streams(today: date | None = None) -> tuple[list[StreamInfo], list[TaskInfo]]:
    """Scan the vault once for stream and task notes.

    Returns:
        Streams ordered by category then name, and the triage list of tasks
        whose stream is missing or unknown.
    """
    today = today or datetime.now(tz=UTC).date()
    yak_dir = await get_yak_dir()
    streams: dict[str, StreamInfo] = {}
    tasks: list[tuple[str, TaskInfo]] = []
    categories: set[str] = set()

    for yak_path in sorted(await list_yak_paths(yak_dir), key=str):
        meta, body = parse_frontmatter(await yak_path.read_text())
        rel_path = yak_path.relative_to(yak_dir).as_posix()
        category = yak_path.parent.name if yak_path.parent != yak_dir else ""
        categories.add(category)
        if meta.get("type") == "stream" and meta.get("id"):
            key = f"{category}/{meta['id']}"
            streams[key] = StreamInfo(
                key=key,
                name=str(meta.get("name") or meta["id"]),
                category=category,
                color=str(meta.get("color") or ""),
                wip_limit=int(meta.get("wip-limit") or 0),
            )
        elif str(meta.get("state", "")) in TASK_STATES:
            tasks.append((str(meta.get("stream") or ""), _task_info(meta, body, rel_path, today)))

    triage: list[TaskInfo] = []
    for stream_key, task in tasks:
        stream = streams.get(stream_key)
        if stream is None:
            triage.append(task)
        elif task.state in CANAL_STATES:
            stream.reaches[task.state].append(task)
        else:
            stream.drained += 1

    category_colors = await resolve_colors(yak_dir, categories)
    for stream in streams.values():
        stream.color = slot_css(stream.color) if stream.color else category_colors.get(stream.category, "")
        for reach in stream.reaches.values():
            reach.sort(key=lambda task: (task.due or "9999", task.path))

    ordered = sorted(streams.values(), key=lambda stream: (stream.category, stream.name))
    return ordered, triage


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
    return render_streams(
        streams=streams,
        focused=focused,
        triage=triage,
        category_colors=category_colors,
    )
