"""The Phase 4 query engine, exercised against a real indexed vault."""

from datetime import date
from unittest.mock import patch

import pytest

from yak_shears._yak.database import close_search_db, init_search_db, update_search_index
from yak_shears._yak.query import (
    Absent,
    DateWithin,
    Equals,
    Note,
    OneOf,
    Present,
    group_counts,
    select,
    sort_notes,
)
from yak_shears.leases import yak_lease

VAULT = {
    "work/ship-it.dj": "---\ntype: task\nstate: queue\nstream: work/launch\ndue: 2026-09-04\n---\n\n# Ship it\n",
    "work/draft.dj": "---\ntype: task\nstate: backlog\nstream: work/launch\n---\n\n# Draft\n",
    "work/done.dj": "---\ntype: task\nstate: complete\nstream: work/launch\n---\n\n# Done\n",
    "work/launch.dj": "---\ntype: stream\nid: launch\nname: Launch\n---\n\n# Launch\n",
    "home/loose.dj": "---\ntype: task\nstate: queue\n---\n\n# Loose end\n",
    "home/plain.dj": "no frontmatter here\n",
}


@pytest.fixture
def indexed_vault(tmp_path, worker_id):
    db_dir = tmp_path / "db" / worker_id
    db_dir.mkdir(parents=True)
    yak_dir = tmp_path / "yaks"
    for rel_path, content in VAULT.items():
        path = yak_dir / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    with patch.dict("os.environ", {"SEARCH_DB_DIR": str(db_dir), "YAK_SHEARS_DIR": str(yak_dir)}):
        init_search_db()
        update_search_index(yak_dir)
        yield yak_dir
        close_search_db()


def paths(notes: list[Note]) -> list[str]:
    return [note.path for note in notes]


@pytest.mark.parametrize(
    ("filters", "expected"),
    [
        ((Equals("state", "queue"),), ["home/loose.dj", "work/ship-it.dj"]),
        ((OneOf("state", ["backlog", "queue"]),), ["home/loose.dj", "work/draft.dj", "work/ship-it.dj"]),
        ((OneOf("state", []),), []),
        ((Present("stream"),), ["work/done.dj", "work/draft.dj", "work/ship-it.dj"]),
        ((Equals("type", "task"), Absent("stream")), ["home/loose.dj"]),
        ((DateWithin("due", 7, today=date(2026, 9, 1)),), ["work/ship-it.dj"]),
        ((DateWithin("due", 1, today=date(2026, 9, 1)),), []),
    ],
    ids=["equality", "membership", "empty-set", "presence", "triage", "due-soon", "not-yet-due"],
)
def test_filters(indexed_vault, filters, expected):
    assert paths(select(*filters)) == expected


def test_a_view_renders_from_the_store_alone(indexed_vault):
    """PLAN.md Phase 4's done-when.

    Notes in {backlog, queue} ordered by modified, with no file read beyond the index.
    """
    notes = sort_notes(select(OneOf("state", ["backlog", "queue"])), lambda note: note.modified)

    assert [note.title for note in notes] == ["Ship it", "Draft", "Loose end"]
    assert [note.category for note in notes] == ["work", "work", "home"]
    assert [note.lease for note in notes] == [yak_lease(VAULT[note.path]) for note in notes]


def test_group_counts_feed_the_dock_meters(indexed_vault):
    assert group_counts("state", Equals("type", "task")) == {"queue": 2, "backlog": 1, "complete": 1}


def test_stream_references_resolve_in_one_pass(indexed_vault):
    streams = {f"{note.category}/{note.meta['id']}": note for note in select(Equals("type", "stream"))}
    tasks = select(Equals("type", "task"))

    assert {task.path: streams.get(str(task.meta.get("stream"))) for task in tasks}.keys()
    assert streams["work/launch"].meta["name"] == "Launch"
    assert [task.path for task in tasks if str(task.meta.get("stream")) not in streams] == ["home/loose.dj"]


def test_a_note_without_frontmatter_is_absent_from_the_store(indexed_vault):
    assert "home/plain.dj" not in paths(select())
