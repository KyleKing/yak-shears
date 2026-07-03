r"""Frontmatter parsing and manipulation for Djot files.

This module provides utilities for parsing YAML frontmatter from Djot files
and writing frontmatter back to files.

Example:
    >>> content = '''---
    ... title: My Note
    ... tags: [python, tutorial]
    ... ---
    ...
    ... Content goes here...
    ... '''
    >>> frontmatter, body = parse_frontmatter(content)
    >>> frontmatter
    {'title': 'My Note', 'tags': ['python, tutorial']}
    >>> body
    'Content goes here...\n'
"""

import re
from typing import Any

import yaml

# iCloud/Apple Notes export metadata lines look like `: name=value\` (the trailing
# backslash is a Djot hard break). A leading run of these lines is a metadata block.
_EXPORT_META_RE = re.compile(r"^: (?P<key>[^=\n]+)=(?P<value>.*)$")


def _parse_export_metadata(content: str) -> tuple[dict[str, Any], str] | None:
    """Parse an Apple Notes/iCloud export metadata block, if present.

    Returns None when the content does not begin with such a block so callers
    can fall back to other formats.
    """
    lines = content.splitlines(keepends=True)
    metadata: dict[str, Any] = {}
    consumed = 0
    for line in lines:
        match = _EXPORT_META_RE.match(line.rstrip("\n"))
        if not match:
            break
        value = match["value"].rstrip("\\").strip()
        metadata[match["key"].strip()] = value
        consumed += 1

    if not metadata:
        return None

    body = "".join(lines[consumed:]).lstrip("\n")
    return metadata, body


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Parse frontmatter from Djot file content.

    Args:
        content: The full content of a Djot file

    Returns:
        Tuple of (frontmatter_dict, body_content)
        - frontmatter_dict: Parsed metadata (empty dict if no frontmatter)
        - body_content: Content after frontmatter (or full content if no frontmatter)

    Note:
        Supports YAML frontmatter delimited by '---' as well as Apple Notes/iCloud
        export blocks whose lines start with ': '. Malformed YAML returns empty dict
        and full content.
    """
    if not content.startswith("---\n"):
        if export := _parse_export_metadata(content):
            return export
        return {}, content

    try:
        # Find the closing ---
        end_idx = content.index("\n---\n", 4)
        yaml_str = content[4:end_idx]
        body = content[end_idx + 5:]
        if body.startswith("\n"):
            body = body[1:]

        # Parse YAML
        frontmatter = yaml.safe_load(yaml_str)
        if frontmatter is None:
            frontmatter = {}
    except (ValueError, yaml.YAMLError):
        # If parsing fails, return empty frontmatter and full content
        return {}, content
    else:
        return frontmatter, body


def write_frontmatter(frontmatter: dict[str, Any], body: str) -> str:
    """Write frontmatter and body to a Djot file string.

    Args:
        frontmatter: Dictionary to serialize as YAML frontmatter
        body: Content to place after frontmatter

    Returns:
        Full Djot file content with frontmatter and body

    Note:
        If frontmatter is empty, returns only the body.
        YAML is written with unicode support and preserves key order.
    """
    if not frontmatter:
        return body

    yaml_str = yaml.dump(
        frontmatter,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )

    return f"---\n{yaml_str}---\n\n{body}"


def update_frontmatter(content: str, updates: dict[str, Any]) -> str:
    r"""Update frontmatter in Djot content with new values.

    Args:
        content: Original Djot file content
        updates: Dictionary of frontmatter fields to update/add

    Returns:
        Updated Djot file content

    Example:
        >>> content = "---\ntitle: Old\n---\n\nBody"
        >>> update_frontmatter(content, {"title": "New", "status": "done"})
        '---\ntitle: New\nstatus: done\n---\n\nBody'
    """
    frontmatter, body = parse_frontmatter(content)
    frontmatter.update(updates)
    return write_frontmatter(frontmatter, body)


def remove_frontmatter_field(content: str, *fields: str) -> str:
    r"""Remove specific fields from frontmatter.

    Args:
        content: Original Djot file content
        *fields: Field names to remove

    Returns:
        Updated Djot file content with fields removed

    Example:
        >>> content = "---\ntitle: Test\nstatus: done\n---\n\nBody"
        >>> remove_frontmatter_field(content, "status")
        '---\ntitle: Test\n---\n\nBody'
    """
    frontmatter, body = parse_frontmatter(content)
    for field in fields:
        frontmatter.pop(field, None)
    return write_frontmatter(frontmatter, body)
