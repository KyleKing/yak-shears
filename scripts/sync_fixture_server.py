"""Serve the real app over a throwaway vault, for the Swift sync engine's integration tests.

Everything lives in a temporary directory: the vault, the user store with the
documented test user, the signing secret, and the search index. Nothing touches
the developer's own vault or `.yak-shears-users.json`.

    uv run python scripts/sync_fixture_server.py --port 8765
    YAK_SHEARS_TEST_SERVER=http://127.0.0.1:8765 swift test --package-path apple/YakShearsKit
"""

import argparse
import asyncio
import os
import tempfile
from pathlib import Path

import uvicorn

from yak_shears._auth.models import Password  # ruff: ignore[import-private-name]
from yak_shears._auth.storage import UserStore, _set_default_store  # ruff: ignore[import-private-name]
from yak_shears._log_utils import log  # ruff: ignore[import-private-name]

TEST_EMAIL = "test@example.com"
TEST_PASSWORD = Password("secure123")


async def _serve(port: int) -> None:
    with tempfile.TemporaryDirectory(prefix="yak-sync-fixture-") as scratch:
        root = Path(scratch)
        vault = root / "vault"
        vault.mkdir()
        os.environ["YAK_SHEARS_DIR"] = vault.as_posix()
        os.environ["SEARCH_DB_DIR"] = (root / "index").as_posix()

        store = UserStore(root / "users.json")
        await store.create_user(TEST_EMAIL, "Test User", TEST_PASSWORD)
        _set_default_store(store)

        # Imported only once the test store is in place.
        from yak_shears.server._routes import create_app  # ruff: ignore[import-outside-top-level, import-private-name]

        log(f"Serving {vault} on http://127.0.0.1:{port}")
        await uvicorn.Server(uvicorn.Config(create_app(), host="127.0.0.1", port=port, log_level="warning")).serve()


def main() -> None:
    """Parse the port and serve until interrupted."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8765)
    asyncio.run(_serve(parser.parse_args().port))


if __name__ == "__main__":
    main()
