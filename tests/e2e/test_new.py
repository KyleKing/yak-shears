"""E2E tests for new yak creation functionality."""

import re

import pytest
from playwright.async_api import BrowserContext, Page, expect

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
    await expect(page.locator("#category")).to_be_visible()
    await expect(page.locator("#category-listbox")).to_have_count(1)
    await expect(page.locator("button[type='submit']")).to_be_visible()


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_create_new_yak_with_existing_category(context: BrowserContext, page: Page, server_lifecycle):
    """Test creating a new yak with an existing category."""
    await login(context, page)

    await page.goto("/new")

    # Pick an existing category from the combobox (if any) by typing its value
    options = await page.locator("#category-listbox .combobox__option").all()
    if options:
        existing = await options[0].get_attribute("data-value")
        await page.fill("#category", existing)
        # Dismiss the open listbox so it does not cover the submit button
        await page.keyboard.press("Escape")

        # Submit form
        await page.click("button[type='submit']")

        # Should redirect to edit page
        await expect(page).to_have_url(re.compile(r"/edit\?yak=.*"))


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_create_new_yak_with_new_category(context: BrowserContext, page: Page, server_lifecycle):
    """Test creating a new yak with a new category."""
    await login(context, page)

    # Wait for combobox.js (loaded at the end of the body). Typing a category
    # opens the listbox over the form actions, so dismiss it before submitting,
    # or the submit click waits for actionability until the test times out.
    await page.goto("/new", wait_until="networkidle")

    # Enter a new category name
    test_category = "test-e2e-category"
    await page.fill("#category", test_category)
    await page.keyboard.press("Escape")
    await expect(page.locator("#category-listbox")).to_be_hidden()

    # Submit form
    await page.click("button[type='submit']")

    # Should redirect to edit page
    await expect(page).to_have_url(re.compile(r"/edit\?yak=.*"))


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_new_yak_cancel_navigation(context: BrowserContext, page: Page, server_lifecycle):
    """Test that cancel button navigates back to yaks page."""
    await login(context, page)

    # combobox.js loads at the end of the body, so pressing Escape straight after
    # navigation can land before it binds. The listbox then opens over the form
    # actions and the Cancel click waits for actionability until the test times
    # out. Wait for the script, dismiss, and confirm it is closed.
    await page.goto("/new", wait_until="networkidle")

    listbox = page.locator("#category-listbox")
    await page.keyboard.press("Escape")
    await expect(listbox).to_be_hidden()

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
async def test_new_yak_requires_authentication(unauthenticated_page: Page, server_lifecycle):
    """Test that new yak page requires authentication."""
    # Try to access without logging in
    await unauthenticated_page.goto("/new")

    # Should redirect to login with redirect parameter
    re_auth_redirect = re.compile(r".+/auth/login\?redirect=.+")
    await expect(unauthenticated_page).to_have_url(re_auth_redirect)
