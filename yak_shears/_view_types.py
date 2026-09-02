"""View-model types shared by the service layer and template rendering."""

from dataclasses import dataclass
from enum import StrEnum


class SortBy(StrEnum):
    """Enum for yak sorting options."""

    CREATED_AT = "created_at"
    MODIFIED_DATE = "modified_date"


class Recency(StrEnum):
    """How recently a yak was edited, as a lamp state rather than a duration."""

    LIVE = "live"
    RECENT = "recent"
    IDLE = "idle"
    COLD = "cold"


@dataclass(frozen=True)
class YakInfo:
    """Yak information for template rendering."""

    backlink_count: int
    category: str
    kind: str
    last_modified: str
    link_count: int
    name: str
    open_ordinals: list[int]
    path: str
    preview: str
    recency: Recency
    tags: list[str]
    truncated: bool


@dataclass(frozen=True)
class SearchResult:
    """Search result for template rendering."""

    path: str
    line_num: int
    preview: str
    word: str
    first_line: str
