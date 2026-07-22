"""Tests for the services module."""

import re
from unittest.mock import patch

import pytest

from yak_shears._templates import SortBy
from yak_shears._yak.services import (
    PREVIEW_MAX_LINES,
    PREVIEW_SOURCE_LIMIT,
    PaginationResult,
    YakPathError,
    _truncate_source,
    create_yak,
    delete_yak,
    get_categories,
    get_yak_dir,
    highlight_content,
    list_yak_paths,
    paginate_yaks,
    prepare_yak_info,
    read_yak,
    save_yak,
)


@pytest.fixture
def temp_yak_dir(tmp_path):
    """Create a temporary yak directory with categorized test files for service layer tests.

    Note: test_database.py has a similar fixture with different structure (flat files).
    These are intentionally separate to match their specific test requirements.
    """
    yak_dir = tmp_path / "yaks"
    yak_dir.mkdir()
    (yak_dir / "category1").mkdir()
    (yak_dir / "category2").mkdir()
    (yak_dir / "category1" / "file1.dj").write_text("content one")
    (yak_dir / "category1" / "file2.dj").write_text("content two")
    (yak_dir / "category2" / "file3.dj").write_text("content three")
    return yak_dir


class TestConfiguration:
    @pytest.mark.asyncio
    async def test_get_yak_dir_default(self, tmp_path):
        with patch.dict("os.environ", {"YAK_SHEARS_DIR": str(tmp_path)}, clear=True):
            result = await get_yak_dir()
            assert str(result) == str(tmp_path)

    @pytest.mark.asyncio
    async def test_get_yak_dir_expands_home(self):
        with patch.dict("os.environ", {}, clear=True):
            result = await get_yak_dir()
            assert "~" not in str(result)


class TestYakListing:
    @pytest.mark.asyncio
    async def test_list_yak_paths(self, temp_yak_dir):
        from anyio import Path

        paths = await list_yak_paths(Path(temp_yak_dir))
        assert len(paths) == 3
        names = {p.name for p in paths}
        assert names == {"file1.dj", "file2.dj", "file3.dj"}

    @pytest.mark.asyncio
    async def test_list_yak_paths_empty_dir(self, tmp_path):
        from anyio import Path

        paths = await list_yak_paths(Path(tmp_path))
        assert paths == []

    @pytest.mark.asyncio
    async def test_list_yak_paths_nonexistent(self, tmp_path):
        from anyio import Path

        paths = await list_yak_paths(Path(tmp_path / "nonexistent"))
        assert paths == []

    @pytest.mark.asyncio
    async def test_get_categories(self, temp_yak_dir):
        from anyio import Path

        paths = await list_yak_paths(Path(temp_yak_dir))
        categories = await get_categories(paths)
        assert categories == {"category1", "category2"}


class TestPagination:
    @pytest.mark.asyncio
    async def test_paginate_yaks_empty(self):
        result = await paginate_yaks([], page=1, page_size=10, sort_by=SortBy.CREATED_AT)
        assert result == PaginationResult(paths=[], total_count=0, total_pages=0)

    @pytest.mark.asyncio
    async def test_paginate_yaks_by_created_at(self, temp_yak_dir):
        from anyio import Path

        paths = await list_yak_paths(Path(temp_yak_dir))
        result = await paginate_yaks(paths, page=1, page_size=10, sort_by=SortBy.CREATED_AT)
        assert result.total_count == 3
        assert result.total_pages == 1
        assert len(result.paths) == 3

    @pytest.mark.asyncio
    async def test_paginate_yaks_by_modified_date(self, temp_yak_dir):
        from anyio import Path

        paths = await list_yak_paths(Path(temp_yak_dir))
        result = await paginate_yaks(paths, page=1, page_size=10, sort_by=SortBy.MODIFIED_DATE)
        assert result.total_count == 3
        assert len(result.paths) == 3

    @pytest.mark.asyncio
    async def test_paginate_yaks_with_category_filter(self, temp_yak_dir):
        from anyio import Path

        paths = await list_yak_paths(Path(temp_yak_dir))
        result = await paginate_yaks(paths, page=1, page_size=10, sort_by=SortBy.CREATED_AT, category="category1")
        assert result.total_count == 2
        assert all(p.parent.name == "category1" for p in result.paths)

    @pytest.mark.asyncio
    async def test_paginate_yaks_pagination(self, temp_yak_dir):
        from anyio import Path

        paths = await list_yak_paths(Path(temp_yak_dir))
        result = await paginate_yaks(paths, page=1, page_size=2, sort_by=SortBy.CREATED_AT)
        assert result.total_count == 3
        assert result.total_pages == 2
        assert len(result.paths) == 2

        result2 = await paginate_yaks(paths, page=2, page_size=2, sort_by=SortBy.CREATED_AT)
        assert len(result2.paths) == 1


