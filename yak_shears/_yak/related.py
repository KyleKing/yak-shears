"""Rank notes related to one note, with the reason each one is on the list.

Structural signals only: what two notes both link to, what tags they share, and
who cites them together. Nothing here is written back into a note.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path as SyncPath

LINK_WEIGHT = 3
TAG_WEIGHT = 2
COCITATION_WEIGHT = 2
RELATED_LIMIT = 8


@dataclass(frozen=True)
class Relation:
    """One related note and why it is related."""

    path: str
    title: str
    score: int
    reasons: list[str]


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def _target_index(paths: list[str]) -> dict[str, str]:
    """Map every name a wikilink may use (the path and its stem) onto the real path."""
    index: dict[str, str] = {}
    for path in paths:
        index[SyncPath(path).stem.lower()] = path
    index.update({path: path for path in paths})
    return index


def rank_related(
    path: str,
    edges: list[tuple[str, str, str]],
    titles: dict[str, str],
    limit: int = RELATED_LIMIT,
) -> list[Relation]:
    """Rank the notes closest to `path`, most related first.

    Args:
        path: The note being read, as a vault-relative path
        edges: Every (source path, target, link type) in the index
        titles: Indexed title per path
        limit: How many notes to return

    Returns:
        At most `limit` relations, each carrying the reasons it scored.
    """
    resolve = _target_index(list(titles))
    names = {path, SyncPath(path).stem.lower()}

    outbound: dict[str, set[str]] = defaultdict(set)
    tags: dict[str, set[str]] = defaultdict(set)
    for source, target, link_type in edges:
        bucket = tags if link_type == "tag" else outbound
        bucket[source].add(target.lower())

    mine, my_tags = outbound.get(path, set()), tags.get(path, set())
    shared_links = {other: len(targets & mine) for other, targets in outbound.items() if other != path}
    shared_tags = {other: len(found & my_tags) for other, found in tags.items() if other != path}

    cocited: Counter[str] = Counter()
    for source, targets in outbound.items():
        if source == path or not (targets & names):
            continue
        for target in targets - names:
            if resolved := resolve.get(target):
                cocited[resolved] += 1

    scored: list[Relation] = []
    for other in {*shared_links, *shared_tags, *cocited} - {path}:
        links, tagged, together = shared_links.get(other, 0), shared_tags.get(other, 0), cocited.get(other, 0)
        score = links * LINK_WEIGHT + tagged * TAG_WEIGHT + together * COCITATION_WEIGHT
        if not score:
            continue
        reasons = [
            *([f"{_plural(links, 'shared link')}"] if links else []),
            *([f"{_plural(tagged, 'shared tag')}"] if tagged else []),
            *([f"cited with it by {_plural(together, 'note')}"] if together else []),
        ]
        scored.append(Relation(path=other, title=titles.get(other, other), score=score, reasons=reasons))

    scored.sort(key=lambda relation: (-relation.score, relation.title))
    return scored[:limit]
