"""Check yak-shears' vendored JS pins, CDN pins, and Python deps for available updates.

Marker convention for CDN pins: a `<!-- freshness: npm <package> -->` comment placed directly
above the tag whose URL embeds `@<version>`.

Marker convention for intentionally held-back Python deps: a trailing `# freshness: hold` comment
on the dependency line in pyproject.toml. Held deps are omitted from the drift report.
"""

import argparse
import logging
import re
import sys
from pathlib import Path

from freshness.checkers import (
    CheckResult,
    extract_pin,
    fetch_github_commit,
    fetch_github_release,
    fetch_npm_latest,
    is_outdated,
    patch_pin,
    render_report,
    run_uv_outdated,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
DOWNLOAD_ASSETS = REPO_ROOT / "scripts" / "download-assets.sh"
EDIT_TEMPLATE = REPO_ROOT / "yak_shears" / "_templates" / "yak" / "edit.html.jinja"
PYPROJECT = REPO_ROOT / "pyproject.toml"

# Version must start with a digit so scoped package names (e.g. @djot/djot@0.3.2) don't get
# mistaken for the version at the "@" before the scope.
CDN_MARKER_PATTERN = re.compile(
    r"<!--\s*freshness:\s*npm\s+(\S+)\s*-->\s*\n.*?@(\d[\w.\-]*)",
)


def check_vendored() -> list[CheckResult]:
    """Check htmx/codejar pins in download-assets.sh, auto-patching the file on drift.

    Returns:
        One CheckResult per pinned dependency.

    """
    download_assets_relpath = str(DOWNLOAD_ASSETS.relative_to(REPO_ROOT))
    results = []

    current_htmx = extract_pin(DOWNLOAD_ASSETS, r"HTMX_VERSION:-([^}]+)")
    latest_htmx = fetch_github_release("bigskysoftware", "htmx")
    if current_htmx and latest_htmx:
        drifted = is_outdated(current_htmx, latest_htmx)
        if drifted:
            patch_pin(DOWNLOAD_ASSETS, current_htmx, latest_htmx)
        results.append(CheckResult("htmx", download_assets_relpath, current_htmx, latest_htmx, drifted))

    current_codejar = extract_pin(DOWNLOAD_ASSETS, r"CODEJAR_VERSION:-([^}]+)")
    latest_codejar = fetch_github_commit("antonmedv", "codejar", "master")
    if current_codejar and latest_codejar:
        drifted = is_outdated(current_codejar, latest_codejar)
        if drifted:
            patch_pin(DOWNLOAD_ASSETS, current_codejar, latest_codejar)
        results.append(CheckResult("codejar", download_assets_relpath, current_codejar, latest_codejar, drifted))

    return results


def check_cdn() -> list[CheckResult]:
    """Check npm-registry versions for each `<!-- freshness: npm ... -->`-marked CDN pin.

    Returns:
        One CheckResult per marked CDN pin.

    """
    results = []
    content = EDIT_TEMPLATE.read_text(encoding="utf-8")
    for match in CDN_MARKER_PATTERN.finditer(content):
        package, current = match.group(1), match.group(2)
        latest = fetch_npm_latest(package)
        if not latest:
            logger.warning("Could not fetch latest npm version for %s", package)
            continue
        drifted = is_outdated(current, latest)
        results.append(CheckResult(package, str(EDIT_TEMPLATE.relative_to(REPO_ROOT)), current, latest, drifted))
    return results


_HOLD_PATTERN = re.compile(r'^\s*"([\w.\-]+)[=><~!].*#\s*freshness:\s*hold\b', re.MULTILINE)
# `uv tree --outdated` prefixes each line with box-drawing tree characters, e.g.
# "│   ├── numpy v2.5.0 (latest: v2.5.1)" - search rather than anchor to line start.
_OUTDATED_LINE_PATTERN = re.compile(r"([a-zA-Z][\w.\-]*) v([\w.\-]+) \(latest: v?([\w.\-]+)\)")


def check_python() -> list[CheckResult]:
    """Check for outdated Python deps via `uv tree --outdated`, skipping `# freshness: hold` deps.

    Returns:
        One CheckResult per outdated, non-held dependency.

    """
    held = set(_HOLD_PATTERN.findall(PYPROJECT.read_text(encoding="utf-8")))
    output = run_uv_outdated()
    results = []
    for line in output.splitlines():
        match = _OUTDATED_LINE_PATTERN.search(line)
        if not match:
            continue
        name, current, latest = match.groups()
        if name in held:
            continue
        results.append(CheckResult(name, "pyproject.toml", current, latest, drifted=True))
    return results


def main() -> int:
    """Run the requested freshness checks and return a process exit code.

    Returns:
        0 if nothing drifted, 1 if any check found unheld drift.

    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vendored", action="store_true", help="Only check vendored JS pins (htmx, codejar)")
    parser.add_argument("--cdn", action="store_true", help="Only check CDN-pinned versions in templates")
    parser.add_argument("--python", action="store_true", help="Only check Python dependency versions via uv")
    args = parser.parse_args()

    run_all = not (args.vendored or args.cdn or args.python)
    results: list[CheckResult] = []
    if args.vendored or run_all:
        results += check_vendored()
    if args.cdn or run_all:
        results += check_cdn()
    if args.python or run_all:
        results += check_python()

    logger.info(render_report(results))
    return 1 if any(result.drifted for result in results) else 0


if __name__ == "__main__":
    sys.exit(main())
