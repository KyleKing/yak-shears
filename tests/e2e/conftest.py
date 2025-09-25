"""Playwright fixtures."""

import asyncio
import time
from asyncio.subprocess import PIPE
from contextlib import suppress
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from playwright.async_api import Page

from ..conftest import SAMPLE_USER_EMAIL, SAMPLE_USER_PASSWORD

PORT = "8081"
BASE_URL = f"http://localhost:{PORT}"

(Path(__file__).absolute().parents[2] / "playwright-secure/auth.json").write_text("{}")


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Configure browser context for testing.

    Docs: https://playwright.dev/docs/api/class-browser#browser-new-context

    """
    return {
        "storage_state": "playwright-secure/auth.json",
        **browser_context_args,
    }


@pytest.fixture(scope="session")
def base_url():
    """Overrides https://github.com/pytest-dev/pytest-base-url."""
    return BASE_URL


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
        if process.returncode is None:
            process.kill()
        await process.wait()


@pytest_asyncio.fixture
async def authenticated_session(context, page: Page):  # , server_lifecycle):
    page.set_default_navigation_timeout(10_000)
    page.set_default_timeout(10_000)
    print("Starting authenticated_session fixture")
    # Ensure server is healthy
    async with httpx.AsyncClient() as client:
        try:
            # TODO: Maybe use a 307 redirect to verify that the user isn't logged in?
            response = await client.get(BASE_URL, timeout=5)
            print(f"Server health check: {response.status_code}")
        except Exception as e:
            print(f"Server health check failed: {e}")
            raise
    # Start from root to handle redirects properly
    print("Navigating to /files")
    try:
        await page.goto("/files", wait_until="load", timeout=10000)
        print("Navigated to /files successfully")
    except Exception as e:
        print(f"Error navigating to /files: {e}")
        raise
    print("Checking current URL after navigation")
    current_url = page.url
    print(f"Current URL: {current_url}")
    if "/auth/login" in current_url:
        print("Already at /auth/login")
    else:
        print("Not at /auth/login, may need to handle redirect")
    print("Reached /auth/login, getting title")
    title = await page.title()
    print(f"Page title: {title}")
    if "Login" in title:
        try:
            # Action Docs: https://playwright.dev/python/docs/input#text-input
            print("Filling email")
            await page.get_by_role("textbox", name="Email").fill(SAMPLE_USER_EMAIL)
            print("Filling password")
            await page.get_by_role("textbox", name="Password").fill(SAMPLE_USER_PASSWORD)
            print("Clicking login button")
            await page.get_by_role("button", name="Login").click()

            print("Waiting for redirect after login")
            await page.wait_for_url("/files", timeout=10000)
            await page.wait_for_load_state("load")

            print("Saving storage state")
            await context.storage_state(path="playwright-secure/auth.json")
        except Exception as e:
            print(f"Error during login process: {e}")
            raise
    else:
        print("Already authenticated, skipping login")


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
