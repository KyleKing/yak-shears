"""Business logic services for Yak management.

Separates business logic from HTTP handlers for better testability
and cleaner separation of concerns.
"""

import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from operator import itemgetter
from pathlib import Path as SyncPath

from anyio import Path

from yak_shears._log_utils import StageTimer, log
from yak_shears._templates import Recency, SearchResult, SortBy, YakInfo
from yak_shears._yak.database import (
    WordMatch,
    check_tables_exist,
    close_search_db,
    derive_title,
    get_backlinks,
    get_file_titles,
    get_search_db_path,
    get_word_count,
    init_search_db,
    refresh_search_index,
    replace_links,
    search_words,
    upsert_frontmatter,
)
from yak_shears._yak.filenames import canonical_stem
from yak_shears.frontmatter import parse_frontmatter
from yak_shears.links import extract_all_links, extract_tags, extract_wikilinks

PREVIEW_LENGTH = 200
PREVIEW_SOURCE_LIMIT = 600
PREVIEW_MAX_LINES = 12
_URL_RE = re.compile(r"https?://", re.IGNORECASE)

# Lamp thresholds in days. The question a rack answers at a glance is "what have
# I touched lately", so the scale is coarse: this week, this month, this year.
_RECENCY_DAYS = ((7, Recency.LIVE), (30, Recency.RECENT), (365, Recency.IDLE))


def _count_links(body: str) -> int:
    """Count hyperlinks (URLs and wikilinks) in a yak body."""
    return len(_URL_RE.findall(body)) + len(extract_wikilinks(body))


def _recency(modified: datetime, now: datetime) -> Recency:
    """Bucket a modification time into a lamp state."""
    age = (now - modified).days
    return next((state for limit, state in _RECENCY_DAYS if age < limit), Recency.COLD)


_TASK_ITEM_RE = re.compile(r"^\s*[-*+]\s+\[( |x|X)\]\s+(.*)$")


def _list_preview_source(body: str) -> str:
    """Preview source for a `type: list` note: its title plus open items.

    The card is glanced at to answer "what do I still need", so unchecked
    items outrank the body head. One pass over the lines, no extra I/O.

    Returns:
        The rebuilt preview source, or the body unchanged when nothing is open.
    """
    lines = body.splitlines()
    title = next((line for line in lines if line.startswith("#")), "")
    open_items = [f"- [ ] {match[2]}" for line in lines if (match := _TASK_ITEM_RE.match(line)) and match[1] == " "]
    if not open_items:
        return body
    return "\n".join([title, "", *open_items] if title else open_items)


_HABIT_COMPLETION_RE = re.compile(r"^\s*[-*+]\s+\[[xX]\]\s+\d{4}-\d{2}-\d{2}\s*$")


def _open_ordinals(body: str) -> list[int]:
    """Ordinals of unchecked items, counted across all task items.

    Returns:
        Indices in the ordinal scheme /lists/toggle expects.
    """
    matches = [match for line in body.splitlines() if (match := _TASK_ITEM_RE.match(line))]
    return [index for index, match in enumerate(matches) if match[1] == " "]


def _habit_preview_source(body: str) -> str:
    """Preview source for a `type: habit` note: the body minus its completion log.

    Returns:
        The body with dated completion items dropped; the log is history, not
        a preview.
    """
    return "\n".join(line for line in body.splitlines() if not _HABIT_COMPLETION_RE.match(line)).strip()


def _truncate_source(body: str, limit: int, max_lines: int) -> tuple[str, bool]:
    """Clip a preview source to at most `max_lines` lines and `limit` chars.

    Keeps cards cheap to render: the grid draws dozens at once and only a few
    lines are visible after the CSS height clamp.
    """
    truncated = False
    lines = body.split("\n")
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        truncated = True
    clipped = "\n".join(lines)
    if len(clipped) > limit:
        cut = clipped.rfind("\n", 0, limit)
        if cut <= 0:
            cut = limit
        clipped = clipped[:cut]
        truncated = True
    return clipped, truncated


# -----------------------------------------------------------------------------
# Configuration


async def get_yak_dir() -> Path:
    """Returns the `YAK_SHEARS_DIR` or fallback."""
    return await Path(os.getenv("YAK_SHEARS_DIR", "~/Sync/yak-shears")).expanduser()


