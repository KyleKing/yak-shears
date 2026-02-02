"""Link detection and extraction for Djot files.

This module provides utilities for detecting wikilinks and tags in Djot content.

Example:
    >>> content = "See [[other-note]] and [[ref|Reference]] for details. #python #tutorial"
    >>> extract_wikilinks(content)
    [('other-note', 'other-note'), ('ref', 'Reference')]
    >>> extract_tags(content)
    ['python', 'tutorial']
"""

import re
from difflib import get_close_matches
from pathlib import Path

# Regex patterns
WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
TAG_RE = re.compile(r"(?:^|\s)#([a-zA-Z0-9_-]+)")


def extract_wikilinks(content: str) -> list[tuple[str, str]]:
    """Extract wikilinks from content.

    Args:
        content: Djot file content to search

    Returns:
        List of (target, alias) tuples
        - target: The link target (page name)
        - alias: Display text (same as target if no alias specified)

    Example:
        >>> extract_wikilinks("See [[page]] and [[other|Other Page]]")
        [('page', 'page'), ('other', 'Other Page')]
    """
    matches = []
    for match in WIKILINK_RE.finditer(content):
        target = match.group(1).strip()
        alias = match.group(2).strip() if match.group(2) else target
        matches.append((target, alias))
    return matches


def extract_tags(content: str) -> list[str]:
    """Extract hashtags from content.

    Args:
        content: Djot file content to search

    Returns:
        List of tag names (without #)

    Example:
        >>> extract_tags("This is #python and #django content")
        ['python', 'django']
    """
    return [match.group(1) for match in TAG_RE.finditer(content)]


def resolve_link(target: str, yak_dir: Path) -> Path | None:
    """Resolve a wikilink target to an actual file path.

    Args:
        target: The wikilink target (e.g., "my-note" from [[my-note]])
        yak_dir: Base directory containing Djot files

    Returns:
        Path to the resolved file, or None if not found

    Resolution strategy:
        1. Exact match: yak_dir/target.dj
        2. Recursive search: yak_dir/**/target.dj
        3. Fuzzy match: Similar file names (70% threshold)

    Example:
        >>> resolve_link("my-note", Path("/yaks"))
        Path("/yaks/category/my-note.dj")
    """
    target_lower = target.lower().replace(" ", "-")

    # 1. Try exact match
    exact = yak_dir / f"{target_lower}.dj"
    if exact.exists():
        return exact

    # 2. Try recursive search (exact stem match)
    for candidate in yak_dir.rglob("*.dj"):
        if candidate.stem.lower() == target_lower:
            return candidate

    # 3. Fuzzy match (70% similarity)
    all_yaks = list(yak_dir.rglob("*.dj"))
    all_names = [p.stem.lower() for p in all_yaks]
    matches = get_close_matches(target_lower, all_names, n=1, cutoff=0.7)

    if matches:
        idx = all_names.index(matches[0])
        return all_yaks[idx]

    return None


def extract_all_links(content: str) -> list[tuple[str, str]]:
    """Extract both wikilinks and tags as links.

    Args:
        content: Djot file content

    Returns:
        List of (target, link_type) tuples where link_type is 'wikilink' or 'tag'

    Example:
        >>> extract_all_links("See [[note]] #python")
        [('note', 'wikilink'), ('python', 'tag')]
    """
    links = []

    # Add wikilinks
    links.extend((target, "wikilink") for target, _ in extract_wikilinks(content))

    # Add tags
    links.extend((tag, "tag") for tag in extract_tags(content))

    return links
