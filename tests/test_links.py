"""Tests for link extraction."""

from pathlib import Path

from yak_shears.links import extract_all_links, extract_tags, extract_wikilinks, resolve_link


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
    # Nested brackets (should extract outer wikilink)
    content1 = "[[outer [[inner]]]]"
    links1 = extract_wikilinks(content1)
    # Should extract the outer wikilink "outer [[inner"
    assert len(links1) == 1
    assert links1[0][0] == "outer [[inner"

    # Empty wikilink
    content2 = "[[]]"
    links2 = extract_wikilinks(content2)
    # Empty wikilinks should be filtered out
    assert len(links2) == 0


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
    # Should not match since # is not preceded by space or line start
    assert len(tags3) == 0


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


class TestLinkResolution:
    """Tests for resolve_link functionality."""

    def test_resolve_link_exact_match(self, tmp_path: Path) -> None:
        """Test resolving a link with exact match in root directory."""
        yak_dir = tmp_path / "yaks"
        yak_dir.mkdir()
        test_file = yak_dir / "my-note.dj"
        test_file.write_text("content")

        result = resolve_link("my-note", yak_dir)
        assert result == test_file

    def test_resolve_link_recursive_search(self, tmp_path: Path) -> None:
        """Test resolving a link with recursive search in subdirectories."""
        yak_dir = tmp_path / "yaks"
        yak_dir.mkdir()
        category_dir = yak_dir / "category"
        category_dir.mkdir()
        test_file = category_dir / "nested-note.dj"
        test_file.write_text("content")

        result = resolve_link("nested-note", yak_dir)
        assert result == test_file

    def test_resolve_link_fuzzy_match(self, tmp_path: Path) -> None:
        """Test resolving a link with fuzzy matching."""
        yak_dir = tmp_path / "yaks"
        yak_dir.mkdir()
        test_file = yak_dir / "my-document.dj"
        test_file.write_text("content")

        # Fuzzy match with typo (70% similarity threshold)
        result = resolve_link("my-documnt", yak_dir)
        assert result == test_file

    def test_resolve_link_no_match_returns_none(self, tmp_path: Path) -> None:
        """Test that resolve_link returns None when no match is found."""
        yak_dir = tmp_path / "yaks"
        yak_dir.mkdir()
        (yak_dir / "other-note.dj").write_text("content")

        result = resolve_link("nonexistent-note", yak_dir)
        assert result is None

    def test_resolve_link_case_insensitive(self, tmp_path: Path) -> None:
        """Test that link resolution is case-insensitive."""
        yak_dir = tmp_path / "yaks"
        yak_dir.mkdir()
        test_file = yak_dir / "my-note.dj"
        test_file.write_text("content")

        result = resolve_link("MY-NOTE", yak_dir)
        assert result == test_file

    def test_resolve_link_space_to_dash_conversion(self, tmp_path: Path) -> None:
        """Test that spaces in target are converted to dashes."""
        yak_dir = tmp_path / "yaks"
        yak_dir.mkdir()
        test_file = yak_dir / "my-note.dj"
        test_file.write_text("content")

        result = resolve_link("my note", yak_dir)
        assert result == test_file

    def test_resolve_link_exact_match_priority_over_fuzzy(self, tmp_path: Path) -> None:
        """Test that exact match takes priority over fuzzy match."""
        yak_dir = tmp_path / "yaks"
        yak_dir.mkdir()
        exact_file = yak_dir / "note.dj"
        exact_file.write_text("exact")
        similar_file = yak_dir / "notes.dj"
        similar_file.write_text("similar")

        result = resolve_link("note", yak_dir)
        assert result == exact_file

    def test_resolve_link_recursive_priority_over_fuzzy(self, tmp_path: Path) -> None:
        """Test that recursive exact match takes priority over fuzzy match."""
        yak_dir = tmp_path / "yaks"
        yak_dir.mkdir()
        fuzzy_file = yak_dir / "my-document.dj"
        fuzzy_file.write_text("fuzzy")
        subdir = yak_dir / "category"
        subdir.mkdir()
        exact_file = subdir / "my-doc.dj"
        exact_file.write_text("exact")

        result = resolve_link("my-doc", yak_dir)
        assert result == exact_file
