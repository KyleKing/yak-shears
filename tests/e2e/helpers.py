"""E2E Playwright Helpers."""

from playwright.async_api import BrowserContext, Page

from tests.conftest import SAMPLE_USER_EMAIL, SAMPLE_USER_PASSWORD
from tests.e2e.conftest import PLAYWRIGHT_AUTH_PATH


async def login(context: BrowserContext, page: Page) -> None:
    """When run as a fixture, this function stalls, but fine as a function."""
    await page.goto("/")

    if "/auth/login" in page.url:
        title = await page.title()
        assert "Login" in title

        await page.get_by_role("textbox", name="Email").fill(SAMPLE_USER_EMAIL)
        await page.get_by_role("textbox", name="Password").fill(SAMPLE_USER_PASSWORD)
        await page.get_by_role("button", name="Login").click()

        await page.wait_for_url("/files")
        await page.wait_for_load_state("load")

        await context.storage_state(path=PLAYWRIGHT_AUTH_PATH)
