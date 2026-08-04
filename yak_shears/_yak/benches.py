"""Benches hub: one page linking each kind-specific surface with live counts."""

from starlette.requests import Request
from starlette.responses import Response

from yak_shears._templates import render_benches

from .habits import collect_habits
from .lists import collect_lists
from .streams import collect_streams


async def benches_handler(_request: Request) -> Response:
    """Handle requests to /benches.

    Returns:
        The rendered hub with per-kind counts.
    """
    streams, triage = await collect_streams()
    lists = await collect_lists()
    habits = await collect_habits()
    return render_benches(
        done_today=sum(1 for habit in habits if habit.done_today),
        habits_count=len(habits),
        in_progress_count=sum(len(stream.reaches["in-progress"]) for stream in streams),
        lists_count=len(lists),
        open_items=sum(info.open_count for info in lists),
        streams_count=len(streams),
        triage_count=len(triage),
    )