class TestYakInfo:
    @pytest.mark.asyncio
    async def test_prepare_yak_info(self, temp_yak_dir):
        from anyio import Path

        yak_dir = Path(temp_yak_dir)
        paths = await list_yak_paths(yak_dir)
        infos = await prepare_yak_info(paths[:1], yak_dir)

        assert len(infos) == 1
        info = infos[0]
        assert info.name in {"file1.dj", "file2.dj", "file3.dj"}
        assert info.category in {"category1", "category2"}
        assert "content" in info.preview
        assert not info.truncated
        assert info.link_count >= 0


class TestLinkCount:
    def test_counts_urls_and_wikilinks(self) -> None:
        from yak_shears._yak.services import _count_links

        body = "See <https://example.com> and http://other.org plus [[a-note]] and [[b|B]]"
        assert _count_links(body) == 4

    def test_no_links(self) -> None:
        from yak_shears._yak.services import _count_links

        assert _count_links("plain text with no links") == 0


class TestPreviewTruncation:
    def test_short_body_is_untouched(self) -> None:
        body = "one\ntwo\nthree"
        clipped, truncated = _truncate_source(body, PREVIEW_SOURCE_LIMIT, PREVIEW_MAX_LINES)
        assert clipped == body
        assert not truncated

    def test_caps_line_count(self) -> None:
        body = "\n".join(str(n) for n in range(50))
        clipped, truncated = _truncate_source(body, PREVIEW_SOURCE_LIMIT, PREVIEW_MAX_LINES)
        assert truncated
        assert len(clipped.split("\n")) == PREVIEW_MAX_LINES

    def test_caps_char_count_at_line_boundary(self) -> None:
        body = "\n".join(["x" * 100] * 5)
        clipped, truncated = _truncate_source(body, 250, PREVIEW_MAX_LINES)
        assert truncated
        assert len(clipped) <= 250
        assert "\n" not in clipped[-1:]


class TestYakCRUD:
    @pytest.mark.asyncio
    async def test_create_yak(self, tmp_path):
        from anyio import Path

        yak_dir = Path(tmp_path)
        result = await create_yak(yak_dir, "new_category")

        assert result.parent.name == "new_category"
        assert result.suffix == ".dj"
        assert await result.exists()

    @pytest.mark.asyncio
    async def test_create_yak_filename_is_iso_utc(self, tmp_path):
        from anyio import Path

        yak_dir = Path(tmp_path)
        result = await create_yak(yak_dir, "new_category")

        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}_\d{2}_\d{2}Z\.dj", result.name)
        content, category = await read_yak(yak_dir, f"new_category/{result.name}")
        assert content == ""
        assert category == "new_category"

    @pytest.mark.asyncio
    async def test_read_yak(self, temp_yak_dir):
        from anyio import Path

        content, category = await read_yak(Path(temp_yak_dir), "category1/file1.dj")
        assert content == "content one"
        assert category == "category1"

    @pytest.mark.asyncio
    async def test_read_yak_not_found(self, temp_yak_dir):
        from anyio import Path

        with pytest.raises(FileNotFoundError):
            await read_yak(Path(temp_yak_dir), "nonexistent.dj")

    @pytest.mark.asyncio
    async def test_save_yak(self, temp_yak_dir):
        from anyio import Path

        yak_dir = Path(temp_yak_dir)
        db_dir = temp_yak_dir.parent / "db"
        db_dir.mkdir()

        with patch.dict("os.environ", {"SEARCH_DB_DIR": str(db_dir)}):
            from yak_shears._yak.database import init_search_db

            init_search_db()
            await save_yak(yak_dir, "category1/file1.dj", "updated content")

        content, _ = await read_yak(yak_dir, "category1/file1.dj")
        assert content == "updated content"

    @pytest.mark.asyncio
    async def test_save_preserves_export_metadata_verbatim(self, temp_yak_dir):
        """Saving must not reformat iCloud export metadata into YAML (no magic)."""
        from anyio import Path

        yak_dir = Path(temp_yak_dir)
        db_dir = temp_yak_dir.parent / "db"
        db_dir.mkdir()
        export = ": id=x-coredata://ABC/ICNote/p1\\\n: name=Sample\\\n\nBody line one\n"

        with patch.dict("os.environ", {"SEARCH_DB_DIR": str(db_dir)}):
            from yak_shears._yak.database import init_search_db

            init_search_db()
            await save_yak(yak_dir, "category1/file1.dj", export)

        content, _ = await read_yak(yak_dir, "category1/file1.dj")
        assert content == export

    @pytest.mark.asyncio
    async def test_delete_yak(self, temp_yak_dir):
        from anyio import Path

        yak_dir = Path(temp_yak_dir)
        await delete_yak(yak_dir, "category1/file1.dj")

        with pytest.raises(FileNotFoundError):
            await read_yak(yak_dir, "category1/file1.dj")

    @pytest.mark.asyncio
    async def test_delete_yak_not_found(self, temp_yak_dir):
        from anyio import Path

        with pytest.raises(FileNotFoundError):
            await delete_yak(Path(temp_yak_dir), "nonexistent.dj")


