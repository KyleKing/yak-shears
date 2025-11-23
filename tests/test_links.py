"""Tests for link extraction."""

from yak_shears.links import extract_all_links, extract_tags, extract_wikilinks


def test_extract_simple_wikilink() -> None:
    """Test extracting simple wikilinks."""
    content = "See [[other-note]] for details."
    links = extract_wikilinks(content)

    assert len(links) == 1
    assert links[0] == ("other-note", "other-note")


def test_extract_wikilink_with_alias() -> None:
    """Test extracting wikilinks with aliases."""
    content = "Check [[ref|Reference Document]] for more info."
    links = extract_wikilinks(content)

    assert len(links) == 1
    assert links[0] == ("ref", "Reference Document")


def test_extract_multiple_wikilinks() -> None:
    """Test extracting multiple wikilinks."""
    content = "See [[note-1]] and [[note-2|Note Two]] and [[note-3]]."
    links = extract_wikilinks(content)

    assert len(links) == 3
    assert ("note-1", "note-1") in links
    assert ("note-2", "Note Two") in links
    assert ("note-3", "note-3") in links


def test_extract_simple_tag() -> None:
    """Test extracting simple tags."""
    content = "This is a note about #python"
    tags = extract_tags(content)

    assert tags == ["python"]


def test_extract_multiple_tags() -> None:
    """Test extracting multiple tags."""
    content = "Technologies: #python #django #web-development"
    tags = extract_tags(content)

    assert len(tags) == 3
    assert "python" in tags
    assert "django" in tags
    assert "web-development" in tags


def test_extract_tags_with_underscores() -> None:
    """Test extracting tags with underscores."""
    content = "Topics: #machine_learning and #data_science"
    tags = extract_tags(content)

    assert "machine_learning" in tags
    assert "data_science" in tags


def test_extract_all_links_mixed() -> None:
    """Test extracting both wikilinks and tags."""
    content = "See [[architecture]] for #backend and #database design."
    links = extract_all_links(content)

    assert len(links) == 3
    assert ("architecture", "wikilink") in links
    assert ("backend", "tag") in links
    assert ("database", "tag") in links


def test_no_links_in_plain_text() -> None:
    """Test that plain text returns no links."""
    content = "This is plain text with no links or tags."
    wikilinks = extract_wikilinks(content)
    tags = extract_tags(content)

    assert wikilinks == []
    assert tags == []


def test_wikilink_edge_cases() -> None:
    """Test edge cases for wikilink extraction."""
    # Nested brackets (should not match)
    content1 = "[[outer [[inner]]]]"
    links1 = extract_wikilinks(content1)
    # Should extract what's parseable
    assert len(links1) > 0

    # Empty wikilink
    content2 = "[[]]"
    links2 = extract_wikilinks(content2)
    # Empty target should be filtered or handled
    assert all(target.strip() for target, _ in links2) or len(links2) == 0


def test_tag_edge_cases() -> None:
    """Test edge cases for tag extraction."""
    # Tag at start of line
    content1 = "#start-tag\nSome content"
    tags1 = extract_tags(content1)
    assert "start-tag" in tags1

    # Tag after space
    content2 = "Word #tag here"
    tags2 = extract_tags(content2)
    assert "tag" in tags2

    # Not a tag (no space before #)
    content3 = "HTML color#ff0000"
    tags3 = extract_tags(content3)
    # Should not match since # is not preceded by space or start
    assert "ff0000" not in tags3 or len(tags3) == 0


def test_unicode_in_links() -> None:
    """Test Unicode characters in link targets."""
    # Unicode in wikilinks
    content1 = "[[日本語]]"
    links1 = extract_wikilinks(content1)
    # May or may not work depending on regex, but shouldn't crash
    assert isinstance(links1, list)

    # ASCII tags only (current implementation)
    content2 = "#テスト"
    tags2 = extract_tags(content2)
    # Current regex only matches ASCII, so this should not match
    assert len(tags2) == 0


def test_complex_document() -> None:
    """Test extraction from a complex document."""
    content = """---
title: Test Document
tags: [meta, test]
---

# Project Overview

This project uses [[architecture-design]] for the backend.
See also [[api-docs|API Documentation]] for details.

Technologies: #python #django #postgresql

Related pages:
- [[setup-guide]]
- [[troubleshooting|Common Issues]]

Tags: #backend #api #database
"""

    wikilinks = extract_wikilinks(content)
    tags = extract_tags(content)

    # Should find 4 wikilinks
    assert len(wikilinks) == 4
    assert ("architecture-design", "architecture-design") in wikilinks
    assert ("api-docs", "API Documentation") in wikilinks

    # Should find 6 tags
    assert len(tags) == 6
    assert "python" in tags
    assert "django" in tags
    assert "postgresql" in tags
    assert "backend" in tags
