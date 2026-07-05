"""Reusable, project-agnostic helpers for checking whether pinned dependency versions are stale.

Intended to be copied as-is into other repos' `scripts/` directories; a project supplies its own
thin registry/CLI (see yak-shears' `scripts/check_freshness.py`) that imports these functions.
"""

import json
import re
import subprocess  # noqa: S404
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

_PRERELEASE_TAG_PATTERN = re.compile(r"-(alpha|beta|rc|pre)\d*$", re.IGNORECASE)


def fetch_github_release(owner: str, repo: str) -> str | None:
    """Fetch the latest stable release tag for a GitHub repo, stripped of a leading 'v'.

    Filters out releases that look like a pre-release by tag name (e.g. `-beta5`), since some
    projects don't set GitHub's `prerelease` flag accurately on their own release endpoint.

    Returns:
        The latest stable tag, or None if the repo/network call is unavailable.

    """
    url = f"https://api.github.com/repos/{owner}/{repo}/releases?per_page=10"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github.v3+json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as response:  # noqa: S310
            releases = json.load(response)
    except urllib.error.URLError:
        return None
    for release in releases:
        tag = release.get("tag_name", "")
        if release.get("prerelease") or release.get("draft") or _PRERELEASE_TAG_PATTERN.search(tag):
            continue
        return tag.lstrip("v") or None
    return None


def fetch_github_commit(owner: str, repo: str, branch: str = "master") -> str | None:
    """Fetch the latest commit SHA on a branch of a GitHub repo.

    Returns:
        The latest commit SHA, or None if the repo/network call is unavailable.

    """
    url = f"https://api.github.com/repos/{owner}/{repo}/commits/{branch}"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github.v3+json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as response:  # noqa: S310
            data = json.load(response)
    except urllib.error.URLError:
        return None
    return data.get("sha")


def fetch_npm_latest(package: str) -> str | None:
    """Fetch the latest published version of an npm package.

    Returns:
        The latest version string, or None if the registry call is unavailable.

    """
    url = f"https://registry.npmjs.org/{package}/latest"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.load(response)
    except urllib.error.URLError:
        return None
    return data.get("version")


def _semver_parts(version: str) -> list[int] | None:
    parts = re.findall(r"\d+", version)
    return [int(part) for part in parts] if parts else None


def is_outdated(current: str, latest: str) -> bool:
    """Return True if `latest` is newer than `current`.

    Falls back to inequality for non-semver strings (e.g. commit SHAs).
    """
    if current == latest:
        return False
    current_parts, latest_parts = _semver_parts(current), _semver_parts(latest)
    if current_parts is None or latest_parts is None:
        return True
    return latest_parts > current_parts


def extract_pin(file_path: Path, pattern: str) -> str | None:
    """Extract the first capture group of `pattern` from a file's contents.

    Returns:
        The captured group, or None if the pattern doesn't match.

    """
    match = re.search(pattern, file_path.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def patch_pin(file_path: Path, old: str, new: str) -> None:
    """Replace the first literal occurrence of `old` with `new` in a file, in place."""
    content = file_path.read_text(encoding="utf-8")
    file_path.write_text(content.replace(old, new, 1), encoding="utf-8")


def run_uv_outdated() -> str:
    """Return the raw output of `uv tree --outdated --universal`."""
    result = subprocess.run(
        ["uv", "tree", "--outdated", "--universal"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout


@dataclass(frozen=True)
class CheckResult:
    """The outcome of comparing one pinned version against its latest upstream value."""

    name: str
    file: str
    current: str
    latest: str
    drifted: bool
    note: str = ""


def render_report(results: list[CheckResult]) -> str:
    """Render a human-readable, line-per-result freshness report.

    Returns:
        The report text, one line (plus an optional note line) per result.

    """
    lines = []
    for result in results:
        status = "OUTDATED" if result.drifted else "up to date"
        lines.append(f"[{status}] {result.name} ({result.file}): {result.current} -> {result.latest}")
        if result.note:
            lines.append(f"    {result.note}")
    return "\n".join(lines)