class TestPathSafety:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "unsafe_path",
        ["../outside.dj", "../../etc/passwd", "category1/../../outside.dj", "/etc/passwd", ""],
    )
    async def test_read_yak_rejects_traversal(self, temp_yak_dir, unsafe_path):
        from anyio import Path

        (temp_yak_dir.parent / "outside.dj").write_text("secret")
        with pytest.raises(YakPathError):
            await read_yak(Path(temp_yak_dir), unsafe_path)

    @pytest.mark.asyncio
    async def test_delete_yak_rejects_traversal(self, temp_yak_dir):
        from anyio import Path

        outside = temp_yak_dir.parent / "outside.dj"
        outside.write_text("secret")
        with pytest.raises(YakPathError):
            await delete_yak(Path(temp_yak_dir), "../outside.dj")
        assert outside.exists()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("unsafe_category", ["../evil", "a/b", "..", "with\x00null"])
    async def test_create_yak_rejects_unsafe_category(self, tmp_path, unsafe_category):
        from anyio import Path

        with pytest.raises(YakPathError):
            await create_yak(Path(tmp_path), unsafe_category)


class TestHighlighting:
    def test_highlight_content_no_query(self):
        result = highlight_content("hello world", "")
        assert result == "hello world"

    def test_highlight_content_single_match(self):
        result = highlight_content("hello world", "hello")
        assert '<span class="search-highlight">hello</span>' in result
        assert "world" in result

    def test_highlight_content_case_insensitive(self):
        result = highlight_content("Hello World", "hello")
        assert '<span class="search-highlight">Hello</span>' in result

    def test_highlight_content_multiple_words(self):
        result = highlight_content("hello beautiful world", "hello world")
        assert '<span class="search-highlight">hello</span>' in result
        assert '<span class="search-highlight">world</span>' in result

    def test_highlight_content_multiline(self):
        result = highlight_content("line one\nline two", "one")
        lines = result.split("\n")
        assert '<span class="search-highlight">one</span>' in lines[0]
        assert "two" in lines[1]

    def test_highlight_content_whitespace_only_query(self):
        """Test that query with only whitespace returns content unchanged."""
        result = highlight_content("hello world", "   ")
        assert result == "hello world"

    def test_highlight_content_empty_words_after_strip(self):
        """Test that empty words after stripping are handled."""
        result = highlight_content("hello world", " ")
        assert result == "hello world"


class TestServiceEdgeCases:
    """Test edge cases in service layer."""

    def test_ensure_search_index_handles_exceptions(self, tmp_path):
        """Test that ensure_search_index_updated handles exceptions gracefully."""
        from unittest.mock import patch

        from yak_shears._yak.services import ensure_search_index_updated

        yak_dir = tmp_path / "yaks"
        yak_dir.mkdir()

        with patch("yak_shears._yak.services.refresh_search_index", side_effect=RuntimeError("Test error")):
            # Should not raise, just log warning
            ensure_search_index_updated(yak_dir)

    def test_create_search_result_invalid_line_number(self, tmp_path):
        """Test that _create_search_result handles invalid line numbers."""
        from yak_shears._yak.services import _create_search_result

        test_file = tmp_path / "test.dj"
        test_file.write_text("line 1\nline 2\nline 3")

        # Line number out of range
        result = _create_search_result(test_file, "test.dj", 10, "test")
        assert result is None

        # Line number 0 (invalid)
        result = _create_search_result(test_file, "test.dj", 0, "test")
        assert result is None

    def test_process_search_results_deduplication(self, tmp_path):
        """Test that search results are deduplicated by path."""
        from yak_shears._yak.services import _process_search_results

        test_file = tmp_path / "test.dj"
        test_file.write_text("hello world test")

        # Multiple results for same file (should only return first)
        raw_results = [
            ("test.dj", 1, "hello"),
            ("test.dj", 1, "world"),  # Duplicate path, should be skipped
            ("test.dj", 1, "test"),  # Duplicate path, should be skipped
        ]

        results = _process_search_results(raw_results, tmp_path)
        # Should only have one result despite multiple matches
        assert len(results) == 1
        assert results[0].path == "test.dj"
