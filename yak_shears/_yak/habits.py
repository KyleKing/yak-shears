"""Habits: `type: habit` notes with dated completions, streaks derived.

A habit note's body accumulates one `- [x] 2026-08-02` item per completion,
so history is plain text in the vault and every number here is a derived
view (STREAMS-DESIGN.md). Grace is earned, not granted: completing outside
the schedule banks a day (capped at GRACE_CAP), and a missed scheduled day
spends one before the streak breaks. A daily schedule has no off days to
earn from; that gap is a recorded open question.
"""

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta


from yak_shears.frontmatter import parse_frontmatter

from .services import (
    get_yak_dir,
    list_yak_paths,
    yak_lease,
)

GRACE_CAP = 7
HEAT_DAYS = 28
_COMPLETION_RE = re.compile(r"^\s*[-*+]\s+\[[xX]\]\s+(\d{4}-\d{2}-\d{2})\s*$")
_PER_WEEK_RE = re.compile(r"^(\d)/week$")
_LOOKBACK_DAYS = 365


@dataclass(frozen=True)
class HeatCell:
    """One day in the recent-history row."""

    day: str
    done: bool
    scheduled: bool


@dataclass(frozen=True)
class HabitInfo:
    """One habit and its derived streak state."""

    name: str
    path: str
    schedule: str
    streak: int
    streak_unit: str
    grace: int
    done_today: bool
    heat: list[HeatCell]
    lease: str


_SATURDAY = 5


def _scheduled(schedule: str, day: date) -> bool:
    if schedule == "weekdays":
        return day.weekday() < _SATURDAY
    return True


def _makeup_day(schedule: str, completions: set[date], consumed: set[date], miss: date, today: date) -> date | None:
    day = miss + timedelta(days=1)
    while day <= today and not _scheduled(schedule, day):
        if day in completions and day not in consumed:
            return day
        day += timedelta(days=1)
    return None


def _daily_streak(schedule: str, completions: set[date], today: date) -> tuple[int, int]:
    streak = 0
    grace = 0
    consumed: set[date] = set()
    start = min(completions) if completions else today
    start = max(start, today - timedelta(days=_LOOKBACK_DAYS))
    day = start
    while day <= today:
        done = day in completions
        if _scheduled(schedule, day):
            if done:
                streak += 1
            elif day < today:
                if grace > 0:
                    grace -= 1
                elif makeup := _makeup_day(schedule, completions, consumed, day, today):
                    consumed.add(makeup)
                else:
                    streak = 0
        elif done and day not in consumed:
            grace = min(GRACE_CAP, grace + 1)
        day += timedelta(days=1)
    return streak, grace


def _weekly_streak(quota: int, completions: set[date], today: date) -> tuple[int, int]:
    if not completions:
        return 0, 0
    streak = 0
    grace = 0
    start = max(min(completions), today - timedelta(days=_LOOKBACK_DAYS))
    week_start = start - timedelta(days=start.weekday())
    this_week = today - timedelta(days=today.weekday())
    while week_start <= this_week:
        week_days = {week_start + timedelta(days=offset) for offset in range(7)}
        count = len(week_days & completions)
        if count >= quota:
            streak += 1
            grace = min(GRACE_CAP, grace + (count - quota))
        elif week_start < this_week:
            if grace >= quota - count:
                grace -= quota - count
                streak += 1
            else:
                streak = 0
        week_start += timedelta(days=7)
    return streak, grace


def derive_streak(schedule: str, completions: set[date], today: date) -> tuple[int, int, str]:
    """Streak and banked grace for a habit.

    Returns:
        (streak, grace, unit) where unit is "d" for day schedules and "w"
        for n-per-week schedules.
    """
    if match := _PER_WEEK_RE.match(schedule):
        streak, grace = _weekly_streak(int(match[1]), completions, today)
        return streak, grace, "w"
    streak, grace = _daily_streak(schedule, completions, today)
    return streak, grace, "d"


def _heat(schedule: str, completions: set[date], today: date) -> list[HeatCell]:
    return [
        HeatCell(day=day.isoformat(), done=day in completions, scheduled=_scheduled(schedule, day))
        for offset in range(HEAT_DAYS - 1, -1, -1)
        for day in [today - timedelta(days=offset)]
    ]


async def collect_habits(today: date | None = None) -> list[HabitInfo]:
    """Scan the vault for `type: habit` notes.

    Returns:
        Habits ordered by name with derived streak, grace, and heat row.
    """
    today = today or datetime.now(tz=UTC).date()
    yak_dir = await get_yak_dir()
    habits = []
    for yak_path in sorted(await list_yak_paths(yak_dir), key=str):
        content = await yak_path.read_text()
        meta, body = parse_frontmatter(content)
        if meta.get("type") != "habit":
            continue
        rel_path = yak_path.relative_to(yak_dir).as_posix()
        schedule = str(meta.get("schedule") or "daily")
        completions = {
            date.fromisoformat(match[1]) for line in body.splitlines() if (match := _COMPLETION_RE.match(line))
        }
        streak, grace, unit = derive_streak(schedule, completions, today)
        habits.append(
            HabitInfo(
                name=str(meta.get("name") or rel_path),
                path=rel_path,
                schedule=schedule,
                streak=streak,
                streak_unit=unit,
                grace=grace,
                done_today=today in completions,
                heat=_heat(schedule, completions, today),
                lease=yak_lease(content),
            )
        )
    return sorted(habits, key=lambda info: info.name)


def toggle_today(content: str, today: date) -> str:
    line = f"- [x] {today.isoformat()}"
    lines = content.splitlines()
    without = [existing for existing in lines if existing.strip() != line]
    if len(without) != len(lines):
        return "\n".join(without) + ("\n" if content.endswith("\n") else "")
    ending = "" if content.endswith("\n") or not content else "\n"
    return f"{content}{ending}{line}\n"
