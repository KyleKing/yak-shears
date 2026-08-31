"""Tests for the database module."""

from unittest.mock import patch

import duckdb
import pytest
from freezegun import freeze_time

from yak_shears._yak.database import (
    CHEAP_SEARCH_TARGET_ROWS,
    MAX_WORD_LENGTH,
    apply_vault_scan,
    check_tables_exist,
    close_search_db,
    delete_files,
    delete_words_for_paths,
    get_backlinks,
    get_file_titles,
    get_frontmatter,
    get_last_update_time,
    get_search_db_path,
    get_stored_files,
    get_word_count,
    index_is_inside_vault,
    init_search_db,
    insert_words,
    refresh_search_index,
    replace_links,
    scan_vault,
    search_link_candidates,
    search_words,
    set_last_update_time,
    should_update_index,
    stray_vault_index,
    update_index_batch,
    update_search_index,
    upsert_file,
    upsert_frontmatter,
)
from yak_shears.links import extract_all_links


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
        close_search_db()


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
    def test_get_search_db_path_defaults_outside_the_vault(self, tmp_path):
        state_home = tmp_path / "state"
        env = {"YAK_SHEARS_DIR": str(tmp_path / "vault"), "XDG_STATE_HOME": str(state_home)}
        with patch.dict("os.environ", env, clear=True):
            path = get_search_db_path()

        # The index must not land in the synced vault (ADR 0010).
        assert path == state_home / "yak-shears" / "yak_shears_search.db"
        assert (tmp_path / "vault") not in path.parents

    def test_index_is_inside_vault_flags_a_legacy_override(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        with patch.dict("os.environ", {"YAK_SHEARS_DIR": str(vault), "SEARCH_DB_DIR": str(vault)}, clear=True):
            assert index_is_inside_vault()

    def test_index_is_not_inside_vault_by_default(self, tmp_path):
        env = {"YAK_SHEARS_DIR": str(tmp_path / "vault"), "XDG_STATE_HOME": str(tmp_path / "state")}
        with patch.dict("os.environ", env, clear=True):
            assert not index_is_inside_vault()

    def test_stray_vault_index_reports_a_leftover_file(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "yak_shears_search.db").write_bytes(b"leftover")
        env = {"YAK_SHEARS_DIR": str(vault), "XDG_STATE_HOME": str(tmp_path / "state")}
        with patch.dict("os.environ", env, clear=True):
            assert stray_vault_index() == vault / "yak_shears_search.db"

    def test_no_stray_when_the_vault_is_clean(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        env = {"YAK_SHEARS_DIR": str(vault), "XDG_STATE_HOME": str(tmp_path / "state")}
        with patch.dict("os.environ", env, clear=True):
            assert stray_vault_index() is None

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

    def test_repeated_links_survive_the_primary_key(self, temp_db):
        content = "See [[target]] then [[target]] again. #topic and more #topic"
        replace_links("source.dj", extract_all_links(content))
        assert ("source.dj", "wikilink") in get_backlinks("target.dj")
        assert ("source.dj", "tag") in get_backlinks("topic")

    def test_replace_links_clears_old(self, temp_db):
        replace_links("source.dj", [("old.dj", "wikilink")])
        replace_links("source.dj", [("new.dj", "wikilink")])
        assert get_backlinks("old.dj") == []
        assert ("source.dj", "wikilink") in get_backlinks("new.dj")


class TestLinkCandidates:
    @staticmethod
    def _seed():
        upsert_file("notes/kettlebell-swing.dj", 100.0, "Kettlebell swing")
        upsert_file("notes/kettle-corn.dj", 300.0, "Kettle corn")
        upsert_file("notes/unrelated.dj", 400.0, "Something about kettles")
        replace_links("notes/a.dj", [("notes/kettlebell-swing.dj", "wikilink")])
        replace_links("notes/b.dj", [("notes/kettlebell-swing.dj", "wikilink")])

    def test_prefix_beats_recency_and_inbound_breaks_the_tie(self, temp_db):
        self._seed()
        ranked = [c.target for c in search_link_candidates("kettle")]
        assert ranked[:2] == ["kettlebell-swing", "kettle-corn"], ranked
        assert "unrelated" in ranked

    def test_empty_query_lists_the_most_recent_first(self, temp_db):
        self._seed()
        assert [c.target for c in search_link_candidates("")][0] == "unrelated"

    def test_the_note_being_edited_is_never_offered(self, temp_db):
        self._seed()
        targets = [c.target for c in search_link_candidates("kettle", exclude="notes/kettle-corn.dj")]
        assert "kettle-corn" not in targets


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

    def test_scanning_the_vault_indexes_links_not_only_words(self, temp_db, temp_yak_dir):
        """A note arriving over Syncthing is never saved through the app, so the scan is
        the only chance to record what it links to."""
        (temp_yak_dir / "file1.dj").write_text("hello [[file2]] world #tagged")
        with patch.dict("os.environ", {"YAK_SHEARS_DIR": str(temp_yak_dir)}):
            update_search_index(temp_yak_dir)

        assert ("file1.dj", "wikilink") in get_backlinks("file2.dj")

        (temp_yak_dir / "file1.dj").write_text("hello world")
        with patch.dict("os.environ", {"YAK_SHEARS_DIR": str(temp_yak_dir)}):
            update_search_index(temp_yak_dir)

        assert get_backlinks("file2.dj") == []

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


class TestSearchTiers:
    """Exact and prefix queries must resolve without the Levenshtein scan."""

    @pytest.fixture
    def indexed_words(self, temp_db):
        insert_words([
            ("file1.dj", 1, "banana"),
            ("file1.dj", 2, "bandana"),
            ("file2.dj", 1, "band"),
            ("file2.dj", 2, "unrelated"),
        ])
        return temp_db

    @pytest.mark.parametrize(
        ("query", "expected_words"),
        [
            ("banana", {"banana", "bandana"}),
            ("BANANA", {"banana", "bandana"}),
            ("band", {"band", "bandana"}),
            ("banna", {"banana"}),
            ("unrelted", {"unrelated"}),
            ("zzzzzzzz", set()),
        ],
    )
    def test_search_words_tiers(self, indexed_words, query, expected_words):
        results = search_words(query)
        assert {word for _, _, word in results} == expected_words

    def test_search_words_skips_fuzzy_when_prefix_is_enough(self, temp_db):
        insert_words([("file.dj", line, f"prefix{line}") for line in range(1, CHEAP_SEARCH_TARGET_ROWS + 5)])
        results = search_words("prefix")
        assert len(results) == CHEAP_SEARCH_TARGET_ROWS + 4


class TestSchemaMigration:
    def test_init_search_db_adds_title_column(self, tmp_path, worker_id):
        db_dir = tmp_path / "legacy" / worker_id
        db_dir.mkdir(parents=True)
        legacy = duckdb.connect(str(db_dir / "yak_shears_search.db"))
        legacy.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)")
        legacy.execute("CREATE TABLE files (path TEXT PRIMARY KEY, mtime REAL)")
        legacy.execute(
            "CREATE TABLE words (path TEXT, line_num INTEGER, word TEXT, PRIMARY KEY (path, line_num, word))"
        )
        legacy.execute("INSERT INTO files VALUES ('old.dj', 1.0)")
        legacy.execute("INSERT INTO words VALUES ('old.dj', 1, 'legacy')")
        legacy.close()

        with patch.dict("os.environ", {"SEARCH_DB_DIR": str(db_dir)}):
            init_search_db()
            init_search_db()

            assert get_stored_files() == {"old.dj": 1.0}
            assert get_file_titles(["old.dj"]) == {}
            assert [word for _, _, word in search_words("legacy")] == ["legacy"]

            upsert_file("old.dj", 2.0, "Legacy Title")
            assert get_file_titles(["old.dj"]) == {"old.dj": "Legacy Title"}


class TestVaultScan:
    @pytest.mark.parametrize("change", ["add", "modify", "delete"])
    def test_scan_reflects_vault_changes(self, temp_db, temp_yak_dir, change):
        update_search_index(temp_yak_dir)

        expected_changed: list[str]
        expected_deleted: list[str]
        match change:
            case "add":
                (temp_yak_dir / "file4.dj").write_text("brand new")
                expected_changed, expected_deleted = ["file4.dj"], []
            case "modify":
                (temp_yak_dir / "file1.dj").write_text("changed content")
                expected_changed, expected_deleted = ["file1.dj"], []
            case _:
                (temp_yak_dir / "file2.dj").unlink()
                expected_changed, expected_deleted = [], ["file2.dj"]

        scan = scan_vault(temp_yak_dir)
        assert scan.changed_paths == expected_changed
        assert scan.deleted_paths == expected_deleted
        assert scan.has_changes

        apply_vault_scan(temp_yak_dir, scan)
        assert not scan_vault(temp_yak_dir).has_changes
        assert set(get_stored_files()) == set(scan.file_mtimes)

    def test_index_stores_derived_titles(self, temp_db, tmp_path):
        yak_dir = tmp_path / "titled"
        yak_dir.mkdir()
        (yak_dir / "heading.dj").write_text("# My Heading\nbody text")
        (yak_dir / "frontmatter.dj").write_text("---\ntitle: From Frontmatter\n---\nbody text")
        (yak_dir / "empty.dj").write_text("")

        update_search_index(yak_dir)

        assert get_file_titles(["heading.dj", "frontmatter.dj", "empty.dj"]) == {
            "heading.dj": "My Heading",
            "frontmatter.dj": "From Frontmatter",
            "empty.dj": "empty.dj",
        }

    def test_refresh_respects_update_interval(self, temp_db, temp_yak_dir):
        with freeze_time("2025-01-01 00:00:00") as frozen_time:
            assert refresh_search_index(temp_yak_dir, force=True)

            (temp_yak_dir / "file1.dj").write_text("changed within the guard window")
            assert not refresh_search_index(temp_yak_dir)

            frozen_time.move_to("2025-01-01 00:02:00")
            assert refresh_search_index(temp_yak_dir)
            assert not refresh_search_index(temp_yak_dir)
