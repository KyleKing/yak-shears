"""Tests for the database module."""

from unittest.mock import patch

import pytest

from yak_shears._yak.database import (
    check_tables_exist,
    delete_files,
    get_backlinks,
    get_frontmatter,
    get_last_update_time,
    get_search_db_path,
    get_stored_files,
    get_word_count,
    init_search_db,
    insert_words,
    replace_links,
    search_words,
    set_last_update_time,
    should_update_index,
    update_index_batch,
    update_search_index,
    upsert_frontmatter,
)


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database for testing."""
    db_dir = tmp_path / "db"
    db_dir.mkdir()
    with patch.dict("os.environ", {"SEARCH_DB_DIR": str(db_dir)}):
        init_search_db()
        yield db_dir


@pytest.fixture
def temp_yak_dir(tmp_path):
    """Create a temporary yak directory with test files."""
    yak_dir = tmp_path / "yaks"
    yak_dir.mkdir()
    (yak_dir / "file1.dj").write_text("hello world\ntest content")
    (yak_dir / "file2.dj").write_text("another file\nwith words")
    (yak_dir / "subdir").mkdir()
    (yak_dir / "subdir" / "file3.dj").write_text("nested file content")
    return yak_dir


class TestDatabasePath:
    def test_get_search_db_path_default(self, tmp_path):
        with patch.dict("os.environ", {"YAK_SHEARS_DIR": str(tmp_path)}, clear=True):
            path = get_search_db_path()
            assert path == tmp_path / "yak_shears_search.db"

    def test_get_search_db_path_with_search_db_dir(self, tmp_path):
        db_dir = tmp_path / "custom_db"
        db_dir.mkdir()
        with patch.dict("os.environ", {"SEARCH_DB_DIR": str(db_dir)}):
            path = get_search_db_path()
            assert path == db_dir / "yak_shears_search.db"


class TestDatabaseInit:
    def test_init_search_db_creates_tables(self, temp_db):
        assert check_tables_exist()

    def test_check_tables_exist_false_when_no_db(self, tmp_path):
        db_dir = tmp_path / "empty"
        db_dir.mkdir()
        with patch.dict("os.environ", {"SEARCH_DB_DIR": str(db_dir)}):
            assert not check_tables_exist()


class TestMetadataOperations:
    def test_get_set_last_update_time(self, temp_db):
        assert get_last_update_time() == 0.0
        set_last_update_time(1234.5)
        assert get_last_update_time() == 1234.5


class TestFileTracking:
    def test_get_stored_files_empty(self, temp_db):
        assert get_stored_files() == {}

    def test_delete_files(self, temp_db):
        insert_words([("test.dj", 1, "hello")])
        update_index_batch([], [], [], {"test.dj": 100.0})
        assert "test.dj" in get_stored_files()

        delete_files(["test.dj"])
        assert "test.dj" not in get_stored_files()


class TestWordIndexing:
    def test_insert_and_search_words(self, temp_db):
        insert_words([
            ("file1.dj", 1, "hello"),
            ("file1.dj", 1, "world"),
            ("file2.dj", 2, "hello"),
        ])
        results = search_words("hello")
        assert len(results) >= 2
        assert all(word == "hello" for _, _, word in results)

    def test_get_word_count(self, temp_db):
        assert get_word_count() == 0
        insert_words([("file.dj", 1, "word1"), ("file.dj", 2, "word2")])
        assert get_word_count() == 2

    def test_search_words_fuzzy(self, temp_db):
        insert_words([("file.dj", 1, "testing")])
        results = search_words("testin")
        assert len(results) == 1


class TestFrontmatter:
    def test_upsert_and_get_frontmatter(self, temp_db):
        upsert_frontmatter("test.dj", {"title": "Test", "tags": ["a", "b"]})
        result = get_frontmatter("test.dj")
        assert result == {"title": "Test", "tags": ["a", "b"]}

    def test_get_frontmatter_not_found(self, temp_db):
        assert get_frontmatter("nonexistent.dj") == {}

    def test_upsert_frontmatter_empty_removes(self, temp_db):
        upsert_frontmatter("test.dj", {"title": "Test"})
        assert get_frontmatter("test.dj") == {"title": "Test"}
        upsert_frontmatter("test.dj", {})
        assert get_frontmatter("test.dj") == {}


class TestLinks:
    def test_replace_and_get_backlinks(self, temp_db):
        replace_links("source.dj", [("target.dj", "wikilink"), ("other", "tag")])
        backlinks = get_backlinks("target.dj")
        assert ("source.dj", "wikilink") in backlinks

    def test_backlinks_without_extension(self, temp_db):
        replace_links("source.dj", [("target", "wikilink")])
        backlinks = get_backlinks("target.dj")
        assert ("source.dj", "wikilink") in backlinks

    def test_replace_links_clears_old(self, temp_db):
        replace_links("source.dj", [("old.dj", "wikilink")])
        replace_links("source.dj", [("new.dj", "wikilink")])
        assert get_backlinks("old.dj") == []
        assert ("source.dj", "wikilink") in get_backlinks("new.dj")


class TestBatchUpdate:
    def test_update_index_batch(self, temp_db):
        insert_words([("old.dj", 1, "oldword")])
        update_index_batch([], [], [], {"old.dj": 100.0})

        update_index_batch(
            deleted_paths=["old.dj"],
            changed_paths=[],
            words_data=[("new.dj", 1, "newword")],
            file_mtimes={"new.dj": 200.0},
        )

        assert "old.dj" not in get_stored_files()
        assert "new.dj" in get_stored_files()
        assert get_word_count() == 1


class TestSearchIndex:
    def test_update_search_index(self, temp_db, temp_yak_dir):
        with patch.dict("os.environ", {"YAK_SHEARS_DIR": str(temp_yak_dir)}):
            update_search_index(temp_yak_dir)
            assert get_word_count() > 0
            stored = get_stored_files()
            assert "file1.dj" in stored
            assert "file2.dj" in stored
            assert "subdir/file3.dj" in stored

    def test_should_update_index_initially(self, temp_db, temp_yak_dir):
        with patch.dict("os.environ", {"YAK_SHEARS_DIR": str(temp_yak_dir)}):
            assert should_update_index(temp_yak_dir)

    def test_should_update_index_after_recent_update(self, temp_db, temp_yak_dir):
        with (
            patch.dict("os.environ", {"YAK_SHEARS_DIR": str(temp_yak_dir)}),
            patch("yak_shears._yak.database.time") as mock_time,
        ):
            mock_time.time.return_value = 1000.0
            update_search_index(temp_yak_dir)
            mock_time.time.return_value = 1030.0
            assert not should_update_index(temp_yak_dir)

    def test_should_update_index_after_file_change(self, temp_db, temp_yak_dir):
        with (
            patch.dict("os.environ", {"YAK_SHEARS_DIR": str(temp_yak_dir)}),
            patch("yak_shears._yak.database.time") as mock_time,
        ):
            mock_time.time.return_value = 1000.0
            update_search_index(temp_yak_dir)
            mock_time.time.return_value = 1100.0
            (temp_yak_dir / "file1.dj").write_text("modified content")
            assert should_update_index(temp_yak_dir)
