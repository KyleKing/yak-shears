"""The `shears lsp` language server: wikilink completion, navigation, note creation, and the streams board."""

import logging
import re
from datetime import UTC, datetime
from functools import partial
from pathlib import Path as SyncPath
from typing import Any

from anyio import Path as AsyncPath
from anyio import to_thread
from lsprotocol import types
from pygls.lsp.server import LanguageServer
from pygls.uris import from_fs_path, to_fs_path
from pygls.workspace import TextDocument

from yak_shears._yak.board import BoardActionError, apply_action
from yak_shears._yak.database import close_search_db, get_backlinks, search_link_candidates
from yak_shears._yak.services import (
    StaleYakError,
    YakPathError,
    create_yak,
    ensure_search_db_ready,
    ensure_search_index_updated,
    get_yak_dir,
    read_leased,
    resolve_yak_path,
)
from yak_shears._yak.streams import StreamInfo, TaskInfo, collect_streams
from yak_shears.leases import yak_lease
from yak_shears.links import WIKILINK_RE, resolve_link

logger = logging.getLogger(__name__)

_OPEN_WIKILINK_RE = re.compile(r"\[\[([^\]\[]*)$")
_ZERO_RANGE = types.Range(start=types.Position(line=0, character=0), end=types.Position(line=0, character=0))

server = LanguageServer("shears", "v1")


def _line_at(document: TextDocument, position: types.Position) -> str:
    return document.lines[position.line] if position.line < len(document.lines) else ""


def _wikilink_target_at(line: str, character: int) -> str | None:
    for match in WIKILINK_RE.finditer(line):
        if match.start() <= character <= match.end():
            return match.group(1).strip()
    return None


def _relative_path(uri: str, yak_dir: AsyncPath) -> str:
    fs_path = to_fs_path(uri)
    if fs_path is None:
        msg = f"Not a file URI: {uri!r}"
        raise ValueError(msg)
    return SyncPath(fs_path).relative_to(SyncPath(str(yak_dir))).as_posix()


async def _completion_list(ls: LanguageServer, params: types.CompletionParams) -> types.CompletionList | None:
    document = ls.workspace.get_text_document(params.text_document.uri)
    line = _line_at(document, params.position)
    match = _OPEN_WIKILINK_RE.search(line[: params.position.character])
    if match is None:
        return None

    prefix = match.group(1)
    yak_dir = await get_yak_dir()
    await ensure_search_db_ready()
    await to_thread.run_sync(ensure_search_index_updated, SyncPath(str(yak_dir)))
    candidates = await to_thread.run_sync(partial(search_link_candidates, limit=8), prefix)

    edit_range = types.Range(
        start=types.Position(line=params.position.line, character=match.start()),
        end=params.position,
    )
    return types.CompletionList(
        is_incomplete=False,
        items=[
            types.CompletionItem(
                label=candidate.title,
                detail=candidate.target,
                kind=types.CompletionItemKind.Reference,
                text_edit=types.TextEdit(range=edit_range, new_text=f"[[{candidate.target}]]"),
            )
            for candidate in candidates
        ],
    )


@server.feature(types.TEXT_DOCUMENT_COMPLETION, types.CompletionOptions(trigger_characters=["["]))
async def completion(ls: LanguageServer, params: types.CompletionParams) -> types.CompletionList | None:
    """Offer notes as wikilink completions when the cursor sits inside an unclosed `[[`.

    Returns:
        Matching notes as completion items, or None outside a wikilink.
    """
    try:
        return await _completion_list(ls, params)
    except Exception:
        logger.exception("textDocument/completion failed")
        return None
    finally:
        # nvim holds this server open all day; the web app must not be locked out between requests.
        close_search_db()


async def _definition_location(ls: LanguageServer, params: types.TextDocumentPositionParams) -> types.Location | None:
    document = ls.workspace.get_text_document(params.text_document.uri)
    line = _line_at(document, params.position)
    target = _wikilink_target_at(line, params.position.character)
    if target is None:
        return None

    yak_dir = await get_yak_dir()
    resolved = await to_thread.run_sync(resolve_link, target, SyncPath(str(yak_dir)))
    if resolved is None:
        return None
    return types.Location(uri=from_fs_path(str(resolved)), range=_ZERO_RANGE)


@server.feature(types.TEXT_DOCUMENT_DEFINITION)
async def definition(ls: LanguageServer, params: types.TextDocumentPositionParams) -> types.Location | None:
    """Resolve the wikilink under the cursor to the note it targets.

    Returns:
        The target note's location, or None when the cursor is not on a resolvable wikilink.
    """
    try:
        return await _definition_location(ls, params)
    except Exception:
        logger.exception("textDocument/definition failed")
        return None


def _all_backlinks(rel_path: str) -> list[str]:
    # The indexer stores a wikilink target as the bare stem and a path link as the vault-relative
    # path, so a note only finds all of its backlinks by asking under both spellings.
    stem = SyncPath(rel_path).stem
    sources = {source for source, _ in get_backlinks(rel_path)}
    sources |= {source for source, _ in get_backlinks(stem)}
    return sorted(sources)


