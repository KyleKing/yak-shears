"""Playwright fixtures."""

import asyncio
import time
from contextlib import suppress
from pathlib import Path as SyncPath

import httpx
import pytest
import pytest_asyncio
from playwright.async_api import ConsoleMessage, Page

PORT = "8081"
BASE_URL = f"http://localhost:{PORT}"

PLAYWRIGHT_AUTH_PATH = ".playwright-auth.json"
(SyncPath(__file__).absolute().parents[2] / PLAYWRIGHT_AUTH_PATH).write_text("{}")


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Configure browser context for testing.

    Docs: https://playwright.dev/docs/api/class-browser#browser-new-context

    """
    return {
        "storage_state": PLAYWRIGHT_AUTH_PATH,
        **browser_context_args,
    }


@pytest.fixture(scope="session")
def base_url():
    """Overrides https://github.com/pytest-dev/pytest-base-url."""
    return BASE_URL


async def check_connection(*, timeout_s: float, url: str) -> None:
    start = time.monotonic()
    async with httpx.AsyncClient() as client:

        async def _is_reachable() -> bool:
            with suppress(httpx.ConnectError):
                await client.get(url)
                return True
            return False

        while not await _is_reachable():
            if (start - time.monotonic()) >= timeout_s:
                msg = f"Failed to connect to {url} within the {timeout_s}s timeout"
                raise RuntimeError(msg)
            await asyncio.sleep(0.5)


@pytest_asyncio.fixture(scope="session")
async def server_lifecycle():
    """Start and stop the server."""
    process = await asyncio.create_subprocess_exec("uv", "run", "serve", "--port", PORT)
    await check_connection(timeout_s=5, url=BASE_URL)
    try:
        yield
    finally:
        if process.returncode is None:
            process.kill()
        await process.wait()


class Messages:
    """Collects console messages."""

    def __init__(self) -> None:
        """Initialized captured messages."""
        self.captured: list[str] = []

    def handler(self, msg: ConsoleMessage) -> None:
        """Use with `page.on("console", ...)`."""
        self.captured.append(f"{msg.type}: {msg.text}")


@pytest_asyncio.fixture
async def console_messages(page: Page):  # noqa: RUF029 - required to be async for event loop!
    """Collect console messages."""
    messages = Messages()
    page.on("console", messages.handler)
    return messages


@pytest.fixture(autouse=True)
def check_console_errors(console_messages):
    """Fail test if there are console errors."""
    yield
    console_errors = [msg for msg in console_messages.captured if msg.startswith("error:")]
    assert len(console_errors) == 0, f"Console errors: {console_errors}"
