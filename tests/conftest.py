"""Pytest configuration."""

import os
import tempfile
from collections.abc import AsyncGenerator, Generator
from contextlib import contextmanager
from pathlib import Path as SyncPath
from typing import Literal
from unittest.mock import patch

import pytest
import pytest_asyncio
from anyio import Path

from yak_shears._auth import handlers
from yak_shears._auth.models import HashedPassword, Password, User
from yak_shears._auth.storage import UserStore, _set_default_store, create_user

MOCK_YAK_DIR = SyncPath(__file__).parent / "test_data/mock_djot_dir_0"


@pytest.fixture(scope="session")
def worker_id() -> str:
    """Get the pytest-xdist worker ID for parallel test isolation.

    Returns:
        str: Worker ID (e.g., 'gw0', 'gw1') or 'master' for non-parallel runs
    """
    return os.environ.get("PYTEST_XDIST_WORKER", "master")


@pytest.fixture(scope="session")
def worker_num(worker_id: str) -> int:
    """Get the numeric worker index for parallel test isolation.

    Args:
        worker_id: The worker ID from pytest-xdist

    Returns:
        int: Worker number (0 for master, 1+ for parallel workers)
    """
    return 0 if worker_id == "master" else int(worker_id.replace("gw", ""))


@contextmanager
def set_yak_shears_dir(dir_path: SyncPath) -> Generator[None, None, None]:
    """Context manager to temporarily set the `YAK_SHEARS_DIR` environment variable."""
    with patch.dict(os.environ, {"YAK_SHEARS_DIR": dir_path.as_posix()}, clear=True):
        yield


@pytest_asyncio.fixture
async def temp_user_file(worker_id: str) -> AsyncGenerator[Path, None]:
    """Create a temporary user store for testing.

    Uses worker-specific file for parallel test isolation.

    Args:
        worker_id: The worker ID from pytest-xdist

    Yields:
        Path: The path to the temporary user file
    """
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=f"_{worker_id}.json",
        delete=False,
        encoding="utf-8",
    ) as _f:
        temp_path = Path(_f.name)
        _f.write('{"users": {}, "email_to_user_id": {}}')

    test_store = UserStore(SyncPath(temp_path))
    _set_default_store(test_store)

    yield temp_path

    await temp_path.unlink(missing_ok=True)


SAMPLE_USER_EMAIL = "test@example.com"
SAMPLE_USER_PASSWORD = Password("secure123")


@pytest_asyncio.fixture
async def sample_user(temp_user_file: Path) -> dict[Literal["id"], str]:
    """Create the sample user for testing.

    Returns:
        dict[Literal["id"], str]: A dictionary containing the user ID
    """
    display_name = "Test User"
    user = await create_user(SAMPLE_USER_EMAIL, display_name, SAMPLE_USER_PASSWORD)
    return {"id": user["id"]}


@pytest.fixture
def mock_user_session():
    """Fixture to patch `get_user_from_session` and provide a mock user.

    Yields:
        User: A mock user object
    """
    with patch.object(handlers, "get_user_from_session") as mock_get_user:
        mock_user = User(
            {
                "id": "test_user_id",
                "email": "test@web.site",
                "display_name": "Test User",
                "password_hash": HashedPassword("123"),
                "salt": "abc",
                "created_at": "2025-05-30T19:52:12.943795+00:00",
                "last_login": None,
            }
        )
        mock_get_user.return_value = mock_user
        yield mock_get_user
