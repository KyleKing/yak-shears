"""E2E tests for new yak creation functionality."""

import re

import pytest
from playwright.async_api import BrowserContext, Page, expect

from ._helpers import login


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_new_yak_page_shows_the_picker(context: BrowserContext, page: Page, server_lifecycle):
    """Test that /new is its own page carrying the creation forms."""
    await login(context, page)

    await page.goto("/new")

    await expect(page).to_have_url("/new")
    await expect(page.locator("h1")).to_contain_text("New Yak")
    await expect(page.locator("#new_category")).to_be_visible()


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_create_new_yak_with_existing_category(context: BrowserContext, page: Page, server_lifecycle):
    """Test that one click on a category key creates a yak and opens the editor."""
    await login(context, page)

    await page.goto("/new")

    keys = page.locator(".new-yak__key")
    if await keys.count():
        await keys.first.click()
        await expect(page).to_have_url(re.compile(r"/edit\?yak=.*"))


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_create_new_yak_with_new_category(context: BrowserContext, page: Page, server_lifecycle):
    """Test creating a new yak with a new category."""
    await login(context, page)

    await page.goto("/new")

    await page.fill("#new_category", "test-e2e-category")
    await page.click(".new-yak__create button[type='submit']")

    await expect(page).to_have_url(re.compile(r"/edit\?yak=.*"))


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_back_returns_to_the_rack(context: BrowserContext, page: Page, server_lifecycle):
    """Test that the header back control leaves /new for the page behind it."""
    await login(context, page)

    await page.goto("/yaks")
    await page.locator(".header__actions a:has-text('New')").click()
    await expect(page).to_have_url("/new")

    await page.click("#header-back")

    await expect(page).to_have_url("/yaks")


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_back_is_absent_on_the_rack(context: BrowserContext, page: Page, server_lifecycle):
    """Test that the rack is the root and offers nothing to go back to."""
    await login(context, page)

    await page.goto("/yaks")

    await expect(page.locator("#header-back")).to_have_count(0)


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_new_yak_from_navigation(context: BrowserContext, page: Page, server_lifecycle):
    """Test that New stays on the header bar rather than behind the menu."""
    await login(context, page)

    await page.goto("/yaks")

    await page.locator(".header__actions a:has-text('New')").click()

    await expect(page).to_have_url("/new")
    await expect(page.locator("#new_category")).to_be_visible()


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_new_yak_requires_authentication(unauthenticated_page: Page, server_lifecycle):
    """Test that new yak page requires authentication."""
    # Try to access without logging in
    await unauthenticated_page.goto("/new")

    # Should redirect to login with redirect parameter
    re_auth_redirect = re.compile(r".+/auth/login\?redirect=.+")
    await expect(unauthenticated_page).to_have_url(re_auth_redirect)
