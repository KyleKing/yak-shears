import re

import pytest
from playwright.async_api import BrowserContext, Page, expect

from ._helpers import login, maybe_screenshot


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_redirect_to_yaks(context: BrowserContext, page: Page, server_lifecycle):
    await login(context, page)

    await page.goto("/")

    title = await page.title()
    assert "Login" not in title, "Login page was not skipped"
    assert "/yaks" in page.url, "Did not redirect to yaks"
    assert title == "Yaks in ./test_data/mock_djot_dir_0"


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_yaks_page_loads(context: BrowserContext, page: Page, server_lifecycle):
    """Test that the yaks page loads correctly."""
    await login(context, page)

    await page.goto("/yaks")
    await maybe_screenshot(page, ".github/screenshots/yaks-page.png")

    content = await page.content()
    assert "Yaks" in content


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_yaks_sorting_by_name(context: BrowserContext, page: Page, server_lifecycle):
    """Test sorting yaks by name."""
    await login(context, page)

    await page.goto("/yaks")

    # Click sort by name button
    sort_by_name = page.locator("a:has-text('Name (Created At)')")
    await sort_by_name.click()

    # Check URL contains sort parameter
    await page.wait_for_url("**/yaks?sort_by=name")

    # Verify the button is marked as active
    await expect(sort_by_name).to_have_class(re.compile(r"button--primary"))


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_yaks_sorting_by_modified_date(context: BrowserContext, page: Page, server_lifecycle):
    """Test sorting yaks by modified date."""
    await login(context, page)

    await page.goto("/yaks")

    # Click sort by modified date button
    sort_by_modified = page.locator("a:has-text('Modified Date')")
    await sort_by_modified.click()

    # Check URL contains sort parameter
    await page.wait_for_url("**/yaks?sort_by=modified_date")

    # Verify the button is marked as active
    await expect(sort_by_modified).to_have_class(re.compile(r"button--primary"))


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_yaks_card_navigation(context: BrowserContext, page: Page, server_lifecycle):
    """Test clicking on a yak card navigates to edit page."""
    await login(context, page)

    await page.goto("/yaks")

    # Click on first yak card
    first_card = page.locator(".card").first
    await first_card.click()

    # Should navigate to edit page
    await expect(page).to_have_url(re.compile(r"/edit\?yak=.*"))


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_yaks_displays_cards(context: BrowserContext, page: Page, server_lifecycle):
    """Test that yak cards are displayed."""
    await login(context, page)

    await page.goto("/yaks")

    # Check that cards are present
    cards = page.locator(".card")
    await expect(cards.first).to_be_visible()

    # Check that cards have content
    card_body = page.locator(".card__body").first
    await expect(card_body).to_be_visible()


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_yaks_responsive_layout(context: BrowserContext, page: Page, server_lifecycle):
    """Test that yaks page is responsive on different screen sizes."""
    await login(context, page)

    # Test on mobile
    await page.set_viewport_size({"width": 375, "height": 667})
    await page.goto("/yaks")

    cards_container = page.locator(".cards")
    await expect(cards_container).to_be_visible()

    # Test on tablet
    await page.set_viewport_size({"width": 768, "height": 1024})
    await page.goto("/yaks")
    await expect(cards_container).to_be_visible()

    # Test on desktop
    await page.set_viewport_size({"width": 1920, "height": 1080})
    await page.goto("/yaks")
    await expect(cards_container).to_be_visible()
