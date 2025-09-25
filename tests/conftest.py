"""Pytest configuration."""

import asyncio
import tempfile
from pathlib import Path
from typing import Literal
from unittest.mock import patch

import pytest
import pytest_asyncio
from playwright.async_api import Page

from yak_shears.auth import handlers
from yak_shears.auth.models import HashedPassword, Password, User
from yak_shears.auth.storage import create_user


@pytest.fixture
def temp_user_file():
    """Create a temporary user file for testing.

    Yields:
        Path: The path to the temporary user file
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as _f:
        temp_path = Path(_f.name)
        _f.write('{"users": {}, "email_to_user_id": {}, "sessions": {}}')

    with (
        patch("yak_shears.auth.storage._USER_DATA_PATH", temp_path),
        patch("yak_shears.auth.storage._USERS", {}),
        patch("yak_shears.auth.storage._EMAIL_TO_USER_ID", {}),
        patch("yak_shears.auth.storage._SESSION_STORE", {}),
    ):
        yield temp_path

    temp_path.unlink(missing_ok=True)


SAMPLE_USER_EMAIL = "test@example.com"
SAMPLE_USER_PASSWORD = Password("secure123")


@pytest.fixture
def sample_user(temp_user_file) -> dict[Literal["id"], str]:
    """Create the sample user for testing.

    Returns:
        dict[Literal["id"], str]: A dictionary containing the user ID
    """
    display_name = "Test User"
    user = create_user(SAMPLE_USER_EMAIL, display_name, SAMPLE_USER_PASSWORD)
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


# ------------------------------------------------------------------------------
# Playwright fixtures
# ------------------------------------------------------------------------------

PORT = "8081"
BASE_URL = f"http://localhost:{PORT}"


@pytest_asyncio.fixture(scope="session")
async def server_lifecycle():
    """Start and stop the server."""
    # PLANNED: Will this error when incorrect?
    process = await asyncio.create_subprocess_exec(
        # FIXME: Remove reload & no-auth
        #  https://www.google.com/search?q=save%20cookies%20python%20playwright%20auth
        "uv",
        "run",
        "serve",
        "--no-auth",
        "--reload",
        "--port",
        PORT,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # PLANNED: Maybe check for availability?
    #  urllib.request.urlopen(BASE_URL).getcode() == 200  # noqa: ERA001
    await asyncio.sleep(2)

    try:
        yield
    finally:
        process.terminate()
        await process.wait()


@pytest.fixture(scope="session")
def base_url():
    """Overrides https://github.com/pytest-dev/pytest-base-url."""
    return BASE_URL


@pytest_asyncio.fixture
async def console_messages(page: Page):  # noqa: RUF029 - required for event loop!
    """Collect console messages."""
    messages = []

    def handler(msg):
        messages.append(f"{msg.type}: {msg.text}")

    page.on("console", handler)
    return messages


@pytest.fixture
def console_errors(console_messages):
    """Filter console errors."""
    return [msg for msg in console_messages if msg.startswith("error:")]


@pytest.fixture(autouse=True)
def check_console_errors(console_errors):
    """Fail test if there are console errors."""
    yield
    assert len(console_errors) == 0, f"Console errors: {console_errors}"
