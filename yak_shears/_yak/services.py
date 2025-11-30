"""Business logic services for Yak management.

Separates business logic from HTTP handlers for better testability
and cleaner separation of concerns.
"""

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from operator import itemgetter
from pathlib import Path as SyncPath

from anyio import Path

from yak_shears._log_utils import log
from yak_shears._templates import SearchResult, SortBy, YakInfo
from yak_shears._yak.database import (
    check_tables_exist,
    get_search_db_path,
    get_word_count,
    init_search_db,
    replace_links,
    search_words,
    should_update_index,
    update_search_index,
    upsert_frontmatter,
)
from yak_shears.frontmatter import parse_frontmatter
from yak_shears.links import extract_all_links

PREVIEW_LENGTH = 200


# -----------------------------------------------------------------------------
# Configuration


async def get_yak_dir() -> Path:
    """Returns the `YAK_SHEARS_DIR` or fallback."""
    return await Path(os.getenv("YAK_SHEARS_DIR", "~/Sync/yak-shears")).expanduser()


# -----------------------------------------------------------------------------
# Yak listing operations


async def list_yak_paths(yak_dir: Path) -> list[Path]:
    """Return all djot yak paths in directory."""
    if not await yak_dir.exists() or not await yak_dir.is_dir():
        return []
    return [_f async for _f in yak_dir.rglob("*.dj") if await _f.is_file()]


async def get_categories(all_paths: list[Path]) -> set[str]:
    """Get available categories (parent directory names)."""
    return {_f.parent.name for _f in all_paths if await _f.is_file()}


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
        paths = [_f for _f in paths if _f.parent.name == category]

    if sort_by == SortBy.MODIFIED_DATE:
        path_mtimes = [(pth, (await pth.stat()).st_mtime) for pth in paths]
        path_mtimes.sort(key=itemgetter(1), reverse=True)
        paths = [pth for pth, _ in path_mtimes]
    else:
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
    for yak_path in paths:
        yak_stats = await yak_path.stat()
        last_modified = datetime.fromtimestamp(yak_stats.st_mtime, tz=UTC).strftime("%Y-%m-%d %H:%M:%S")
        content = await yak_path.read_text(encoding="utf-8")
        preview = content[:PREVIEW_LENGTH].replace("\n", " ")

        info = YakInfo(
            category=yak_path.parent.name,
            last_modified=last_modified,
            name=yak_path.name,
            path=yak_path.relative_to(yak_dir).as_posix(),
            preview=preview,
            truncated=len(content) > PREVIEW_LENGTH,
        )
        yaks.append(info)
    return yaks


# -----------------------------------------------------------------------------
# Yak CRUD operations


async def create_yak(yak_dir: Path, category: str) -> Path:
    """Create a new empty yak file.

    Returns:
        Path to the newly created yak file.
    """
    category_dir = yak_dir / category
    await category_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}.dj"
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
    yak_path = yak_dir / relative_path
    if not await yak_path.is_file():
        raise FileNotFoundError(f"Yak not found: {yak_path}")

    content = await yak_path.read_text(encoding="utf-8")
    category = yak_path.parent.name if yak_path.parent != yak_dir else ""
    return content, category


async def save_yak(yak_dir: Path, relative_path: str, content: str) -> None:
    """Save yak content and update metadata index.

    Raises:
        FileNotFoundError: If yak doesn't exist
    """
    yak_path = yak_dir / relative_path
    if not await yak_path.is_file():
        raise FileNotFoundError(f"Yak not found: {yak_path}")

    await yak_path.write_text(content, encoding="utf-8")
    index_yak_metadata(SyncPath(yak_path), SyncPath(yak_dir))


async def delete_yak(yak_dir: Path, relative_path: str) -> None:
    """Delete a yak file.

    Raises:
        FileNotFoundError: If yak doesn't exist
    """
    yak_path = yak_dir / relative_path
    if not await yak_path.is_file():
        raise FileNotFoundError(f"Yak not found: {yak_path}")

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
    """Ensure the search database exists and is valid."""
    db_path = get_search_db_path()
    if not await Path(db_path).exists():
        init_search_db()
    elif not check_tables_exist():
        log("WARNING: Search database appears corrupted, reinitializing")
        await Path(db_path).unlink(missing_ok=True)
        init_search_db()


def ensure_search_index_updated(sync_yak_dir: SyncPath) -> None:
    """Ensure the search index is up to date."""
    try:
        if should_update_index(sync_yak_dir) or get_word_count() == 0:
            update_search_index(sync_yak_dir)
    except Exception as exc:
        log(f"WARNING: Failed to update search index: {exc}")


def perform_search(query: str, sync_yak_dir: SyncPath) -> list[SearchResult]:
    """Perform search and return processed results."""
    raw_results = search_words(query)
    return _process_search_results(raw_results, sync_yak_dir)


def _process_search_results(
    search_results: list[tuple[str, int, str]],
    sync_yak_dir: SyncPath,
) -> list[SearchResult]:
    """Process raw search results into SearchResult objects, grouped by file."""
    results = []
    seen_paths: set[str] = set()

    for path, line_num, word in search_results:
        if path in seen_paths:
            continue
        seen_paths.add(path)

        file_path = sync_yak_dir / path
        try:
            content = file_path.read_text(encoding="utf-8")
            lines = content.splitlines()
            if 1 <= line_num <= len(lines):
                preview = lines[line_num - 1].strip()
                first_line = lines[0].strip() if lines else ""
                results.append(
                    SearchResult(
                        path=path,
                        line_num=line_num,
                        preview=preview,
                        word=word,
                        first_line=first_line,
                    )
                )
        except Exception as exc:
            log(f"WARNING: Error reading file {file_path}: {exc}")

    return results


# -----------------------------------------------------------------------------
# Preview generation


def highlight_content(content: str, query: str) -> str:
    """Highlight search query matches in content."""
    import re

    if not query:
        return content

    lines = content.splitlines()
    highlighted_lines = []

    for line in lines:
        highlighted = line
        for word in query.lower().split():
            if word.strip():
                pattern = re.compile(re.escape(word), re.IGNORECASE)
                highlighted = pattern.sub(
                    lambda m: f'<span class="search-highlight">{m.group(0)}</span>',
                    highlighted,
                )
        highlighted_lines.append(highlighted)

    return "\n".join(highlighted_lines)
