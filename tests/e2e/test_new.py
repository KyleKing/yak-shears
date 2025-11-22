"""E2E tests for new yak creation functionality."""

import re

import pytest
from playwright.async_api import BrowserContext, Page, expect

from tests.conftest import MOCK_YAK_DIR

from ._helpers import login


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_new_yak_page_loads(context: BrowserContext, page: Page, server_lifecycle):
    """Test that the new yak page loads correctly."""
    await login(context, page)

    await page.goto("/new")

    # Check page title
    await expect(page).to_have_title("New Yak")

    # Check form elements are present
    await expect(page.locator("h1")).to_contain_text("Create New Yak")
    await expect(page.locator("#category_select")).to_be_visible()
    await expect(page.locator("#new_category")).to_be_visible()
    await expect(page.locator("button[type='submit']")).to_be_visible()


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_create_new_yak_with_existing_category(context: BrowserContext, page: Page, server_lifecycle):
    """Test creating a new yak with an existing category."""
    await login(context, page)

    await page.goto("/new")

    # Select an existing category (if available)
    category_options = await page.locator("#category_select option").all()
    if len(category_options) > 1:  # More than just the placeholder
        # Select the first real category
        await page.select_option("#category_select", index=1)

        # Submit form
        await page.click("button[type='submit']")

        # Should redirect to edit page
        await expect(page).to_have_url(re.compile(r"/edit\?yak=.*"))


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_create_new_yak_with_new_category(context: BrowserContext, page: Page, server_lifecycle):
    """Test creating a new yak with a new category."""
    await login(context, page)

    await page.goto("/new")

    # Enter a new category name
    test_category = "test-e2e-category"
    await page.fill("#new_category", test_category)

    # Submit form
    await page.click("button[type='submit']")

    # Should redirect to edit page
    await expect(page).to_have_url(re.compile(r"/edit\?yak=.*"))


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_new_yak_cancel_navigation(context: BrowserContext, page: Page, server_lifecycle):
    """Test that cancel button navigates back to yaks page."""
    await login(context, page)

    await page.goto("/new")

    # Click cancel
    cancel_button = page.locator("a:has-text('Cancel')")
    await cancel_button.click()

    # Should navigate to yaks page
    await expect(page).to_have_url("/yaks")


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_new_yak_from_navigation(context: BrowserContext, page: Page, server_lifecycle):
    """Test navigating to new yak page from main navigation."""
    await login(context, page)

    await page.goto("/yaks")

    # Click "New" in navigation
    new_link = page.locator("a.nav__link:has-text('New')")
    await new_link.click()

    # Should navigate to new page
    await expect(page).to_have_url("/new")
    await expect(page).to_have_title("New Yak")


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_new_yak_requires_authentication(context: BrowserContext, page: Page, server_lifecycle):
    """Test that new yak page requires authentication."""
    # Try to access without logging in
    await page.goto("/new")

    # Should redirect to login with redirect parameter
    await expect(page).to_have_url("**/auth/login?redirect=**")
