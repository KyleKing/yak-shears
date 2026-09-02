"""Tests for the `shears lsp` language server."""

import inspect
from pathlib import Path as SyncPath

import pytest
from anyio import Path as AsyncPath
from lsprotocol import types
from pygls.workspace import Workspace

from tests.conftest import set_yak_shears_dir
from yak_shears._yak.database import _CACHE, close_search_db, init_search_db, update_search_index
from yak_shears._yak.filenames import is_canonical
from yak_shears.leases import yak_lease
from yak_shears.lsp.server import act, bench, completion, definition, new_note, references, server

# Notes live under a category directory, so a vault-relative path never equals a wikilink
# target: the indexer stores the target as a bare stem.
VAULT = {
    "tasks/alpha.dj": "---\ntype: note\n---\n\n# Alpha\n",
    "notes/beta.dj": "---\ntype: note\n---\n\nSee [[alpha]] and [[missing]] for context.\n",
}


@pytest.fixture
def indexed_vault(tmp_path):
    yak_dir = tmp_path / "yaks"
    for rel_path, content in VAULT.items():
        path = yak_dir / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    with set_yak_shears_dir(yak_dir):
        init_search_db()
        update_search_index(yak_dir)
        yield yak_dir


def _open_document(yak_dir: SyncPath, relative_path: str, text: str) -> str:
    server.protocol._workspace = Workspace(root_uri=yak_dir.as_uri())  # ruff: ignore[private-member-access]
    uri = (yak_dir / relative_path).as_uri()
    server.workspace.put_text_document(types.TextDocumentItem(uri=uri, language_id="djot", version=1, text=text))
    return uri


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("line", "character", "expected_line"),
    [
        ("[[alpha]]", 4, "[[alpha]]pha]]"),
        ("Some plain text", 16, None),
    ],
    ids=["mid-word-replaces-open-span", "no-bracket-returns-nothing"],
)
async def test_completion_text_edit_replaces_open_span(indexed_vault, line, character, expected_line):
    uri = _open_document(indexed_vault, "notes/beta.dj", line)
    params = types.CompletionParams(
        text_document=types.TextDocumentIdentifier(uri=uri),
        position=types.Position(line=0, character=character),
    )

    result = await completion(server, params)

    if expected_line is None:
        assert result is None
        return

    assert result is not None
    item = next(item for item in result.items if item.detail == "alpha")
    edit = item.text_edit
    assert isinstance(edit, types.TextEdit)
    assert line[: edit.range.start.character] + edit.new_text + line[edit.range.end.character :] == expected_line


@pytest.mark.asyncio
async def test_definition_resolves_wikilink_and_none_when_unresolved(indexed_vault):
    text = VAULT["notes/beta.dj"]
    uri = _open_document(indexed_vault, "notes/beta.dj", text)
    link_line = next(index for index, line in enumerate(text.splitlines()) if "[[alpha]]" in line)
    line_text = text.splitlines()[link_line]
    alpha_character = line_text.index("[[alpha]]") + 3
    missing_character = line_text.index("[[missing]]") + 3

    resolved = await definition(
        server,
        types.TextDocumentPositionParams(
            text_document=types.TextDocumentIdentifier(uri=uri), position=types.Position(link_line, alpha_character)
        ),
    )
    unresolved = await definition(
        server,
        types.TextDocumentPositionParams(
            text_document=types.TextDocumentIdentifier(uri=uri),
            position=types.Position(link_line, missing_character),
        ),
    )

    assert resolved is not None
    assert resolved.uri == (indexed_vault / "tasks/alpha.dj").as_uri()
    assert unresolved is None


@pytest.mark.asyncio
async def test_references_returns_backlinks_for_current_document(indexed_vault):
    uri = _open_document(indexed_vault, "tasks/alpha.dj", VAULT["tasks/alpha.dj"])
    params = types.ReferenceParams(
        text_document=types.TextDocumentIdentifier(uri=uri),
        position=types.Position(0, 0),
        context=types.ReferenceContext(include_declaration=False),
    )

    locations = await references(server, params)

    assert [location.uri for location in locations] == [(indexed_vault / "notes/beta.dj").as_uri()]


