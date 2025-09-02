# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "httpx>=0.28.1",
# ]
# ///
"""Download and verify CDN assets with checksum validation.

```sh
# Requirements specified with.
uv add --script scripts/download_static_assets.py 'httpx>=0.28.1'
# Then run with:
uv run scripts/download_static_assets.py
```

"""

import hashlib
import sys
from pathlib import Path
from typing import NamedTuple

import httpx


class Asset(NamedTuple):
    """CDN asset configuration."""

    url: str
    local_path: Path
    expected_sha256: str


ASSETS = [
    Asset(
        url="https://cdn.jsdelivr.net/npm/alpinejs@3.14.1/dist/cdn.min.js",
        local_path=Path("yak_shears/static/js/alpine.min.js"),
        expected_sha256="358d9afbb1ab5befa2f48061a30776e5bcd7707f410a606ba985f98bc3b1c034",
    ),
    Asset(
        url="https://cdn.jsdelivr.net/npm/@imacrayon/alpine-ajax@0.12.4/dist/cdn.min.js",
        local_path=Path("yak_shears/static/js/alpine-ajax.min.js"),
        expected_sha256="e59b94a0cfed67f5e4d5a3db2cb0135eb929ff9f3dffc5b48e36cd170acbe1e1",
    ),
]


def calculate_sha256(content: bytes) -> str:
    """Return SHA256 hash of content."""
    return hashlib.sha256(content).hexdigest()


def download_asset(asset: Asset) -> None:
    """Download and verify an asset."""
    with httpx.Client(timeout=30.0) as client:
        response = client.get(asset.url)
        response.raise_for_status()
        content = response.content

    if (actual_sha256 := calculate_sha256(content)) != asset.expected_sha256:
        err_msg = f"Checksum mismatch: {actual_sha256} != {asset.expected_sha256}"
        raise ValueError(err_msg)

    asset.local_path.parent.mkdir(parents=True, exist_ok=True)
    asset.local_path.write_bytes(content)


def main(assets: list[Asset]) -> int:
    """Returns shell exit code 0 if downloads are successful."""
    for asset in assets:
        if not asset.local_path.exists():
            print(f"Downloading asset to {asset.local_path}")  # noqa: T201
            download_asset(asset)
    return 0


if __name__ == "__main__":
    sys.exit(main(ASSETS))
