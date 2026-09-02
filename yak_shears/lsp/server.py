"""The `shears lsp` language server: wikilink completion, navigation, and note creation."""

import logging
import re
from functools import partial
from pathlib import Path as SyncPath

from anyio import Path as AsyncPath
from anyio import to_thread
from lsprotocol import types
from pygls.lsp.server import LanguageServer
from pygls.uris import from_fs_path, to_fs_path
from pygls.workspace import TextDocument

from yak_shears._yak.database import close_search_db, get_backlinks, search_link_candidates
from yak_shears._yak.services import create_yak, ensure_search_db_ready, ensure_search_index_updated, get_yak_dir
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


async def _backlink_locations(ls: LanguageServer, params: types.ReferenceParams) -> list[types.Location]:
    document = ls.workspace.get_text_document(params.text_document.uri)
    yak_dir = await get_yak_dir()
    rel_path = _relative_path(document.uri, yak_dir)
    backlinks = await to_thread.run_sync(get_backlinks, rel_path)
    return [
        types.Location(uri=from_fs_path(str(SyncPath(str(yak_dir)) / source_path)), range=_ZERO_RANGE)
        for source_path, _link_type in backlinks
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


@server.command("shears.new")
async def new_note(_ls: LanguageServer, category: str, _template: str | None = None) -> dict[str, str]:
    """Create a new note in `category`.

    Returns:
        `{"path": <absolute path>}`, or `{}` on failure.
    """
    try:
        yak_dir = await get_yak_dir()
        path = await create_yak(yak_dir, category)
        return {"path": str(path)}
    except Exception:
        logger.exception("shears.new failed")
        return {}
