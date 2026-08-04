"""Board writes: line-level frontmatter rewrites and their inverses."""

from datetime import date

import pytest

from yak_shears._yak.board import BoardActionError, apply_action
from yak_shears.frontmatter import parse_frontmatter, rewrite_frontmatter_field

TODAY = date(2026, 8, 4)

TASK = """---
type: task
state: queue
stream: work/tlr-migration
due: 2026-08-09
flex: 3
---

# Ship the importer

Body stays verbatim.
"""


def test_rewrite_replaces_only_the_field_line() -> None:
    updated = rewrite_frontmatter_field(TASK, "state", "in-progress")
    assert "state: in-progress\n" in updated
    assert updated.replace("state: in-progress", "state: queue") == TASK


def test_rewrite_inserts_missing_field_before_closing_delimiter() -> None:
    updated = rewrite_frontmatter_field(TASK, "waiting", "code review")
    assert "flex: 3\nwaiting: code review\n---\n" in updated


def test_rewrite_removes_field() -> None:
    updated = rewrite_frontmatter_field(TASK, "due", None)
    assert "due:" not in updated
    restored = rewrite_frontmatter_field(updated, "due", "2026-08-09")
    assert parse_frontmatter(restored) == parse_frontmatter(TASK)


def test_rewrite_quotes_unsafe_scalars() -> None:
    updated = rewrite_frontmatter_field(TASK, "waiting", "vendor: reply, then #retest")
    assert 'waiting: "vendor: reply, then #retest"\n' in updated


def test_rewrite_creates_frontmatter_when_absent() -> None:
    updated = rewrite_frontmatter_field("# Bare note\n", "state", "backlog")
    assert updated == "---\nstate: backlog\n---\n\n# Bare note\n"


def test_rewrite_consumes_block_list_values() -> None:
    content = '---\nblocked-by:\n  - "[[a]]"\n  - "[[b]]"\nstate: queue\n---\n\nBody\n'
    updated = rewrite_frontmatter_field(content, "blocked-by", None)
    assert updated == "---\nstate: queue\n---\n\nBody\n"


def test_advance_crosses_one_sill() -> None:
    result = apply_action(TASK, "advance", today=TODAY)
    assert "state: in-progress" in result.content
    assert result.inverse == "state:queue"


def test_advance_past_complete_refuses() -> None:
    drained = rewrite_frontmatter_field(TASK, "state", "complete")
    with pytest.raises(BoardActionError):
        apply_action(drained, "advance", today=TODAY)


def test_lower_refuses_at_backlog() -> None:
    bottom = rewrite_frontmatter_field(TASK, "state", "backlog")
    with pytest.raises(BoardActionError):
        apply_action(bottom, "lower", today=TODAY)


def test_due_shift_is_relative_to_current_due() -> None:
    result = apply_action(TASK, "due:+7d", today=TODAY)
    assert "due: 2026-08-16" in result.content
    assert result.inverse == "due:2026-08-09"


def test_due_shift_without_due_starts_from_today() -> None:
    undated = rewrite_frontmatter_field(TASK, "due", None)
    result = apply_action(undated, "due:+1d", today=TODAY)
    assert "due: 2026-08-05" in result.content
    assert result.inverse == "due:clear"


def test_waiting_toggles_and_carries_the_reason_back() -> None:
    closed = apply_action(TASK, "waiting", reason="vendor reply", today=TODAY)
    assert "waiting: vendor reply" in closed.content
    reopened = apply_action(closed.content, "waiting", today=TODAY)
    assert reopened.inverse_reason == "vendor reply"
    assert reopened.content == TASK


def test_unknown_action_and_state_refuse() -> None:
    with pytest.raises(BoardActionError):
        apply_action(TASK, "sideways", today=TODAY)
    with pytest.raises(BoardActionError):
        apply_action(TASK, "state:paused", today=TODAY)


@pytest.mark.parametrize(
    "action",
    [
        "advance",
        "lower",
        "state:not-planned",
        "due:today",
        "due:+7d",
        "due:clear",
        "waiting",
        "stream:home/errands",
        "stream:clear",
    ],
)
def test_every_action_round_trips_through_its_inverse(action: str) -> None:
    result = apply_action(TASK, action, reason="vendor reply", today=TODAY)
    restored = apply_action(result.content, result.inverse, reason=result.inverse_reason, today=TODAY)
    if action.endswith("clear"):
        assert parse_frontmatter(restored.content) == parse_frontmatter(TASK)
    else:
        assert restored.content == TASK
