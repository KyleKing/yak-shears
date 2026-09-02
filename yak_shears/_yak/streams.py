"""Read-only /streams canal view over the frontmatter index (STREAMS-DESIGN.md).

Reads nothing but the store, so a task's stream is whatever the vault currently
says. The index is refreshed first because each strip publishes a lease, and a
lease older than the file would have its write refused as stale.
"""

import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from functools import partial
from pathlib import Path as SyncPath
from typing import Any

from anyio import to_thread

from yak_shears._view_types import Recency

from .categories import resolve_colors, slot_css
from .database import refresh_search_index
from .query import Note, Present, select
from .services import ensure_search_db_ready, get_yak_dir

CANAL_STATES = ("in-progress", "queue", "backlog")
DRAIN_STATES = ("complete", "not-planned")
TASK_STATES = frozenset(CANAL_STATES) | frozenset(DRAIN_STATES)


_RECENCY_DAYS = ((7, Recency.LIVE), (30, Recency.RECENT), (365, Recency.IDLE))

# The undo toast renders a one-press write form from query params, so only
# actions inside the board grammar (and sane paths) may reach it.
_UNDO_ACTION_RE = re.compile(r"advance|lower|waiting|state:[a-z-]+|due:(?:clear|\d{4}-\d{2}-\d{2})|stream:[\w./-]+")


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
    relations: int
    recency: Recency
    lease: str


@dataclass(frozen=True)
class UndoInfo:
    """The inverse of the last board write, rendered as the undo toast."""

    path: str
    action: str
    reason: str
    label: str
    lease: str


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


def _list_len(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    return 1 if value else 0


def _task_info(note: Note, today: date) -> TaskInfo:
    meta = note.meta
    due = _as_date(meta.get("due"))
    flex = int(meta.get("flex") or 0)
    age = (datetime.now(tz=UTC) - note.modified).days
    return TaskInfo(
        title=note.title,
        path=note.path,
        state=str(meta.get("state") or "backlog"),
        due=due.isoformat() if due else "",
        flex=flex,
        urgency=_urgency(due, flex, today),
        waiting=str(meta.get("waiting") or ""),
        relations=_list_len(meta.get("blocked-by")) + _list_len(meta.get("relates")),
        recency=next((state for limit, state in _RECENCY_DAYS if age < limit), Recency.COLD),
        lease=note.lease,
    )


def _board_notes() -> list[Note]:
    """Every note that can appear on the board, by path.

    A task is typed as one or carries a board state, so both queries run and
    merge rather than pushing an OR the filter grammar does not have.

    Returns:
        Stream and task notes, ordered by path.
    """
    notes = {note.path: note for note in select(Present("type"))}
    notes.update({note.path: note for note in select(Present("state"))})
    return [notes[path] for path in sorted(notes)]


async def collect_streams(today: date | None = None) -> tuple[list[StreamInfo], list[TaskInfo]]:
    """Read the index once for stream and task notes.

    Returns:
        Streams ordered by category then name, and the triage list of tasks
        whose stream is missing or unknown.
    """
    today = today or datetime.now(tz=UTC).date()
    yak_dir = await get_yak_dir()
    await ensure_search_db_ready()
    await to_thread.run_sync(partial(refresh_search_index, SyncPath(yak_dir), force=True))

    streams: dict[str, StreamInfo] = {}
    tasks: list[tuple[str, TaskInfo]] = []
    categories: set[str] = set()

    for note in await to_thread.run_sync(_board_notes):
        meta = note.meta
        categories.add(note.category)
        if meta.get("type") == "stream" and meta.get("id"):
            key = f"{note.category}/{meta['id']}"
            streams[key] = StreamInfo(
                key=key,
                name=str(meta.get("name") or meta["id"]),
                category=note.category,
                color=str(meta.get("color") or ""),
                wip_limit=int(meta.get("wip-limit") or 0),
            )
        elif meta.get("type") == "task" or str(meta.get("state", "")) in TASK_STATES:
            tasks.append((str(meta.get("stream") or ""), _task_info(note, today)))

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
