"""Playwright fixtures."""

import asyncio
import os
import shutil
import time
from contextlib import suppress
from pathlib import Path as SyncPath

import httpx
import pytest
import pytest_asyncio
from playwright.async_api import ConsoleMessage, Page

from tests.conftest import MOCK_YAK_DIR


def _get_worker_port() -> str:
    """Get port for this worker to enable parallel E2E tests."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "master")
    worker_num = 0 if worker_id == "master" else int(worker_id.replace("gw", ""))
    return str(8081 + worker_num)


def _get_playwright_auth_path() -> SyncPath:
    """Get worker-specific Playwright auth file path."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "master")
    return SyncPath(__file__).absolute().parents[2] / f".playwright-auth-{worker_id}.json"


PORT = _get_worker_port()
BASE_URL = f"http://localhost:{PORT}"

PLAYWRIGHT_AUTH_PATH = _get_playwright_auth_path()
PLAYWRIGHT_AUTH_PATH.write_text("{}")


@pytest.fixture(scope="session", autouse=True)
def cleanup_mock_directories():
    """Clean up dynamically created test directories before and after test session."""
    # Directories that get created by tests but should not persist
    dynamic_dirs = [
        MOCK_YAK_DIR / "mock_djot_dir_0",
        MOCK_YAK_DIR / "test-e2e-category",
    ]

    for dir_path in dynamic_dirs:
        if dir_path.exists():
            shutil.rmtree(dir_path)

    yield

    # Clean up after tests too
    for dir_path in dynamic_dirs:
        if dir_path.exists():
            shutil.rmtree(dir_path)


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Configure browser context for testing.

    Docs: https://playwright.dev/docs/api/class-browser#browser-new-context

    Note: storage_state is not set by default to ensure clean auth state per test.
    Tests that need authentication should call the login() helper.
    """
    return {
        **browser_context_args,
    }


@pytest_asyncio.fixture(loop_scope="session")
async def unauthenticated_page(browser):
    """Create a page without authentication."""
    # Create a new context without any storage state (unauthenticated)
    context = await browser.new_context(storage_state=None, base_url=BASE_URL)
    page = await context.new_page()
    page.set_default_timeout(5000)
    yield page
    await page.close()
    await context.close()


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
    env = {**os.environ, "YAK_SHEARS_DIR": MOCK_YAK_DIR.as_posix()}
    process = await asyncio.create_subprocess_exec(
        "uv", "run", "serve", "--port", PORT, env=env, stderr=asyncio.subprocess.PIPE
    )
    await check_connection(timeout_s=5, url=BASE_URL)
    if process.returncode is not None:
        stderr_output = await process.stderr.read() if process.stderr else b""
        error_msg = stderr_output.decode().strip() or f"exit code {process.returncode}"
        msg = f"Server failed to start: {error_msg}"
        raise RuntimeError(msg)

    async def shutdown():
        if process.returncode is None:
            process.terminate()
            await asyncio.wait_for(process.wait(), timeout=5.0)

    try:
        try:
            yield
        except KeyboardInterrupt:
            await shutdown()
            raise
    finally:
        await shutdown()


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
def check_console_errors(request):
    """Fail test if there are console errors (unless explicitly allowed)."""
    # Skip console error checking for tests using unauthenticated_page
    # since they don't have the console_messages fixture
    if "unauthenticated_page" in request.fixturenames:
        yield
        return

    # For tests with regular page fixture, check console errors
    try:
        console_messages_obj = request.getfixturevalue("console_messages")
    except Exception:
        # If console_messages isn't available, skip checking
        yield
        return

    yield

    # Allow tests to mark themselves as allowing console errors
    allow_console_errors = request.node.get_closest_marker("allow_console_errors")
    if not allow_console_errors:
        console_errors = [msg for msg in console_messages_obj.captured if msg.startswith("error:")]
        assert len(console_errors) == 0, f"Console errors: {console_errors}"
