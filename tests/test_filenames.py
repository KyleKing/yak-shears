"""Canonical filename detection and the Doctor migration that applies it."""

from datetime import UTC, datetime
from pathlib import Path as SyncPath

import pytest

from yak_shears._yak.filenames import (
    CANONICAL_FORMAT,
    apply_renames,
    canonical_stem,
    is_canonical,
    parse_stem,
    plan_renames,
)


@pytest.fixture
def vault(tmp_path: SyncPath) -> SyncPath:
    (tmp_path / "evergreen").mkdir()
    return tmp_path


@pytest.mark.parametrize(
    ("stem", "expected"),
    [
        ("2026-07-22T14_03_51Z", datetime(2026, 7, 22, 14, 3, 51, tzinfo=UTC)),
        ("20260722_140351", datetime(2026, 7, 22, 14, 3, 51, tzinfo=UTC)),
        ("2026-07-22T14_03_51", datetime(2026, 7, 22, 14, 3, 51, tzinfo=UTC)),
        ("20260722T140351Z", datetime(2026, 7, 22, 14, 3, 51, tzinfo=UTC)),
        ("meeting-notes", None),
        ("", None),
        ("2026-13-45T99_99_99Z", None),
    ],
)
def test_parse_stem(stem: str, expected: datetime | None) -> None:
    assert parse_stem(stem) == expected


@pytest.mark.parametrize(
    ("stem", "expected"),
    [
        ("2026-07-22T14_03_51Z", True),
        ("20260722_140351", False),
        ("2026-07-22T14_03_51", False),
        ("groceries", False),
    ],
)
def test_is_canonical(stem: str, expected: bool) -> None:
    assert is_canonical(stem) is expected


def test_canonical_stem_normalises_to_utc() -> None:
    from datetime import timedelta, timezone

    eastern = timezone(timedelta(hours=-4))
    local = datetime(2026, 7, 22, 10, 3, 51, tzinfo=eastern)
    assert canonical_stem(local) == "2026-07-22T14_03_51Z"
    assert datetime.strptime(canonical_stem(local), CANONICAL_FORMAT).year == 2026


def test_plan_sorts_files_into_the_right_buckets(vault: SyncPath) -> None:
    (vault / "evergreen/2026-07-22T14_03_51Z.dj").write_text("canonical")
    (vault / "evergreen/20250930_153525.dj").write_text("legacy")
    (vault / "evergreen/meeting-notes.dj").write_text("hand named")

    report = plan_renames(vault)

    assert report.canonical == ["evergreen/2026-07-22T14_03_51Z.dj"]
    assert report.unparseable == ["evergreen/meeting-notes.dj"]
    assert [rename.new_path for rename in report.renames] == ["evergreen/2025-09-30T15_35_25Z.dj"]
    assert report.needs_migration is True


def test_plan_blocks_a_rename_that_would_collide(vault: SyncPath) -> None:
    (vault / "evergreen/20250930_153525.dj").write_text("legacy")
    (vault / "evergreen/2025-09-30T15_35_25Z.dj").write_text("already there")

    report = plan_renames(vault)

    assert report.renames == []
    assert [rename.old_path for rename in report.blocked] == ["evergreen/20250930_153525.dj"]


def test_empty_vault_needs_no_migration(vault: SyncPath) -> None:
    report = plan_renames(vault)
    assert report.needs_migration is False
    assert report.canonical == []


def test_apply_renames_moves_files_and_repoints_wikilinks(vault: SyncPath) -> None:
    (vault / "evergreen/20250930_153525.dj").write_text("the target note")
    (vault / "evergreen/2026-07-22T14_03_51Z.dj").write_text(
        "see [[20250930_153525]] and [[20250930_153525|the old one]] and [[elsewhere]]"
    )

    result = apply_renames(vault, plan_renames(vault).renames)

    assert not (vault / "evergreen/20250930_153525.dj").exists()
    assert (vault / "evergreen/2025-09-30T15_35_25Z.dj").read_text() == "the target note"
    assert result.relinked == ["evergreen/2026-07-22T14_03_51Z.dj"]

    linker = (vault / "evergreen/2026-07-22T14_03_51Z.dj").read_text()
    assert "[[2025-09-30T15_35_25Z]]" in linker
    assert "[[2025-09-30T15_35_25Z|the old one]]" in linker
    assert "[[elsewhere]]" in linker


def test_apply_renames_leaves_unrelated_notes_untouched(vault: SyncPath) -> None:
    (vault / "evergreen/20250930_153525.dj").write_text("target")
    untouched = vault / "evergreen/meeting-notes.dj"
    untouched.write_text("no links here")

    result = apply_renames(vault, plan_renames(vault).renames)

    assert result.relinked == []
    assert untouched.read_text() == "no links here"


def test_renamed_files_sort_correctly_against_canonical_siblings(vault: SyncPath) -> None:
    # The reason to migrate at all. `paginate_yaks` orders SortBy.CREATED_AT by
    # filename descending, so the newest note should come first. "-" sorts below
    # the digits, so a compact January name beats an ISO December one and the
    # older note is listed as the newer.
    (vault / "evergreen/20260101_000000.dj").write_text("january")
    (vault / "evergreen/2026-12-31T23_59_59Z.dj").write_text("december")

    def newest_first() -> list[str]:
        return sorted((pth.name for pth in (vault / "evergreen").iterdir()), reverse=True)

    assert newest_first()[0] == "20260101_000000.dj"

    apply_renames(vault, plan_renames(vault).renames)

    assert newest_first() == ["2026-12-31T23_59_59Z.dj", "2026-01-01T00_00_00Z.dj"]


def test_apply_renames_raises_when_a_planned_file_disappeared(vault: SyncPath) -> None:
    (vault / "evergreen/20250930_153525.dj").write_text("legacy")
    planned = plan_renames(vault).renames
    (vault / "evergreen/20250930_153525.dj").unlink()

    with pytest.raises(FileNotFoundError):
        apply_renames(vault, planned)