class YakPathError(ValueError):
    """Raised when a user-supplied yak path is unsafe or malformed."""


class StaleYakError(Exception):
    """Raised when a save would overwrite changes made since the yak was opened.

    Carries what is on disk so a caller can show the reader the difference rather
    than only telling them there is one.
    """

    def __init__(self, message: str, current: str = "") -> None:
        super().__init__(message)
        self.current = current


async def resolve_yak_path(yak_dir: Path, relative_path: str) -> Path:
    """Resolve a user-supplied relative path strictly within `yak_dir`.

    Prevents path traversal (e.g. `../../etc/passwd`) and absolute paths from
    escaping the notes directory.

    Raises:
        YakPathError: If the path is empty, absolute, or escapes `yak_dir`.
    """
    if not relative_path or SyncPath(relative_path).is_absolute():
        msg = f"Invalid yak path: {relative_path!r}"
        raise YakPathError(msg)

    base = await yak_dir.resolve()
    resolved = await (yak_dir / relative_path).resolve()
    if resolved != base and base not in resolved.parents:
        msg = f"Yak path escapes notes directory: {relative_path!r}"
        raise YakPathError(msg)
    return resolved


def _validate_category(category: str) -> str:
    """Validate that a category is a single safe path segment.

    Raises:
        YakPathError: If the category contains path separators or traversal.
    """
    if category in {".", ".."} or "/" in category or "\\" in category or "\x00" in category:
        msg = f"Invalid category: {category!r}"
        raise YakPathError(msg)
    return category


# -----------------------------------------------------------------------------
# Yak listing operations


async def list_yak_paths(yak_dir: Path) -> list[Path]:
    """Return all djot yak paths in directory."""
    if not await yak_dir.exists() or not await yak_dir.is_dir():
        return []
    return [f async for f in yak_dir.rglob("*.dj") if await f.is_file()]


async def get_categories(all_paths: list[Path]) -> set[str]:
    """Get available categories (parent directory names)."""
    return {f.parent.name for f in all_paths if await f.is_file()}


@dataclass(frozen=True)
class PaginationResult:
    """Result of paginating yak paths."""

    paths: list[Path]
    total_count: int
    total_pages: int


async def paginate_yaks(
    paths: list[Path],
    page: int,
    page_size: int,
    sort_by: SortBy,
    category: str | None = None,
) -> PaginationResult:
    """Filter, sort, and paginate yak paths."""
    if not paths:
        return PaginationResult(paths=[], total_count=0, total_pages=0)

    if category:
        paths = [f for f in paths if f.parent.name == category]

    if sort_by == SortBy.MODIFIED_DATE:
        path_mtimes = [(pth, (await pth.stat()).st_mtime) for pth in paths]
        path_mtimes.sort(key=itemgetter(1), reverse=True)
        paths = [pth for pth, _ in path_mtimes]
    else:
        # SortBy.CREATED_AT: filenames are creation timestamps, so sorting by
        # name is equivalent to and more reliable than filesystem metadata.
        paths = sorted(paths, key=lambda pth: pth.name.lower(), reverse=True)

    total_count = len(paths)
    total_pages = (total_count + page_size - 1) // page_size

    start_idx = (page - 1) * page_size
    end_idx = min(start_idx + page_size, total_count)

    return PaginationResult(
        paths=paths[start_idx:end_idx],
        total_count=total_count,
        total_pages=total_pages,
    )


async def prepare_yak_info(paths: list[Path], yak_dir: Path) -> list[YakInfo]:
    """Prepare yak data for template rendering."""
    yaks = []
    now = datetime.now(tz=UTC)
    for yak_path in paths:
        yak_stats = await yak_path.stat()
        modified = datetime.fromtimestamp(yak_stats.st_mtime, tz=UTC)
        last_modified = modified.strftime("%Y-%m-%d %H:%M:%S")
        content = await yak_path.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(content)
        body = body.strip()
        open_ordinals: list[int] = []
        match meta.get("type"):
            case "list":
                preview_source = _list_preview_source(body)
                open_ordinals = _open_ordinals(body)
            case "habit":
                preview_source = _habit_preview_source(body)
            case _:
                preview_source = body
        preview, truncated = _truncate_source(preview_source, PREVIEW_SOURCE_LIMIT, PREVIEW_MAX_LINES)
        rel_path = yak_path.relative_to(yak_dir).as_posix()

        info = YakInfo(
            backlink_count=len(get_backlinks(rel_path)),
            category=yak_path.parent.name,
            kind=str(meta.get("type") or ("task" if meta.get("state") else "")),
            last_modified=last_modified,
            link_count=_count_links(body),
            name=yak_path.name,
            open_ordinals=open_ordinals,
            path=rel_path,
            preview=preview,
            recency=_recency(modified, now),
            tags=extract_tags(body),
            truncated=truncated,
        )
        yaks.append(info)
    return yaks


