"""Tests for the static asset budget.

DESIGN.md asserted a 14KB budget long before anything measured it, and the
figure was never met. It is a test now so the documented number stays
answerable to the file that ships.
"""

import gzip
from pathlib import Path as SyncPath

MAIN_CSS = SyncPath(__file__).absolute().parents[1] / "yak_shears/static/css/main.css"

# Render-blocking CSS, gzipped, as served. Raise this deliberately and only
# with a reason: it is the one asset that blocks first paint on every route.
CSS_BUDGET_BYTES = 22 * 1024


def test_css_stays_within_budget() -> None:
    """The render-blocking stylesheet fits the documented budget."""
    compressed = len(gzip.compress(MAIN_CSS.read_bytes(), mtime=0))
    assert compressed <= CSS_BUDGET_BYTES, (
        f"main.css is {compressed / 1024:.1f} KB gzipped, over the {CSS_BUDGET_BYTES / 1024:.0f} KB budget. "
        f"Cut rules or raise CSS_BUDGET_BYTES on purpose."
    )
