"""Category color slots and the vault-adjacent mapping that pins them."""

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from anyio import Path

from yak_shears._log_utils import log


@dataclass(frozen=True)
class ColorSlot:
    """One anodize color a category can be assigned to."""

    name: str
    css: str


# Twelve anodize colors for the category caps. Hues 25-55 are left out on
# purpose: that band is armed amber, which means "this action will fire" and
# must not also mean "this note is filed under tasks".
PALETTE: tuple[ColorSlot, ...] = (
    ColorSlot("clay", "hsl(16, 72%, 58%)"),
    ColorSlot("rose", "hsl(352, 68%, 62%)"),
    ColorSlot("pink", "hsl(328, 62%, 64%)"),
    ColorSlot("mauve", "hsl(302, 52%, 62%)"),
    ColorSlot("violet", "hsl(276, 58%, 64%)"),
    ColorSlot("indigo", "hsl(250, 62%, 62%)"),
    ColorSlot("azure", "hsl(216, 72%, 56%)"),
    ColorSlot("sky", "hsl(196, 74%, 50%)"),
    ColorSlot("teal", "hsl(174, 62%, 44%)"),
    ColorSlot("moss", "hsl(150, 52%, 46%)"),
    ColorSlot("fern", "hsl(118, 46%, 48%)"),
    ColorSlot("olive", "hsl(72, 52%, 46%)"),
)

_BY_NAME = {slot.name: slot for slot in PALETTE}

# Walking the palette in order would hand the first few categories neighbouring
# hues, which is exactly the confusion this replaced. Stepping by 5 through 12
# slots visits every one of them while keeping consecutive picks far apart.
_ASSIGN_STEP = 5
_ASSIGN_ORDER: tuple[str, ...] = tuple(
    PALETTE[(index * _ASSIGN_STEP) % len(PALETTE)].name for index in range(len(PALETTE))
)

CONFIG_DIRNAME = ".yak-shears"
CONFIG_FILENAME = "categories.json"

UNASSIGNED_COLOR = "var(--color-border)"


def slot_css(slot_name: str) -> str:
    """CSS color for a palette slot.

    Returns:
        The slot's CSS color, or the unassigned neutral for an unknown name.
    """
    slot = _BY_NAME.get(slot_name)
    return slot.css if slot else UNASSIGNED_COLOR


def assign_slots(stored: Mapping[str, str], categories: Iterable[str]) -> dict[str, str]:
    """Extend a stored category-to-slot mapping to cover `categories`.

    Existing assignments are never moved, so a category keeps its color for the
    life of the vault. A category named after a palette slot claims that slot
    when it is free; everything else takes the next free slot in spread order.

    Returns:
        The stored mapping plus an entry for every previously unassigned category.
    """
    assigned = {category: slot for category, slot in stored.items() if slot in _BY_NAME}
    taken = set(assigned.values())
    pending = sorted(category for category in categories if category and category not in assigned)

    for category in pending:
        if category in _BY_NAME and category not in taken:
            assigned[category] = category
            taken.add(category)

    free = [name for name in _ASSIGN_ORDER if name not in taken]
    for index, category in enumerate(category for category in pending if category not in assigned):
        # Past twelve categories the wheel is exhausted and slots repeat, which
        # is honest: two categories share a color rather than drifting into two
        # shades of the same one.
        assigned[category] = free[index] if index < len(free) else _ASSIGN_ORDER[index % len(_ASSIGN_ORDER)]

    return assigned


def config_path(yak_dir: Path) -> Path:
    """Locate the category color mapping inside a vault.

    Returns:
        Path of the mapping file, whether or not it exists.
    """
    return yak_dir / CONFIG_DIRNAME / CONFIG_FILENAME


async def load_slots(yak_dir: Path) -> dict[str, str]:
    """Read the stored category-to-slot mapping.

    Returns:
        The stored mapping, or an empty one if it is absent or unreadable.
    """
    path = config_path(yak_dir)
    if not await path.is_file():
        return {}
    try:
        raw = json.loads(await path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        log(f"WARNING: Could not read {path}: {err}")
        return {}
    if not isinstance(raw, dict):
        log(f"WARNING: Ignoring {path}: expected an object of category to color")
        return {}
    return {str(category): str(slot) for category, slot in raw.items()}


async def save_slots(yak_dir: Path, slots: Mapping[str, str]) -> None:
    """Write the category-to-slot mapping into the vault."""
    path = config_path(yak_dir)
    await path.parent.mkdir(parents=True, exist_ok=True)
    ordered = {category: slots[category] for category in sorted(slots)}
    await path.write_text(json.dumps(ordered, indent=2) + "\n", encoding="utf-8")


async def resolve_colors(yak_dir: Path, categories: Iterable[str]) -> dict[str, str]:
    """Category-to-CSS-color map, persisting any slots assigned on the way.

    Returns:
        A mapping from category name to a CSS color string.
    """
    categories = list(categories)
    stored = await load_slots(yak_dir)
    slots = assign_slots(stored, categories)
    if slots != stored:
        try:
            await save_slots(yak_dir, slots)
        except OSError as err:
            log(f"WARNING: Could not persist category colors: {err}")
    return {category: slot_css(slot) for category, slot in slots.items()}
