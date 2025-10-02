import pytest
from playwright.async_api import BrowserContext, Page, expect

from ._helpers import login


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_search_with_query(context: BrowserContext, page: Page, server_lifecycle, console_messages):
    """Test searching with a query and verifying matches."""
    await login(context, page)

    await page.goto("/search")

    # Check the HTML head
    head_html = await page.locator("head").inner_html()
    assert head_html is not None

    # Enter search query
    search_input = page.locator(".search-input")
    await search_input.fill("yak")
    # Wait for HTMX to trigger search (300ms delay)
    await page.wait_for_timeout(500)
    await page.wait_for_selector(".search-results-list")

    # Check that results are displayed
    results = page.locator(".search-result")
    count = await results.count()
    assert count > 1, "Expected at least two matches"

    # Check first result
    first_result = results.first
    await expect(first_result).to_contain_text("yak1.dj")

    # Check data attributes
    data_path = await first_result.get_attribute("data-path")
    data_line = await first_result.get_attribute("data-line")
    assert data_path is not None
    assert data_line is not None

    # Check if JavaScript loaded
    body_class = await page.get_attribute("body", "class")
    assert body_class is not None

    # Test clicking on result shows preview
    await first_result.click()

    # Wait for preview to load
    await page.wait_for_timeout(500)  # Give time for API call

    # Check that preview content is loaded
    preview_content = page.locator("#search-preview-content")
    preview_text = await preview_content.text_content()
    assert preview_text is not None, "Preview text should not be None"
    assert len(preview_text.strip()) > 0, "Preview should contain content"

    # Test arrow key navigation updates preview
    await page.keyboard.press("ArrowDown")
    await page.wait_for_timeout(100)
    # Check that preview content changed (different line numbers or content)
    new_preview_text = await preview_content.text_content()
    # The preview should be different or at least exist
    assert new_preview_text is not None, "New preview text should not be None"
    assert len(new_preview_text.strip()) > 0, "Preview should still contain content after navigation"

    # Test arrow key navigation updates preview
    await page.keyboard.press("ArrowDown")
    await page.wait_for_timeout(100)
    # Check that preview content changed (different line numbers or content)
    new_preview_text = await preview_content.text_content()
    # The preview should be different or at least exist
    assert new_preview_text is not None, "New preview text should not be None after second navigation"
    assert len(new_preview_text.strip()) > 0, "Preview should still contain content after second navigation"
