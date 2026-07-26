"""Tests for template helper functions."""

import re

from yak_shears._templates import _LIGHTNESSES, _SATURATIONS, get_category_color

_HSL_RE = re.compile(r"^hsl\((\d{1,3}), (\d{1,3})%, (\d{1,3})%\)$")


def test_category_color_empty_uses_border() -> None:
    assert get_category_color("") == "var(--color-border)"


def test_category_color_is_valid_hsl() -> None:
    match = _HSL_RE.match(get_category_color("personal"))
    assert match
    hue, sat, light = (int(g) for g in match.groups())
    assert 0 <= hue < 360
    assert sat in _SATURATIONS
    assert light in _LIGHTNESSES


def test_category_color_is_deterministic() -> None:
    assert get_category_color("evergreen") == get_category_color("evergreen")


def test_category_color_varies_by_name() -> None:
    colors = {get_category_color(name) for name in ("personal", "evergreen", "work", "test")}
    assert len(colors) > 1
