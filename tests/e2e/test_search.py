import pytest
from playwright.async_api import BrowserContext, Page, expect

from ._helpers import login, maybe_screenshot


@pytest.mark.playwright
@pytest.mark.asyncio
@pytest.mark.timeout(None)
async def test_search_with_query(context: BrowserContext, page: Page, server_lifecycle, console_messages):
    """Test searching with a query and verifying matches."""
    await login(context, page)

    await page.goto("/search")
    await maybe_screenshot(page, ".github/screenshots/search-page.png")

    # Check the HTML head
    head_html = await page.locator("head").inner_html()
    assert head_html is not None

    # Enter search query
    search_input = page.locator(".search-input")
    await search_input.fill("yak")
    # Wait for HTMX to trigger search and results to load
    await page.wait_for_selector(".search-results-list", timeout=5000)

    # Check that results are displayed
    results = page.locator(".search-result")
    count = await results.count()
    assert count > 1, "Expected at least two matches"

    # Check first result
    first_result = results.first
    await expect(first_result).to_contain_text("yak1.dj")

    # Check data attributes
    data_path = await first_result.get_attribute("data-path")
    assert data_path is not None

    # Check if JavaScript loaded
    body_class = await page.get_attribute("body", "class")
    assert body_class is not None

    # Test clicking on result shows preview
    await first_result.click()

    # Wait for preview content to load (API call)
    preview_content = page.locator("#search-preview-content")
    await expect(preview_content).not_to_be_empty(timeout=5000)

    # Check that preview content is loaded and contains expected content
    preview_text = await preview_content.text_content()
    assert preview_text is not None, "Preview text should not be None"
    assert len(preview_text.strip()) > 0, "Preview should contain content"
    # Preview should show content from a yak file that matches the search
    await expect(preview_content).to_contain_text("yak", ignore_case=True)

    # Test arrow key navigation updates preview
    initial_text = preview_text
    await page.keyboard.press("ArrowDown")
    await page.wait_for_function(
        "initialText => document.querySelector('#search-preview-content')?.textContent !== initialText",
        arg=initial_text,
        timeout=5000,
    )
    # Check that preview content changed (different line numbers or content)
    new_preview_text = await preview_content.text_content()
    # The preview should be different or at least exist
    assert new_preview_text is not None, "New preview text should not be None"
    assert len(new_preview_text.strip()) > 0, "Preview should still contain content after navigation"

    # Test arrow key navigation updates preview
    await page.keyboard.press("ArrowDown")
    # Wait for next preview update
    await page.wait_for_function(
        "prevText => document.querySelector('#search-preview-content')?.textContent !== prevText",
        arg=new_preview_text,
        timeout=5000,
    )
    # Check that preview content changed (different line numbers or content)
    final_preview_text = await preview_content.text_content()
    # The preview should be different or at least exist
    assert final_preview_text is not None, "New preview text should not be None after second navigation"
    assert len(final_preview_text.strip()) > 0, "Preview should still contain content after second navigation"


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_search_modal_on_small_screen(context: BrowserContext, page: Page, server_lifecycle, console_messages):
    """Test that search shows preview in modal on small screens."""
    await login(context, page)

    # Set viewport to small screen
    await page.set_viewport_size({"width": 600, "height": 800})

    await page.goto("/search")

    # Enter search query
    search_input = page.locator(".search-input")
    await search_input.fill("yak")
    # Wait for HTMX to trigger search and results to load
    await page.wait_for_selector(".search-results-list", timeout=5000)

    # Check that results are displayed
    results = page.locator(".search-result")
    count = await results.count()
    assert count > 1

    # Check that preview is not visible on small screen
    preview = page.locator("#search-preview")
    await expect(preview).not_to_be_visible()

    # Click on first result to open modal
    first_result = results.first
    await first_result.click()

    # Wait for modal to appear
    modal = page.locator("#search-preview-modal")
    await expect(modal).to_be_visible()

    # Check that modal content is loaded (wait for API call)
    modal_content = page.locator("#search-preview-modal-content")
    await expect(modal_content).not_to_be_empty(timeout=5000)
    modal_text = await modal_content.text_content()
    assert modal_text is not None
    assert len(modal_text.strip()) > 0

    # Check that close button works
    close_button = page.locator("#search-preview-modal-close")
    await close_button.click()
    await expect(modal).not_to_be_visible()
