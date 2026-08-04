"""Photo and video attachment handling for yaks.

Uploads are transcoded to web-safe formats (HEIC->JPEG, MOV/HEVC->H.264 MP4),
compressed, and stored per-category under ``<category>/_attachments/`` with a
content-hashed filename so re-uploading the same file dedupes. A downscaled
thumbnail (or video poster frame) is written under ``_attachments/.thumbs/``.

Blocking work (Pillow, ffmpeg) is dispatched to a worker thread so the async
handlers stay responsive.
"""

import hashlib
import re
import subprocess  # noqa: S404
import tempfile
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path as SyncPath

import filetype
from anyio import Path, to_thread
from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

from yak_shears._log_utils import log
from yak_shears.frontmatter import parse_frontmatter

register_heif_opener()

ATTACHMENTS_DIRNAME = "_attachments"
THUMBS_DIRNAME = ".thumbs"

MAX_IMAGE_BYTES = 25 * 1024 * 1024
MAX_VIDEO_BYTES = 300 * 1024 * 1024

_FULL_IMAGE_MAX_EDGE = 2560
_THUMB_MAX_EDGE = 640
_JPEG_QUALITY = 85
_THUMB_QUALITY = 78
_VIDEO_MAX_W = 1920
_VIDEO_MAX_H = 1080
_POSTER_MAX_EDGE = 640
_FILENAME_RE_OK = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")

_IMAGE_INPUT_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/heic", "image/heif"}
_VIDEO_INPUT_TYPES = {"video/mp4", "video/quicktime", "video/webm", "video/x-matroska", "video/x-msvideo"}


class MediaError(ValueError):
    """Raised when an upload is rejected (bad type, too large, or corrupt)."""


class MediaKind(StrEnum):
    """The two supported media families."""

    IMAGE = "image"
    VIDEO = "video"


@dataclass(frozen=True)
class MediaResult:
    """Outcome of processing one upload, ready to embed in a yak."""

    kind: MediaKind
    category: str
    filename: str
    url: str
    thumb_url: str
    snippet: str
    reused: bool


def category_of(yak_rel_path: str) -> str:
    """Return the category (top-level dir) a yak lives in.

    Raises:
        MediaError: If the yak is at the notes root (no category to attach to).
    """
    parent = SyncPath(yak_rel_path).parent
    category = parent.name
    if not category or category == ".":
        msg = "Move this note into a category before adding media"
        raise MediaError(msg)
    return category


def _safe_filename(filename: str) -> str:
    """Reject any filename that isn't a plain ``<name>.<ext>`` token.

    Raises:
        MediaError: If the name contains path separators or unexpected chars.
    """
    if not filename or filename in {".", ".."} or set(filename) - _FILENAME_RE_OK:
        msg = f"Invalid attachment filename: {filename!r}"
        raise MediaError(msg)
    return filename


async def attachments_dir(yak_dir: Path, category: str) -> Path:
    """Return (creating if needed) the ``_attachments`` dir for a category."""
    attach = yak_dir / category / ATTACHMENTS_DIRNAME
    await attach.mkdir(parents=True, exist_ok=True)
    return attach


async def resolve_attachment(yak_dir: Path, category: str, filename: str, *, thumb: bool) -> Path:
    """Resolve a public media/thumb URL to a real file inside ``_attachments``.

    Raises:
        MediaError: If the category or filename is unsafe or escapes the dir.
    """
    _safe_filename(filename)
    if category in {".", ".."} or "/" in category or "\\" in category or "\x00" in category:
        msg = f"Invalid category: {category!r}"
        raise MediaError(msg)

    attach = yak_dir / category / ATTACHMENTS_DIRNAME
    target = (attach / THUMBS_DIRNAME / filename) if thumb else (attach / filename)

    base = await attach.resolve()
    resolved = await target.resolve()
    if base not in resolved.parents:
        msg = f"Attachment path escapes notes directory: {filename!r}"
        raise MediaError(msg)
    return resolved


def _detect_kind(data: bytes) -> tuple[MediaKind, str]:
    """Sniff the real media type from magic bytes, ignoring client claims.

    Returns:
        (kind, mime) tuple.

    Raises:
        MediaError: If the bytes aren't a supported image or video.
    """
    kind = filetype.guess(data)
    mime = kind.mime if kind else ""
    if mime in _IMAGE_INPUT_TYPES:
        return MediaKind.IMAGE, mime
    if mime in _VIDEO_INPUT_TYPES:
        return MediaKind.VIDEO, mime
    msg = f"Unsupported media type: {mime or 'unknown'}"
    raise MediaError(msg)


def _process_image(src: SyncPath, dest: SyncPath, thumb: SyncPath) -> None:
    """Transcode any image to a compressed JPEG plus a downscaled thumbnail."""
    with Image.open(src) as opened:
        oriented = ImageOps.exif_transpose(opened)
        rgb = oriented.convert("RGB")

        full = rgb.copy()
        full.thumbnail((_FULL_IMAGE_MAX_EDGE, _FULL_IMAGE_MAX_EDGE), Image.Resampling.LANCZOS)
        full.save(dest, "JPEG", quality=_JPEG_QUALITY, optimize=True, progressive=True)

        preview = rgb.copy()
        preview.thumbnail((_THUMB_MAX_EDGE, _THUMB_MAX_EDGE), Image.Resampling.LANCZOS)
        preview.save(thumb, "JPEG", quality=_THUMB_QUALITY, optimize=True)


