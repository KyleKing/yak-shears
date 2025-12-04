"""E2E Playwright Helpers."""

import os
from pathlib import Path

from playwright.async_api import BrowserContext, Page, expect

from tests.conftest import SAMPLE_USER_EMAIL, SAMPLE_USER_PASSWORD

from .conftest import get_playwright_auth_path

CAPTURE_SCREENSHOTS = os.getenv("CAPTURE_SCREENSHOTS", "false").lower() == "true"


async def maybe_screenshot(page: Page, path: str | Path) -> None:
    """Capture a screenshot only if CAPTURE_SCREENSHOTS environment variable is set to 'true'."""
    if CAPTURE_SCREENSHOTS:
        await page.screenshot(path=path)


async def login(context: BrowserContext, page: Page, *, save_state: bool = False) -> None:
    """Login helper that authenticates the user.

    Args:
        context: Browser context
        page: Page instance
        save_state: If True, save authentication state to file for session reuse
    """
    await page.goto("/")

    if "/auth/login" in page.url:
        title = await page.title()
        assert "Login" in title

        await maybe_screenshot(page, ".github/screenshots/login-page.png")

        await page.get_by_role("textbox", name="Email").fill(SAMPLE_USER_EMAIL)
        await page.get_by_role("textbox", name="Password").fill(SAMPLE_USER_PASSWORD)
        await page.get_by_role("button", name="Login").click()

        await page.wait_for_url("/yaks")
        await page.wait_for_load_state("load")

        if save_state:
            await context.storage_state(path=get_playwright_auth_path())


async def open_menu(page: Page, *, pin: bool = False) -> None:
    """Helper to open the edit page Menu.

    Args:
        page: Page instance
        pin: If True, pin menu to be open
    """
    menu_button = page.locator("button:has-text('Menu')")
    await expect(menu_button).to_be_visible()
    await menu_button.click()
    if pin:
        await page.locator("#panel-pin-btn").click()
