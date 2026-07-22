"""Canonical yak filenames and the migration for older ones.

Yaks are named after their creation instant in UTC, e.g.
``2026-07-22T14_03_51Z.dj``. Earlier versions wrote ``20260722_140351.dj``, and
the two shapes do not sort together: ``-`` sorts below the digits, so within a
single year every compact name outranks every ISO one.

Rather than teach the listing sort to parse both shapes, the files themselves
are migrated so a plain filename sort stays correct. That keeps the cost in a
one-off Doctor action instead of on every page render.

Names that are not a timestamp in a known format are reported and left alone. A
hand-written filename is a deliberate choice, not a defect.
"""

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path as SyncPath

CANONICAL_FORMAT = "%Y-%m-%dT%H_%M_%SZ"

# Ordered most-specific first. Every one is interpreted as UTC, which is what
# create_yak has always written regardless of the shape it used.
_LEGACY_FORMATS = (
    "%Y-%m-%dT%H_%M_%S",
    "%Y%m%d_%H%M%S",
    "%Y%m%dT%H%M%SZ",
    "%Y%m%dT%H%M%S",
)

_CANONICAL_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}_\d{2}_\d{2}Z$")


def canonical_stem(moment: datetime) -> str:
    """Return the canonical filename stem for an instant."""
    return moment.astimezone(UTC).strftime(CANONICAL_FORMAT)


def is_canonical(stem: str) -> bool:
    """Whether a filename stem already matches the canonical shape."""
    return bool(_CANONICAL_RE.match(stem))


def parse_stem(stem: str) -> datetime | None:
    """Parse a filename stem written in the canonical or any legacy shape.

    Returns:
        The UTC instant the name encodes, or None when it is not a timestamp.
    """
    for fmt in (CANONICAL_FORMAT, *_LEGACY_FORMATS):
        try:
            return datetime.strptime(stem, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


@dataclass(frozen=True)
class Rename:
    """One planned rename, in vault-relative posix form."""

    old_path: str
    new_path: str
    old_stem: str
    new_stem: str


@dataclass
class FilenameReport:
    """What a scan of the vault found.

    ``blocked`` holds renames that would land on a name already in use; they are
    reported rather than resolved, because two notes claiming one instant is a
    situation for a human to look at.
    """

    canonical: list[str] = field(default_factory=list)
    renames: list[Rename] = field(default_factory=list)
    blocked: list[Rename] = field(default_factory=list)
    unparseable: list[str] = field(default_factory=list)

    @property
    def needs_migration(self) -> bool:
        """Whether any file can be renamed right now."""
        return bool(self.renames)


def plan_renames(yak_dir: SyncPath) -> FilenameReport:
    """Scan the vault and decide which yaks should be renamed."""
    report = FilenameReport()
    paths = sorted(pth for pth in yak_dir.rglob("*.dj") if pth.is_file())
    taken = {pth.relative_to(yak_dir).as_posix() for pth in paths}

    for path in paths:
        rel = path.relative_to(yak_dir).as_posix()
        stem = path.stem
        if is_canonical(stem):
            report.canonical.append(rel)
            continue

        moment = parse_stem(stem)
        if moment is None:
            report.unparseable.append(rel)
            continue

        new_stem = canonical_stem(moment)
        new_rel = (path.parent / f"{new_stem}.dj").relative_to(yak_dir).as_posix()
        rename = Rename(old_path=rel, new_path=new_rel, old_stem=stem, new_stem=new_stem)
        if new_rel in taken:
            report.blocked.append(rename)
        else:
            report.renames.append(rename)
            taken.add(new_rel)

    return report


def _rewrite_wikilinks(content: str, stem_map: dict[str, str]) -> str:
    """Point ``[[old-stem]]`` at the new stem, preserving any display alias."""
    if not stem_map:
        return content

    def _replace(match: re.Match[str]) -> str:
        target = match.group(1).strip()
        alias = match.group(2)
        renamed = stem_map.get(target)
        if renamed is None:
            return match.group(0)
        return f"[[{renamed}|{alias.strip()}]]" if alias else f"[[{renamed}]]"

    return re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", _replace, content)


@dataclass(frozen=True)
class MigrationResult:
    """Outcome of applying a rename plan."""

    renamed: list[Rename]
    relinked: list[str]


def apply_renames(yak_dir: SyncPath, renames: list[Rename]) -> MigrationResult:
    """Rename the planned files and repoint wikilinks that named their stems.

    Files are renamed first and links rewritten afterwards, so a failure partway
    leaves stale links (which the Doctor already reports) rather than links
    pointing at files that were never moved.

    Raises:
        FileNotFoundError: If a planned source file is no longer present.
    """
    done: list[Rename] = []
    for rename in renames:
        source = yak_dir / rename.old_path
        target = yak_dir / rename.new_path
        if not source.is_file():
            msg = f"Yak vanished before rename: {rename.old_path}"
            raise FileNotFoundError(msg)
        if target.exists():
            continue
        source.rename(target)
        done.append(rename)

    stem_map = {rename.old_stem: rename.new_stem for rename in done}
    relinked: list[str] = []
    for path in sorted(pth for pth in yak_dir.rglob("*.dj") if pth.is_file()):
        content = path.read_text(encoding="utf-8")
        rewritten = _rewrite_wikilinks(content, stem_map)
        if rewritten != content:
            path.write_text(rewritten, encoding="utf-8")
            relinked.append(path.relative_to(yak_dir).as_posix())

    return MigrationResult(renamed=done, relinked=relinked)
