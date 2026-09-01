"""Query and aggregate notes by frontmatter, reading only the index (PLAN.md Phase 4).

Every view under Phases 5-6 is a query here, so no membership lives in the app:
a stream's tasks are whatever the vault currently says, rebuildable by a scan.

Filtering and grouping run in DuckDB over `yak_frontmatter`; field names travel
as bound JSON paths, never as SQL text. Sorting stays in Python because keys
like urgency are derived from the row rather than stored.
"""

import json
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path as SyncPath
from typing import Any, Protocol, runtime_checkable

from .database import get_search_db


@dataclass(frozen=True)
class Note:
    """One indexed note: its frontmatter plus what the file table knows."""

    path: str
    title: str
    modified: datetime
    meta: dict[str, Any]

    @property
    def category(self) -> str:
        parent = SyncPath(self.path).parent
        return "" if parent == SyncPath() else parent.name


@runtime_checkable
class Filter(Protocol):
    def clause(self) -> tuple[str, list[Any]]:
        """Return an SQL predicate and the parameters it binds."""
        ...


def _path(field: str) -> str:
    return f"$.{field}"


_VALUE = "json_extract_string(f.frontmatter_json, ?)"


@dataclass(frozen=True)
class Equals:
    field: str
    value: str

    def clause(self) -> tuple[str, list[Any]]:
        return f"{_VALUE} = ?", [_path(self.field), self.value]


@dataclass(frozen=True)
class OneOf:
    field: str
    values: Sequence[str]

    def clause(self) -> tuple[str, list[Any]]:
        if not self.values:
            return "FALSE", []
        placeholders = ",".join("?" for _ in self.values)
        return f"{_VALUE} IN ({placeholders})", [_path(self.field), *self.values]


@dataclass(frozen=True)
class Present:
    field: str

    def clause(self) -> tuple[str, list[Any]]:
        return f"{_VALUE} IS NOT NULL", [_path(self.field)]


@dataclass(frozen=True)
class Absent:
    field: str

    def clause(self) -> tuple[str, list[Any]]:
        return f"{_VALUE} IS NULL", [_path(self.field)]


@dataclass(frozen=True)
class DateWithin:
    """Field holds an ISO date no later than `days` from today (negative looks back)."""

    field: str
    days: int
    today: date | None = None

    def clause(self) -> tuple[str, list[Any]]:
        anchor = self.today or datetime.now(tz=UTC).date()
        cutoff = date.fromordinal(anchor.toordinal() + self.days)
        return f"TRY_CAST({_VALUE} AS DATE) <= ?", [_path(self.field), cutoff]


def _where(filters: Iterable[Filter]) -> tuple[str, list[Any]]:
    clauses, params = [], []
    for spec in filters:
        clause, values = spec.clause()
        clauses.append(f"({clause})")
        params.extend(values)
    return (" AND ".join(clauses) or "TRUE"), params


def select(*filters: Filter) -> list[Note]:
    """Return every indexed note matching all filters, ordered by path.

    Callers sort: `sort_notes` handles derived keys the store cannot hold.
    """
    predicate, params = _where(filters)
    with get_search_db() as con:
        rows = con.execute(
            f"""
            SELECT f.path, COALESCE(files.title, f.path), COALESCE(files.mtime, 0), f.frontmatter_json
            FROM yak_frontmatter f
            LEFT JOIN files ON files.path = f.path
            WHERE {predicate}
            ORDER BY f.path
            """,  # ruff: ignore[hardcoded-sql-expression] - predicate is built from bound placeholders only
            params,
        ).fetchall()
    return [
        Note(path=path, title=title, modified=datetime.fromtimestamp(mtime, tz=UTC), meta=json.loads(meta_json))
        for path, title, mtime, meta_json in rows
    ]


def group_counts(field: str, *filters: Filter) -> dict[str, int]:
    """Count matching notes per value of `field`, for the dock meters.

    Returns:
        Count per value, skipping notes where the field is absent.
    """
    predicate, params = _where(filters)
    with get_search_db() as con:
        rows = con.execute(
            f"""
            SELECT json_extract_string(f.frontmatter_json, ?) AS value, count(*)
            FROM yak_frontmatter f
            WHERE {predicate}
            GROUP BY value
            """,  # ruff: ignore[hardcoded-sql-expression] - predicate is built from bound placeholders only
            [_path(field), *params],
        ).fetchall()
    return {value: count for value, count in rows if value is not None}


def sort_notes(notes: Iterable[Note], *keys: Callable[[Note], Any]) -> list[Note]:
    """Sort by each key in turn, so the first key is the primary one.

    Returns:
        A new list; the input is not mutated.
    """
    ordered = list(notes)
    for key in reversed(keys):
        ordered.sort(key=key)
    return ordered
