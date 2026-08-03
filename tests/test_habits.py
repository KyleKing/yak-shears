"""Streak and grace derivation for habits."""

from datetime import date, timedelta

from yak_shears._yak.habits import _toggle_today, derive_streak

TODAY = date(2026, 8, 3)


def _days(*offsets: int) -> set[date]:
    return {TODAY - timedelta(days=offset) for offset in offsets}


def test_daily_streak_counts_consecutive_days() -> None:
    streak, grace, unit = derive_streak("daily", _days(0, 1, 2), TODAY)
    assert streak == 3
    assert grace == 0
    assert unit == "d"


def test_daily_miss_breaks_streak_without_grace() -> None:
    streak, _, _ = derive_streak("daily", _days(0, 2, 3), TODAY)
    assert streak == 1


def test_today_not_yet_done_does_not_break_streak() -> None:
    streak, _, _ = derive_streak("daily", _days(1, 2, 3), TODAY)
    assert streak == 3


def test_weekday_habit_earns_grace_on_weekends() -> None:
    # 2026-08-01/02 are a weekend; completing them banks two grace days.
    completions = _days(0) | {date(2026, 8, 1), date(2026, 8, 2)}
    streak, grace, _ = derive_streak("weekdays", completions, TODAY)
    assert streak == 1
    assert grace == 2


def test_weekday_grace_covers_a_missed_day() -> None:
    # Friday 2026-07-31 missed, but the weekend earned grace before Monday.
    completions = {date(2026, 7, 29), date(2026, 7, 30), date(2026, 8, 1), TODAY}
    streak, grace, _ = derive_streak("weekdays", completions, TODAY)
    assert streak == 3
    assert grace == 0


def test_weekly_quota_and_surplus() -> None:
    # Two full weeks at quota 2, with one surplus completion banked.
    completions = {
        date(2026, 7, 20),
        date(2026, 7, 21),
        date(2026, 7, 22),
        date(2026, 7, 27),
        date(2026, 7, 28),
    }
    streak, grace, unit = derive_streak("2/week", completions, TODAY)
    assert streak >= 2
    assert grace == 1
    assert unit == "w"


def test_toggle_today_appends_then_retracts() -> None:
    content = "---\ntype: habit\n---\n\n# Stretch\n"
    marked = _toggle_today(content, TODAY)
    assert marked.endswith("- [x] 2026-08-03\n")
    assert _toggle_today(marked, TODAY) == content
