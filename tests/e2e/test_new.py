"""E2E tests for new yak creation functionality."""

import re

import pytest
from playwright.async_api import BrowserContext, Page, expect

from ._helpers import login


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_new_yak_modal_opens_over_the_rack(context: BrowserContext, page: Page, server_lifecycle):
    """Test that /new lands on the rack with the creation modal open."""
    await login(context, page)

    await page.goto("/new")

    await expect(page).to_have_url("/yaks?new=1")
    await expect(page.locator("#new-yak")).to_be_visible()
    await expect(page.locator("#new-yak-title")).to_contain_text("New Yak")
    await expect(page.locator("#new_category")).to_be_visible()


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_create_new_yak_with_existing_category(context: BrowserContext, page: Page, server_lifecycle):
    """Test that one click on a category key creates a yak and opens the editor."""
    await login(context, page)

    await page.goto("/yaks?new=1")

    keys = page.locator(".new-yak__key")
    if await keys.count():
        await keys.first.click()
        await expect(page).to_have_url(re.compile(r"/edit\?yak=.*"))


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_create_new_yak_with_new_category(context: BrowserContext, page: Page, server_lifecycle):
    """Test creating a new yak with a new category."""
    await login(context, page)

    await page.goto("/yaks?new=1")

    await page.fill("#new_category", "test-e2e-category")
    await page.click(".new-yak__create button[type='submit']")

    await expect(page).to_have_url(re.compile(r"/edit\?yak=.*"))


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_new_yak_close_navigation(context: BrowserContext, page: Page, server_lifecycle):
    """Test that closing the modal returns to the rack."""
    await login(context, page)

    await page.goto("/yaks?new=1")
    await page.click(".modal__close")

    await expect(page).to_have_url("/yaks")
    await expect(page.locator("#new-yak")).to_have_count(0)


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_new_yak_from_navigation(context: BrowserContext, page: Page, server_lifecycle):
    """Test opening the creation modal from main navigation."""
    await login(context, page)

    await page.goto("/yaks")

    await page.locator("a.nav__link:has-text('New')").click()

    await expect(page).to_have_url("/yaks?new=1")
    await expect(page.locator("#new-yak")).to_be_visible()


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_new_yak_requires_authentication(unauthenticated_page: Page, server_lifecycle):
    """Test that new yak page requires authentication."""
    # Try to access without logging in
    await unauthenticated_page.goto("/new")

    # Should redirect to login with redirect parameter
    re_auth_redirect = re.compile(r".+/auth/login\?redirect=.+")
    await expect(unauthenticated_page).to_have_url(re_auth_redirect)