async def _backlink_locations(ls: LanguageServer, params: types.ReferenceParams) -> list[types.Location]:
    document = ls.workspace.get_text_document(params.text_document.uri)
    yak_dir = await get_yak_dir()
    rel_path = _relative_path(document.uri, yak_dir)
    sources = await to_thread.run_sync(_all_backlinks, rel_path)
    return [
        types.Location(uri=from_fs_path(str(SyncPath(str(yak_dir)) / source)), range=_ZERO_RANGE)
        for source in sources
    ]


@server.feature(types.TEXT_DOCUMENT_REFERENCES)
async def references(ls: LanguageServer, params: types.ReferenceParams) -> list[types.Location]:
    """List notes that link to the current document.

    Returns:
        A location per note that links here, or an empty list when nothing does.
    """
    try:
        return await _backlink_locations(ls, params)
    except Exception:
        logger.exception("textDocument/references failed")
        return []
    finally:
        close_search_db()


def _task_payload(task: TaskInfo) -> dict[str, Any]:
    return {
        "title": task.title,
        "path": task.path,
        "state": task.state,
        "due": task.due,
        "flex": task.flex,
        "urgency": task.urgency,
        "waiting": task.waiting,
        "relations": task.relations,
        "recency": task.recency.value,
        "lease": task.lease,
    }


def _stream_payload(stream: StreamInfo) -> dict[str, Any]:
    return {
        "key": stream.key,
        "name": stream.name,
        "category": stream.category,
        "color": stream.color,
        "wip_limit": stream.wip_limit,
        "wip": stream.wip,
        "over_wip": stream.over_wip,
        "drained": stream.drained,
        "reaches": {state: [_task_payload(task) for task in reach] for state, reach in stream.reaches.items()},
    }


async def _load_leased_note(
    yak_dir: AsyncPath, path: str, action: str, lease: str
) -> tuple[AsyncPath, str] | dict[str, Any]:
    try:
        yak_path = await resolve_yak_path(yak_dir, path)
    except YakPathError as err:
        return {"ok": False, "code": "invalid", "error": str(err)}

    if action.startswith("stream:") and action != "stream:clear":
        streams, _ = await collect_streams()
        if action.removeprefix("stream:") not in {stream.key for stream in streams}:
            return {"ok": False, "code": "invalid", "error": "Unknown stream"}

    try:
        content = await read_leased(yak_path, lease)
    except StaleYakError as err:
        return {"ok": False, "code": "stale", "error": str(err)}
    except FileNotFoundError as err:
        return {"ok": False, "code": "not_found", "error": str(err)}

    return yak_path, content


async def _act(params: dict[str, Any]) -> dict[str, Any]:
    path = str(params.get("path", ""))
    action = str(params.get("action", ""))
    reason = str(params.get("reason", ""))
    lease = str(params.get("lease", ""))
    if not lease:
        return {"ok": False, "code": "invalid", "error": "Missing lease"}

    yak_dir = await get_yak_dir()
    loaded = await _load_leased_note(yak_dir, path, action, lease)
    if isinstance(loaded, dict):
        return loaded
    yak_path, content = loaded

    try:
        result = apply_action(content, action, reason=reason, today=datetime.now(tz=UTC).date())
    except BoardActionError as err:
        return {"ok": False, "code": "invalid", "error": str(err)}

    await yak_path.write_text(result.content)
    return {
        "ok": True,
        "label": result.label,
        "lease": yak_lease(result.content),
        "inverse": {"path": path, "action": result.inverse, "reason": result.inverse_reason},
    }


@server.command("shears.act")
async def act(_ls: LanguageServer, params: dict[str, Any]) -> dict[str, Any]:
    """Apply one board action to a task note and return its inverse for undo.

    Returns:
        `{"ok": True, "label", "lease", "inverse"}` on success, or an
        `{"ok": False, "code", "error"}` shape on failure.
    """
    try:
        return await _act(params)
    except Exception:
        logger.exception("shears.act failed")
        return {"ok": False, "code": "failed", "error": "shears.act failed"}
    finally:
        close_search_db()


async def _bench(kind: str) -> dict[str, Any]:
    if kind != "streams":
        return {"ok": False, "code": "invalid", "error": f"Unsupported bench kind: {kind!r}"}
    streams, orphans = await collect_streams()
    return {
        "ok": True,
        "kind": "streams",
        "streams": [_stream_payload(stream) for stream in streams],
        "orphans": [_task_payload(task) for task in orphans],
    }


@server.command("shears.bench")
async def bench(_ls: LanguageServer, kind: str) -> dict[str, Any]:
    """Fetch bench data for the nvim streams buffer.

    Returns:
        The bench payload for `kind`, or an `{"ok": False, "code", "error"}`
        shape on failure.
    """
    try:
        return await _bench(kind)
    except Exception:
        logger.exception("shears.bench failed")
        return {"ok": False, "code": "failed", "error": "shears.bench failed"}
    finally:
        close_search_db()


@server.command("shears.new")
async def new_note(_ls: LanguageServer, category: str) -> dict[str, Any]:
    """Create a new note in `category`.

    Returns:
        `{"ok": True, "path"}` on success, or an `{"ok": False, "code", "error"}`
        shape on failure.
    """
    try:
        yak_dir = await get_yak_dir()
        path = await create_yak(yak_dir, category)
    except Exception:
        logger.exception("shears.new failed")
        return {"ok": False, "code": "failed", "error": "shears.new failed"}
    return {"ok": True, "path": str(path)}
