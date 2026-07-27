"""Tests for category color slots and their vault-adjacent mapping."""

import json
import re
from itertools import pairwise

import pytest
from anyio import Path

from yak_shears._yak.categories import (
    PALETTE,
    UNASSIGNED_COLOR,
    assign_slots,
    config_path,
    load_slots,
    resolve_colors,
    save_slots,
    slot_css,
)

_HSL_RE = re.compile(r"^hsl\((\d{1,3}), (\d{1,3})%, (\d{1,3})%\)$")

# The band reserved for armed amber, which must never also mean "a category".
_AMBER_LOW, _AMBER_HIGH = 25, 55

# Below this the two caps read as shades of one color rather than two categories.
_MIN_HUE_GAP = 30


def _hue(slot_name: str) -> int:
    match = _HSL_RE.match(slot_css(slot_name))
    assert match
    return int(match.group(1))


def test_palette_names_are_unique() -> None:
    assert len({slot.name for slot in PALETTE}) == len(PALETTE)


def test_no_palette_hue_lands_in_the_amber_band() -> None:
    assert all(not (_AMBER_LOW <= _hue(slot.name) <= _AMBER_HIGH) for slot in PALETTE)


def test_unknown_slot_falls_back_to_the_unassigned_neutral() -> None:
    assert slot_css("chartreuse") == UNASSIGNED_COLOR


def test_assignment_keeps_early_categories_far_apart() -> None:
    slots = assign_slots({}, ["evergreen", "notes-export", "personal", "tasks", "test"])
    hues = sorted(_hue(slot) for slot in slots.values())
    gaps = [second - first for first, second in pairwise(hues)]
    assert min(gaps) >= _MIN_HUE_GAP


def test_assignment_is_stable_when_a_category_is_added() -> None:
    original = assign_slots({}, ["personal", "tasks"])
    extended = assign_slots(original, ["personal", "tasks", "work"])
    assert {key: extended[key] for key in original} == original


def test_a_category_named_after_a_color_claims_that_slot() -> None:
    assert assign_slots({}, ["teal", "work"])["teal"] == "teal"


def test_a_taken_color_name_falls_through_to_the_spread() -> None:
    slots = assign_slots({"test": "teal"}, ["test", "teal"])
    assert slots["test"] == "teal"
    assert slots["teal"] != "teal"


def test_stored_entries_naming_an_unknown_slot_are_reassigned() -> None:
    assert assign_slots({"personal": "chartreuse"}, ["personal"])["personal"] in {slot.name for slot in PALETTE}


@pytest.mark.asyncio
async def test_missing_config_loads_as_empty(tmp_path) -> None:
    assert await load_slots(Path(tmp_path)) == {}


@pytest.mark.asyncio
async def test_malformed_config_loads_as_empty(tmp_path) -> None:
    path = config_path(Path(tmp_path))
    await path.parent.mkdir(parents=True)
    await path.write_text("[not an object]", encoding="utf-8")
    assert await load_slots(Path(tmp_path)) == {}


@pytest.mark.asyncio
async def test_slots_round_trip_through_the_vault(tmp_path) -> None:
    yak_dir = Path(tmp_path)
    await save_slots(yak_dir, {"tasks": "azure"})
    assert await load_slots(yak_dir) == {"tasks": "azure"}


@pytest.mark.asyncio
async def test_resolve_persists_newly_assigned_slots(tmp_path) -> None:
    yak_dir = Path(tmp_path)
    colors = await resolve_colors(yak_dir, ["personal", "tasks"])

    stored = json.loads(await config_path(yak_dir).read_text(encoding="utf-8"))
    assert set(stored) == {"personal", "tasks"}
    assert colors["personal"] == slot_css(stored["personal"])


@pytest.mark.asyncio
async def test_resolve_does_not_move_an_existing_assignment(tmp_path) -> None:
    yak_dir = Path(tmp_path)
    await save_slots(yak_dir, {"tasks": "olive"})

    colors = await resolve_colors(yak_dir, ["personal", "tasks"])

    assert colors["tasks"] == slot_css("olive")