async def read_yak_body(yak_dir: Path, relative_path: str) -> str:
    """Read a yak's content with YAML frontmatter stripped.

    Raises:
        FileNotFoundError: If yak doesn't exist
    """
    yak_path = await resolve_yak_path(yak_dir, relative_path)
    if not await yak_path.is_file():
        msg = f"Yak not found: {yak_path}"
        raise FileNotFoundError(msg)

    content = await yak_path.read_text(encoding="utf-8")
    _, body = parse_frontmatter(content)
    return body


# -----------------------------------------------------------------------------
# Yak CRUD operations


async def create_yak(yak_dir: Path, category: str) -> Path:
    """Create a new empty yak file.

    Returns:
        Path to the newly created yak file.
    """
    _validate_category(category)
    category_dir = yak_dir / category
    await category_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{canonical_stem(datetime.now(UTC))}.dj"
    yak_path = category_dir / filename

    await yak_path.write_text("", encoding="utf-8")
    return yak_path


async def read_yak(yak_dir: Path, relative_path: str) -> tuple[str, str]:
    """Read yak content and category.

    Returns:
        Tuple of (content, category)

    Raises:
        FileNotFoundError: If yak doesn't exist
    """
    yak_path = await resolve_yak_path(yak_dir, relative_path)
    if not await yak_path.is_file():
        msg = f"Yak not found: {yak_path}"
        raise FileNotFoundError(msg)

    content = await yak_path.read_text(encoding="utf-8")
    category = yak_path.parent.name if yak_path.parent != yak_dir else ""
    return content, category


def yak_lease(content: str) -> str:
    """Fingerprint content so a save can prove which version it started from."""
    return sha256(content.encode("utf-8")).hexdigest()[:16]


async def read_leased(yak_path: Path, expected_lease: str | None) -> str:
    """Read a yak, refusing when it no longer matches the lease the page carried.

    An action composed against a stale page (toggle the third item, advance this
    task) can still apply cleanly to changed content while meaning something the
    reader never intended.

    Returns:
        Current file content.

    Raises:
        StaleYakError: If expected_lease does not match what is on disk
    """
    content = await yak_path.read_text()
    if expected_lease is not None and yak_lease(content) != expected_lease:
        msg = f"{yak_path.name} changed since this page was loaded"
        raise StaleYakError(msg, content)
    return content


async def save_yak(yak_dir: Path, relative_path: str, content: str, expected_lease: str | None = None) -> str:
    """Save yak content and update metadata index.

    Passing expected_lease makes the write conditional, the way
    `git push --force-with-lease` is: the save is refused when the file changed
    underneath the editor (Syncthing, another device, a second tab).

    Returns:
        Lease for the content just written.

    Raises:
        FileNotFoundError: If yak doesn't exist
        StaleYakError: If expected_lease does not match what is on disk
    """
    yak_path = await resolve_yak_path(yak_dir, relative_path)
    if not await yak_path.is_file():
        msg = f"Yak not found: {yak_path}"
        raise FileNotFoundError(msg)

    if expected_lease is not None:
        current = await yak_path.read_text(encoding="utf-8")
        if yak_lease(current) != expected_lease:
            msg = f"{relative_path} changed since it was opened"
            raise StaleYakError(msg, current)

    await yak_path.write_text(content, encoding="utf-8")
    index_yak_metadata(SyncPath(yak_path), SyncPath(yak_dir))
    return yak_lease(content)


async def delete_yak(yak_dir: Path, relative_path: str) -> None:
    """Delete a yak file.

    Raises:
        FileNotFoundError: If yak doesn't exist
    """
    yak_path = await resolve_yak_path(yak_dir, relative_path)
    if not await yak_path.is_file():
        msg = f"Yak not found: {yak_path}"
        raise FileNotFoundError(msg)

    await yak_path.unlink()