@pytest.mark.asyncio
async def test_shears_new_creates_a_canonically_named_note(indexed_vault):
    result = await new_note(server, "inbox")

    assert result["ok"] is True
    path = SyncPath(result["path"])
    assert path.parent.name == "inbox"
    assert path.parent.parent == indexed_vault
    assert is_canonical(path.stem)
    assert await AsyncPath(path).is_file()


def test_shears_new_takes_exactly_the_arguments_the_client_sends():
    """The pygls dispatcher passes command arguments positionally and rejects a mismatched count."""
    parameters = list(inspect.signature(new_note).parameters)

    assert parameters == ["_ls", "category"]


@pytest.mark.asyncio
async def test_search_db_connection_is_released_after_a_request(indexed_vault):
    uri = _open_document(indexed_vault, "notes/beta.dj", "[[al")
    params = types.CompletionParams(text_document=types.TextDocumentIdentifier(uri=uri), position=types.Position(0, 4))

    await completion(server, params)

    assert _CACHE.connection is None

    close_search_db()


STREAMS_VAULT = {
    "work/ship-it.dj": "---\ntype: task\nstate: queue\nstream: work/launch\ndue: 2026-09-04\n---\n\n# Ship it\n",
    "work/launch.dj": "---\ntype: stream\nid: launch\nname: Launch\n---\n\n# Launch\n",
}


@pytest.fixture
def streams_vault(tmp_path):
    yak_dir = tmp_path / "yaks"
    for rel_path, content in STREAMS_VAULT.items():
        path = yak_dir / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    with set_yak_shears_dir(yak_dir):
        init_search_db()
        update_search_index(yak_dir)
        yield yak_dir


@pytest.mark.asyncio
async def test_shears_bench_streams_returns_streams_with_the_task_in_its_reach(streams_vault):
    result = await bench(server, "streams")

    assert result["ok"] is True
    assert result["kind"] == "streams"
    assert result["orphans"] == []
    [stream] = result["streams"]
    assert stream["key"] == "work/launch"
    assert stream["name"] == "Launch"
    assert stream["wip"] == 0
    [task] = stream["reaches"]["queue"]
    assert task["path"] == "work/ship-it.dj"
    assert task["due"] == "2026-09-04"


@pytest.mark.asyncio
async def test_shears_bench_rejects_an_unsupported_kind(streams_vault):
    result = await bench(server, "habits")

    assert result == {"ok": False, "code": "invalid", "error": "Unsupported bench kind: 'habits'"}


@pytest.mark.asyncio
async def test_search_db_connection_is_released_after_a_bench_request(streams_vault):
    await bench(server, "streams")

    assert _CACHE.connection is None

    close_search_db()


@pytest.mark.asyncio
async def test_shears_act_applies_and_its_inverse_restores_the_original_content(streams_vault):
    path = "work/ship-it.dj"
    original = STREAMS_VAULT[path]

    applied = await act(server, {"path": path, "action": "advance", "reason": "", "lease": yak_lease(original)})

    assert applied["ok"] is True
    assert (streams_vault / path).read_text() != original

    inverse = applied["inverse"]
    restored = await act(
        server,
        {"path": inverse["path"], "action": inverse["action"], "reason": inverse["reason"], "lease": applied["lease"]},
    )

    assert restored["ok"] is True
    assert (streams_vault / path).read_text() == original


@pytest.mark.asyncio
async def test_shears_act_rejects_a_stale_lease_and_leaves_the_file_unchanged(streams_vault):
    path = "work/ship-it.dj"
    original = STREAMS_VAULT[path]

    result = await act(server, {"path": path, "action": "advance", "reason": "", "lease": "stale"})

    assert result["ok"] is False
    assert result["code"] == "stale"
    assert (streams_vault / path).read_text() == original


@pytest.mark.asyncio
async def test_shears_act_rejects_an_empty_lease_and_leaves_the_file_unchanged(streams_vault):
    path = "work/ship-it.dj"
    original = STREAMS_VAULT[path]

    result = await act(server, {"path": path, "action": "advance", "reason": "", "lease": ""})

    assert result == {"ok": False, "code": "invalid", "error": "Missing lease"}
    assert (streams_vault / path).read_text() == original