def _run_ffmpeg(args: list[str]) -> None:
    """Run ffmpeg, raising MediaError with stderr context on failure.

    Raises:
        MediaError: If ffmpeg exits non-zero.
    """
    result = subprocess.run(  # noqa: S603
        ["ffmpeg", "-y", "-loglevel", "error", *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        log(f"ERROR: ffmpeg failed: {result.stderr.strip()[:500]}")
        msg = "Could not process video"
        raise MediaError(msg)


def _process_video(src: SyncPath, dest: SyncPath, poster: SyncPath) -> None:
    """Transcode any video to a web-safe H.264 MP4 and extract a poster frame."""
    scale = (
        f"scale='min({_VIDEO_MAX_W},iw)':'min({_VIDEO_MAX_H},ih)':"
        "force_original_aspect_ratio=decrease,scale=trunc(iw/2)*2:trunc(ih/2)*2"
    )
    _run_ffmpeg([
        "-i", str(src),
        "-map", "0:v:0", "-map", "0:a:0?",
        "-vf", scale,
        "-c:v", "libx264", "-profile:v", "high", "-level:v", "4.1",
        "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-ac", "2",
        "-movflags", "+faststart",
        str(dest),
    ])
    poster_vf = f"scale='min({_POSTER_MAX_EDGE},iw)':-2,format=yuvj420p"
    for seek in ("1", "0"):
        _run_ffmpeg(["-ss", seek, "-i", str(dest), "-frames:v", "1", "-vf", poster_vf, "-q:v", "3", str(poster)])
        if poster.exists():
            break


def _process_sync(
    data: bytes,
    kind: MediaKind,
    attach_dir: SyncPath,
    thumbs_dir: SyncPath,
    stem: str,
) -> str:
    """Blocking pipeline: write input, transcode, emit outputs. Returns filename."""
    ext = "jpg" if kind == MediaKind.IMAGE else "mp4"
    dest = attach_dir / f"{stem}.{ext}"
    thumb = thumbs_dir / f"{stem}.jpg"
    thumbs_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        raw = SyncPath(tmp) / "input"
        raw.write_bytes(data)
        if kind == MediaKind.IMAGE:
            _process_image(raw, dest, thumb)
        else:
            _process_video(raw, dest, thumb)
    return dest.name


async def process_upload(yak_dir: Path, yak_rel_path: str, filename: str, data: bytes) -> MediaResult:
    """Validate, transcode, and store an upload; return an embeddable result.

    The original bytes are hashed for dedupe and discarded after transcoding.

    Raises:
        MediaError: If the upload is unsupported, too large, or unreadable.
    """
    category = category_of(yak_rel_path)
    kind, _mime = _detect_kind(data)

    limit = MAX_IMAGE_BYTES if kind == MediaKind.IMAGE else MAX_VIDEO_BYTES
    if len(data) > limit:
        msg = f"File too large ({len(data) // (1024 * 1024)} MB); limit is {limit // (1024 * 1024)} MB"
        raise MediaError(msg)

    stem = hashlib.sha256(data).hexdigest()[:12]
    attach = await attachments_dir(yak_dir, category)
    ext = "jpg" if kind == MediaKind.IMAGE else "mp4"
    existing = attach / f"{stem}.{ext}"

    reused = await existing.is_file()
    if reused:
        out_name = existing.name
    else:
        out_name = await to_thread.run_sync(
            _process_sync, data, kind, SyncPath(attach), SyncPath(attach) / THUMBS_DIRNAME, stem
        )

    alt = SyncPath(filename).stem or "attachment"
    url = f"/media/{category}/{out_name}"
    thumb_url = f"/thumb/{category}/{stem}.jpg"
    return MediaResult(
        kind=kind,
        category=category,
        filename=out_name,
        url=url,
        thumb_url=thumb_url,
        snippet=f"![{alt}]({url})",
        reused=reused,
    )


# -----------------------------------------------------------------------------
# Doctor: reconcile references against files on disk

_MEDIA_REF_RE = re.compile(r"/media/([^/\s)\"']+)/([^\s)\"']+)")


@dataclass
class DoctorReport:
    """Attachment integrity across the notes directory.

    ``missing`` are ``/media/...`` references with no file on disk (broken
    embeds); ``orphans`` are attachment files no note references (safe to
    delete). Both hold ``(category, filename)`` pairs; ``missing`` also carries
    the referencing note path. ``untyped_tasks`` are notes carrying ``state:``
    without ``type: task``, the implicit form the kind system reads but
    Doctor asks to make explicit.
    """

    missing: list[tuple[str, str, str]] = field(default_factory=list)
    orphans: list[tuple[str, str, int]] = field(default_factory=list)
    referenced_count: int = 0
    file_count: int = 0
    untyped_tasks: list[str] = field(default_factory=list)


async def build_doctor_report(yak_dir: Path) -> DoctorReport:
    """Scan every yak for ``/media`` references and reconcile with disk."""
    report = DoctorReport()
    referenced: set[tuple[str, str]] = set()

    async for note in yak_dir.rglob("*.dj"):
        if not await note.is_file():
            continue
        rel = note.relative_to(yak_dir).as_posix()
        content = await note.read_text(encoding="utf-8")
        meta, _ = parse_frontmatter(content)
        if meta.get("state") and not meta.get("type"):
            report.untyped_tasks.append(rel)
        for category, filename in _MEDIA_REF_RE.findall(content):
            referenced.add((category, filename))
            attachment = yak_dir / category / ATTACHMENTS_DIRNAME / filename
            if not await attachment.is_file():
                report.missing.append((category, filename, rel))
    report.referenced_count = len(referenced)

    async for attach in yak_dir.rglob(ATTACHMENTS_DIRNAME):
        if not await attach.is_dir():
            continue
        category = attach.parent.name
        async for pth in attach.iterdir():
            if not await pth.is_file():
                continue
            report.file_count += 1
            if (category, pth.name) not in referenced:
                size_kb = (await pth.stat()).st_size // 1024
                report.orphans.append((category, pth.name, size_kb))
    return report
