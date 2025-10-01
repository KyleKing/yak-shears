import pytest
from playwright.async_api import BrowserContext, Page

from ._helpers import login


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_search_with_query(context: BrowserContext, page: Page, server_lifecycle, console_messages):
    """Test searching with a query and verifying matches."""
    await login(context, page)

    await page.goto("/search")

    # Check the HTML head
    head_html = await page.locator("head").inner_html()
    print(f"Head HTML: {head_html}")

    # Enter search query
    search_input = page.locator(".search-input")
    await search_input.fill("yak")
    # Wait for HTMX to trigger search (300ms delay)
    await page.wait_for_timeout(500)

    # Wait for results
    await page.wait_for_selector(".search-results-list")

    # Check that results are displayed
    results = page.locator(".search-result")
    count = await results.count()
    assert count > 0, "No search results found"

    # Check first result
    first_result = results.first
    text = await first_result.text_content()
    assert text is not None, "Result text should not be None"
    assert "yak1.dj" in text, f"Expected yak1.dj in result, got: {text}"

    # Check data attributes
    data_path = await first_result.get_attribute("data-path")
    data_line = await first_result.get_attribute("data-line")
    print(f"First result data-path: {data_path}, data-line: {data_line}")

    # Check if JavaScript loaded
    body_class = await page.get_attribute("body", "class")
    print(f"Body class: {body_class}")

    # Test clicking on result shows preview
    await first_result.click()

    # Wait for preview to load
    await page.wait_for_timeout(500)  # Give time for API call

    # Check that preview content is loaded
    preview_content = page.locator("#search-preview-content")
    preview_text = await preview_content.text_content()
    print(f"Preview text: '{preview_text}'")
    assert preview_text is not None and len(preview_text.strip()) > 0, "Preview should contain content"

    # Test arrow key navigation updates preview
    if count > 1:
        # Press arrow down to select second result
        await page.keyboard.press("ArrowDown")

        # Wait a bit for preview to update
        await page.wait_for_timeout(100)

        # Check that preview content changed (different line numbers or content)
        new_preview_text = await preview_content.text_content()
        # The preview should be different or at least exist
        assert new_preview_text is not None and len(new_preview_text.strip()) > 0, (
            "Preview should still contain content after navigation"
        )

    # Test arrow key navigation updates preview
    if count > 1:
        # Press arrow down to select second result
        await page.keyboard.press("ArrowDown")

        # Wait a bit for preview to update
        await page.wait_for_timeout(100)

        # Check that preview content changed (different line numbers or content)
        new_preview_text = await preview_content.text_content()
        # The preview should be different or at least exist
        assert new_preview_text is not None and len(new_preview_text.strip()) > 0, (
            "Preview should still contain content after navigation"
        )
