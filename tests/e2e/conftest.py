"""Playwright fixtures."""

import asyncio
import time
from asyncio.subprocess import PIPE
from contextlib import suppress

import httpx
import pytest
import pytest_asyncio
from playwright.async_api import Page

PORT = "8082"
BASE_URL = f"http://localhost:{PORT}"


@pytest_asyncio.fixture(scope="session")
async def server_lifecycle():
    """Start and stop the server."""
    process = await asyncio.create_subprocess_exec("uv", "run", "serve", "--port", PORT, stdout=PIPE, stderr=PIPE)

    timeout_s = 5
    start = time.monotonic()
    async with httpx.AsyncClient() as client:

        async def is_reachable() -> bool:
            with suppress(httpx.ConnectError):
                await client.get(BASE_URL)
                return True
            return False

        while not await is_reachable():
            if (start - time.monotonic()) >= timeout_s:
                raise RuntimeError("Failed to connect within the timeout")
            await asyncio.sleep(0.5)

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
async def console_messages(page: Page):  # noqa: RUF029 - required to be async for event loop!
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
