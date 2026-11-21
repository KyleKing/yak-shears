"""Vault operations behind the sync API: the manifest and conditional create.

A native client keeps its own copy of the vault and reconciles it against the
manifest. Every write is conditional on a lease, so the server stays the single
writer and a client can never overwrite a version it has not seen.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path as SyncPath
from pathlib import PurePosixPath

from anyio import Path

from yak_shears._yak.filenames import is_canonical
from yak_shears._yak.services import (
    StaleYakError,
    YakPathError,
    index_yak_metadata,
    list_yak_paths,
    resolve_yak_path,
    yak_lease,
)

YAK_SUFFIX = ".dj"


@dataclass(frozen=True)
class ManifestEntry:
    """One yak as the sync manifest describes it."""

    path: str
    lease: str
    modified: str


def _is_hidden(relative: PurePosixPath) -> bool:
    """Whether any part of a vault path is hidden (Syncthing's `.stversions`, `.stfolder`).

    Returns:
        True when a directory or file name starts with a dot.
    """
    return any(part.startswith(".") for part in relative.parts)


async def build_manifest(yak_dir: Path) -> list[ManifestEntry]:
    """List every yak with the lease a client must present to change it.

    Hidden directories are skipped: `.stversions` holds Syncthing's backup copies,
    which a client would otherwise download as if they were notes.

    Returns:
        Entries sorted by path, so two manifests of the same vault compare equal.
    """
    entries = []
    for yak_path in await list_yak_paths(yak_dir):
        relative = PurePosixPath(yak_path.relative_to(yak_dir).as_posix())
        if _is_hidden(relative):
            continue
        content = await yak_path.read_text(encoding="utf-8")
        modified = datetime.fromtimestamp((await yak_path.stat()).st_mtime, tz=UTC)
        entries.append(ManifestEntry(path=relative.as_posix(), lease=yak_lease(content), modified=modified.isoformat()))
    return sorted(entries, key=lambda entry: entry.path)


def validate_new_yak_path(relative_path: str) -> None:
    """Check that a client-chosen path names a yak the way the server would have.

    The listing sort is a plain filename compare, so a client that creates notes
    offline has to name them with `canonical_stem()` like every other writer, in
    the vault root or one category directory deep.

    Raises:
        YakPathError: If the path is not `[category/]<canonical stem>.dj`.
    """
    relative = PurePosixPath(relative_path)
    if (
        relative.suffix != YAK_SUFFIX
        or not is_canonical(relative.stem)
        or len(relative.parts) > 2  # noqa: PLR2004
        or _is_hidden(relative)
        or "\\" in relative_path
    ):
        msg = f"New yaks must be named [category/]<UTC instant>{YAK_SUFFIX}: {relative_path!r}"
        raise YakPathError(msg)


async def create_yak_with_content(yak_dir: Path, relative_path: str, content: str) -> str:
    """Create a yak a client wrote offline, refusing to replace an existing file.

    Returns:
        Lease for the content just written.

    Raises:
        StaleYakError: If a file already exists at the path, carrying its content
    """
    validate_new_yak_path(relative_path)
    yak_path = await resolve_yak_path(yak_dir, relative_path)
    await yak_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        async with await yak_path.open("x", encoding="utf-8") as handle:
            await handle.write(content)
    except FileExistsError:
        current = await yak_path.read_text(encoding="utf-8")
        msg = f"{relative_path} already exists"
        raise StaleYakError(msg, current) from None
    index_yak_metadata(SyncPath(yak_path), SyncPath(yak_dir))
    return yak_lease(content)
