"""Tests for frontmatter parsing."""

from yak_shears.frontmatter import (
    parse_frontmatter,
    remove_frontmatter_field,
    update_frontmatter,
    write_frontmatter,
)


def test_parse_empty_frontmatter() -> None:
    """Test parsing content with no frontmatter."""
    content = "Just some content\nwith no frontmatter"
    frontmatter, body = parse_frontmatter(content)

    assert frontmatter == {}
    assert body == content


def test_parse_valid_frontmatter() -> None:
    """Test parsing valid YAML frontmatter."""
    content = """---
title: My Note
tags: [python, tutorial]
status: draft
---

Body content here"""

    frontmatter, body = parse_frontmatter(content)

    assert frontmatter == {
        "title": "My Note",
        "tags": ["python", "tutorial"],
        "status": "draft",
    }
    assert body == "Body content here"


def test_parse_malformed_frontmatter() -> None:
    """Test parsing malformed YAML returns empty dict."""
    content = """---
invalid: yaml: content: here
---

Body"""

    frontmatter, body = parse_frontmatter(content)

    # Malformed YAML should return empty frontmatter and full content
    assert frontmatter == {}
    assert body == content


def test_write_frontmatter() -> None:
    """Test writing frontmatter to content."""
    frontmatter = {"title": "Test", "status": "done"}
    body = "Content here"

    result = write_frontmatter(frontmatter, body)

    assert result.startswith("---\n")
    assert "title: Test" in result
    assert "status: done" in result
    assert result.endswith("Content here")


def test_write_empty_frontmatter() -> None:
    """Test writing empty frontmatter returns just body."""
    result = write_frontmatter({}, "Just content")
    assert result == "Just content"


def test_round_trip() -> None:
    """Test parsing and writing preserves data."""
    original = """---
title: Round Trip Test
count: 42
---

Body content"""

    frontmatter, body = parse_frontmatter(original)
    reconstructed = write_frontmatter(frontmatter, body)

    # Parse again to verify
    frontmatter2, body2 = parse_frontmatter(reconstructed)

    assert frontmatter == frontmatter2
    assert body == body2


def test_update_frontmatter() -> None:
    """Test updating frontmatter fields."""
    content = """---
title: Old Title
status: draft
---

Body"""

    result = update_frontmatter(content, {"title": "New Title", "priority": "high"})

    frontmatter, _ = parse_frontmatter(result)
    assert frontmatter["title"] == "New Title"
    assert frontmatter["status"] == "draft"
    assert frontmatter["priority"] == "high"


def test_remove_frontmatter_field() -> None:
    """Test removing frontmatter fields."""
    content = """---
title: Test
status: done
priority: low
---

Body"""

    result = remove_frontmatter_field(content, "status", "priority")

    frontmatter, body = parse_frontmatter(result)
    assert frontmatter == {"title": "Test"}
    assert body == "Body"


def test_unicode_support() -> None:
    """Test Unicode characters in frontmatter."""
    content = """---
title: テスト
emoji: 🎉
---

Content"""

    frontmatter, body = parse_frontmatter(content)
    assert frontmatter["title"] == "テスト"
    assert frontmatter["emoji"] == "🎉"

    # Round-trip
    result = write_frontmatter(frontmatter, body)
    frontmatter2, _ = parse_frontmatter(result)
    assert frontmatter == frontmatter2


def test_parse_empty_yaml_frontmatter() -> None:
    """Test parsing frontmatter with empty YAML section."""
    content = """---
---

Body content"""

    frontmatter, body = parse_frontmatter(content)

    # Empty YAML is treated as malformed, returns full content
    assert frontmatter == {}
    assert body == content


def test_parse_whitespace_only_frontmatter() -> None:
    """Test parsing frontmatter with only whitespace in YAML section."""
    content = """---

---

Body content"""

    frontmatter, body = parse_frontmatter(content)

    # Whitespace-only YAML is parsed as None by YAML, which becomes empty dict
    assert frontmatter == {}
    assert body == "Body content"


def test_parse_icloud_export_metadata() -> None:
    """Apple Notes/iCloud export metadata block is parsed and stripped from body."""
    content = (
        ": id=x-coredata://ABCD/ICNote/p1\\\n"
        ": creation_date=2025-01-01T09:30:48\\\n"
        ": name=Dog Sheep\\\n"
        ": folder=Notes\\\n"
        "\n"
        "````` =html\n"
        "<div><h1>Dog Sheep</h1></div>\n"
    )

    frontmatter, body = parse_frontmatter(content)

    assert frontmatter == {
        "id": "x-coredata://ABCD/ICNote/p1",
        "creation_date": "2025-01-01T09:30:48",
        "name": "Dog Sheep",
        "folder": "Notes",
    }
    assert body.startswith("````` =html")
    assert ": id=" not in body


def test_parse_icloud_export_value_with_equals() -> None:
    """Values containing '=' are preserved after the first delimiter."""
    frontmatter, _ = parse_frontmatter(": query=a=b=c\\\n\nBody")
    assert frontmatter == {"query": "a=b=c"}


def test_colon_line_not_metadata_is_left_alone() -> None:
    """A leading ': ' line without '=' is not treated as export metadata."""
    content = ": just a note line\nmore body"
    frontmatter, body = parse_frontmatter(content)
    assert frontmatter == {}
    assert body == content
