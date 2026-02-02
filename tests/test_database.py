"""Tests for the database module."""

from unittest.mock import patch

import pytest
from freezegun import freeze_time

from yak_shears._yak.database import (
    MAX_WORD_LENGTH,
    check_tables_exist,
    delete_files,
    delete_words_for_paths,
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
    upsert_file,
    upsert_frontmatter,
)


@pytest.fixture
def temp_db(tmp_path, worker_id):
    """Create a temporary database for testing.

    Uses worker-specific directory for parallel test isolation.
    """
    db_dir = tmp_path / "db" / worker_id
    db_dir.mkdir(parents=True)
    with patch.dict("os.environ", {"SEARCH_DB_DIR": str(db_dir)}):
        init_search_db()
        yield db_dir


@pytest.fixture
def temp_yak_dir(tmp_path):
    """Create a temporary yak directory with test files for database indexing tests.

    Note: test_services.py has a similar fixture with different structure (categorized files).
    These are intentionally separate to match their specific test requirements.
    """
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
        assert len(results) == 2
        assert all(word == "hello" for _, _, word in results)
        # Verify both files are in results
        file_paths = {file_path for file_path, _, _ in results}
        assert file_paths == {"file1.dj", "file2.dj"}

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
            freeze_time("2025-01-01 00:00:00") as frozen_time,
        ):
            update_search_index(temp_yak_dir)
            frozen_time.move_to("2025-01-01 00:00:30")
            assert not should_update_index(temp_yak_dir)

    def test_should_update_index_after_file_change(self, temp_db, temp_yak_dir):
        with (
            patch.dict("os.environ", {"YAK_SHEARS_DIR": str(temp_yak_dir)}),
            freeze_time("2025-01-01 00:00:00") as frozen_time,
        ):
            update_search_index(temp_yak_dir)
            frozen_time.move_to("2025-01-01 00:01:40")
            (temp_yak_dir / "file1.dj").write_text("modified content")
            assert should_update_index(temp_yak_dir)

    def test_should_update_index_detects_deleted_files(self, temp_db, temp_yak_dir):
        """Test that should_update_index detects when files are deleted."""
        with (
            patch.dict("os.environ", {"YAK_SHEARS_DIR": str(temp_yak_dir)}),
            freeze_time("2025-01-01 00:00:00") as frozen_time,
        ):
            # Initial index
            update_search_index(temp_yak_dir)
            frozen_time.move_to("2025-01-01 00:02:00")  # Move past update threshold

            # Delete a file
            (temp_yak_dir / "file1.dj").unlink()

            # Should detect missing file
            assert should_update_index(temp_yak_dir)


class TestDatabaseEdgeCases:
    """Test edge cases and error handling in database operations."""

    def test_delete_files_empty_list(self, temp_db):
        """Test that delete_files handles empty list gracefully."""
        delete_files([])
        # Should not raise error

    def test_delete_words_for_paths_empty_list(self, temp_db):
        """Test that delete_words_for_paths handles empty list gracefully."""
        delete_words_for_paths([])
        # Should not raise error

    def test_insert_words_empty_list(self, temp_db):
        """Test that insert_words handles empty list gracefully."""
        insert_words([])
        assert get_word_count() == 0

    def test_upsert_file_basic(self, temp_db):
        """Test upserting file metadata."""
        upsert_file("test.dj", 123.456)
        stored = get_stored_files()
        assert "test.dj" in stored
        assert abs(stored["test.dj"] - 123.456) < 0.01  # Float precision tolerance

        # Update with new mtime
        upsert_file("test.dj", 789.012)
        stored = get_stored_files()
        assert abs(stored["test.dj"] - 789.012) < 0.01  # Float precision tolerance

    def test_process_file_with_very_long_words(self, temp_db, tmp_path):
        """Test that very long words are truncated to MAX_WORD_LENGTH."""
        yak_dir = tmp_path / "yaks"
        yak_dir.mkdir()
        long_word = "a" * (MAX_WORD_LENGTH + 50)
        (yak_dir / "file1.dj").write_text(f"short {long_word} normal")

        with patch.dict("os.environ", {"YAK_SHEARS_DIR": str(yak_dir)}):
            update_search_index(yak_dir)

        # Search for truncated word
        results = search_words("a" * MAX_WORD_LENGTH)
        assert len(results) > 0

    def test_process_file_unreadable_encoding(self, temp_db, tmp_path):
        """Test that unreadable files are skipped gracefully."""
        yak_dir = tmp_path / "yaks"
        yak_dir.mkdir()
        # Create a file with valid content
        good_file = yak_dir / "good.dj"
        good_file.write_text("readable content")
        # Create a file with binary content (will cause read error)
        bad_file = yak_dir / "bad.dj"
        bad_file.write_bytes(b"\x80\x81\x82\x83")

        with patch.dict("os.environ", {"YAK_SHEARS_DIR": str(yak_dir)}):
            # Should not raise, just skip bad file
            update_search_index(yak_dir)

        # Good file should still be indexed
        stored = get_stored_files()
        assert "good.dj" in stored

    def test_update_index_batch_with_transaction(self, temp_db):
        """Test that update_index_batch uses transactions."""
        # Add initial data
        insert_words([("old.dj", 1, "oldword")])
        update_index_batch([], [], [], {"old.dj": 100.0})
        assert get_word_count() == 1

        # Update in batch
        update_index_batch(
            deleted_paths=["old.dj"],
            changed_paths=[],
            words_data=[
                ("new1.dj", 1, "word1"),
                ("new2.dj", 1, "word2"),
            ],
            file_mtimes={"new1.dj": 200.0, "new2.dj": 300.0},
        )

        assert get_word_count() == 2
        stored = get_stored_files()
        assert "old.dj" not in stored
        assert "new1.dj" in stored
        assert "new2.dj" in stored