# -----------------------------------------------------------------------------
# Metadata indexing


def index_yak_metadata(yak_path: SyncPath, yak_dir: SyncPath) -> None:
    """Index frontmatter and links from a yak file."""
    try:
        rel_path = yak_path.relative_to(yak_dir).as_posix()
        content = yak_path.read_text(encoding="utf-8")

        frontmatter, body = parse_frontmatter(content)
        links = extract_all_links(body)

        upsert_frontmatter(rel_path, frontmatter)
        replace_links(rel_path, links)
    except Exception as exc:
        log(f"WARNING: Failed to index metadata for {yak_path}: {exc}")


# -----------------------------------------------------------------------------
# Search operations


async def ensure_search_db_ready() -> None:
    """Ensure the search database exists, is valid, and has the current schema."""
    db_path = get_search_db_path()
    if await Path(db_path).exists() and not check_tables_exist():
        log("WARNING: Search database appears corrupted, reinitializing")
        close_search_db()
        await Path(db_path).unlink(missing_ok=True)
    init_search_db()


def ensure_search_index_updated(sync_yak_dir: SyncPath) -> None:
    """Ensure the search index is up to date."""
    try:
        refresh_search_index(sync_yak_dir, force=get_word_count() == 0)
    except Exception as exc:
        log(f"WARNING: Failed to update search index: {exc}")


def perform_search(query: str, sync_yak_dir: SyncPath, timer: StageTimer | None = None) -> list[SearchResult]:
    """Perform search and return processed results."""
    timer = timer or StageTimer()
    with timer.stage("query"):
        raw_results = search_words(query)
    with timer.stage("process"):
        return _process_search_results(raw_results, sync_yak_dir)


def _process_search_results(
    search_results: list[WordMatch],
    sync_yak_dir: SyncPath,
) -> list[SearchResult]:
    """Process raw search results into SearchResult objects, keeping the best hit per file.

    Returns:
        One result per matched file, in relevance order.
    """
    seen_paths: set[str] = set()
    matched = [match for match in search_results if not (match.path in seen_paths or seen_paths.add(match.path))]

    titles = get_file_titles([match.path for match in matched])
    results = []
    for match in matched:
        result = _create_search_result(
            sync_yak_dir / match.path, match.path, match.line_num, match.word, titles.get(match.path)
        )
        if result:
            results.append(result)

    return results


def _create_search_result(
    file_path: SyncPath,
    rel_path: str,
    line_num: int,
    word: str,
    title: str | None = None,
) -> SearchResult | None:
    """Create a SearchResult from a file path, returning None on error."""
    try:
        content = file_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        if not (1 <= line_num <= len(lines)):
            return None
        return SearchResult(
            path=rel_path,
            line_num=line_num,
            preview=lines[line_num - 1].strip(),
            word=word,
            first_line=title or derive_title(content, rel_path),
        )
    except Exception as exc:
        log(f"WARNING: Error reading file {file_path}: {exc}")
        return None


# -----------------------------------------------------------------------------
# Preview generation


def highlight_content(content: str, query: str) -> str:
    """Highlight search query matches in content."""
    import html

    if not query:
        return content

    words = [w for w in query.lower().split() if w.strip()]
    if not words:
        return content

    def _highlight_line(line: str) -> str:
        matches: list[tuple[int, int, str]] = []
        for word in words:
            pattern = re.compile(re.escape(word), re.IGNORECASE)
            matches.extend((match.start(), match.end(), match.group(0)) for match in pattern.finditer(line))

        if not matches:
            return html.escape(line)

        matches.sort()
        merged: list[tuple[int, int, str]] = []
        for start, end, text in matches:
            if merged and start < merged[-1][1]:
                merged[-1] = (merged[-1][0], max(end, merged[-1][1]), line[merged[-1][0]:max(end, merged[-1][1])])
            else:
                merged.append((start, end, text))

        result: list[str] = []
        last_end = 0
        for start, end, text in merged:
            result.extend((html.escape(line[last_end:start]), f'<span class="search-highlight">{html.escape(text)}</span>'))
            last_end = end
        result.append(html.escape(line[last_end:]))

        return "".join(result)

    return "\n".join(_highlight_line(line) for line in content.splitlines())
