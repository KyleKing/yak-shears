"""Board writes for /streams: the command grammar over task frontmatter.

Every action rewrites only the frontmatter lines it touches and computes its
own inverse, so the response can carry a one-press undo (STREAMS-DESIGN.md).
"""

import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from yak_shears.frontmatter import parse_frontmatter, rewrite_frontmatter_field

from .streams import CANAL_STATES, TASK_STATES


_RAISE = {"backlog": "queue", "queue": "in-progress", "in-progress": "complete"}
_LOWER = {new: old for old, new in _RAISE.items()}
_SHIFT_RE = re.compile(r"([+-]\d+)d")


class BoardActionError(Exception):
    """An action that cannot apply to the note as it stands."""


@dataclass(frozen=True)
class ActionResult:
    """One applied write plus the action that reverses it."""

    content: str
    inverse: str
    inverse_reason: str
    label: str


def _shift_due(current: str, operand: str, today: date) -> str:
    try:
        return date.fromisoformat(operand).isoformat()
    except ValueError:
        pass
    if operand == "today":
        return today.isoformat()
    if operand == "tomorrow":
        return (today + timedelta(days=1)).isoformat()
    if match := _SHIFT_RE.fullmatch(operand):
        try:
            base = date.fromisoformat(current) if current else today
        except ValueError:
            base = today
        return (base + timedelta(days=int(match[1]))).isoformat()
    msg = f"Unknown due operand: {operand}"
    raise BoardActionError(msg)


def _set_state(content: str, new_state: str, old_state: str) -> ActionResult:
    if new_state not in TASK_STATES:
        msg = f"Unknown state: {new_state}"
        raise BoardActionError(msg)
    return ActionResult(
        content=rewrite_frontmatter_field(content, "state", new_state),
        inverse=f"state:{old_state}",
        inverse_reason="",
        label=f"state → {new_state}",
    )


def _apply_gate(content: str, action: str, state: str) -> ActionResult:
    if action == "advance":
        if state not in _RAISE:
            msg = f"Cannot raise from {state}"
            raise BoardActionError(msg)
        return _set_state(content, _RAISE[state], state)
    if state not in _LOWER or _LOWER[state] not in CANAL_STATES:
        msg = f"Cannot lower from {state}"
        raise BoardActionError(msg)
    return _set_state(content, _LOWER[state], state)


def _apply_due(content: str, meta: dict[str, Any], operand: str, today: date) -> ActionResult:
    raw_due = meta.get("due")
    current = raw_due.isoformat() if isinstance(raw_due, date) else str(raw_due or "")
    inverse = f"due:{current}" if current else "due:clear"
    if operand == "clear":
        if not current:
            raise BoardActionError("No due date to clear")
        return ActionResult(
            content=rewrite_frontmatter_field(content, "due", None),
            inverse=inverse,
            inverse_reason="",
            label="due cleared",
        )
    new_due = _shift_due(current, operand, today)
    return ActionResult(
        content=rewrite_frontmatter_field(content, "due", new_due),
        inverse=inverse,
        inverse_reason="",
        label=f"due → {new_due}",
    )


def _apply_waiting(content: str, meta: dict[str, Any], reason: str) -> ActionResult:
    current_reason = str(meta.get("waiting") or "")
    if current_reason:
        return ActionResult(
            content=rewrite_frontmatter_field(content, "waiting", None),
            inverse="waiting",
            inverse_reason=current_reason,
            label="gate reopened",
        )
    return ActionResult(
        content=rewrite_frontmatter_field(content, "waiting", reason or "external"),
        inverse="waiting",
        inverse_reason="",
        label=f"waiting: {reason or 'external'}",
    )


def _apply_stream(content: str, meta: dict[str, Any], target: str) -> ActionResult:
    current_stream = str(meta.get("stream") or "")
    inverse = f"stream:{current_stream}" if current_stream else "stream:clear"
    if target == "clear":
        if not current_stream:
            raise BoardActionError("No stream to clear")
        return ActionResult(
            content=rewrite_frontmatter_field(content, "stream", None),
            inverse=inverse,
            inverse_reason="",
            label="stream cleared",
        )
    return ActionResult(
        content=rewrite_frontmatter_field(content, "stream", target),
        inverse=inverse,
        inverse_reason="",
        label=f"stream → {target}",
    )


def apply_action(content: str, action: str, *, reason: str = "", today: date) -> ActionResult:
    """Apply one board action to a note's content.

    Actions: ``advance``, ``lower``, ``state:<name>``, ``due:<operand>``
    (today, tomorrow, clear, +Nd, -Nd, an ISO date), ``waiting`` (toggle,
    ``reason`` names the gate), and ``stream:<category/id or clear>``.

    Returns:
        The rewritten content, the inverse action, and a toast label.

    Raises:
        BoardActionError: When the action or operand does not apply.
    """
    meta, _ = parse_frontmatter(content)
    state = str(meta.get("state") or "backlog")

    if action in {"advance", "lower"}:
        return _apply_gate(content, action, state)
    if action.startswith("state:"):
        return _set_state(content, action.removeprefix("state:"), state)
    if action.startswith("due:"):
        return _apply_due(content, meta, action.removeprefix("due:"), today)
    if action == "waiting":
        return _apply_waiting(content, meta, reason)
    if action.startswith("stream:"):
        return _apply_stream(content, meta, action.removeprefix("stream:"))
    msg = f"Unknown action: {action}"
    raise BoardActionError(msg)
