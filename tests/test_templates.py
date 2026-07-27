"""Tests for template helper functions."""

from yak_shears._templates import color_lookup
from yak_shears._yak.categories import UNASSIGNED_COLOR, slot_css


def test_color_lookup_unknown_category_uses_border() -> None:
    assert color_lookup({})("personal") == UNASSIGNED_COLOR


def test_color_lookup_returns_the_assigned_color() -> None:
    assert color_lookup({"personal": slot_css("teal")})("personal") == slot_css("teal")
