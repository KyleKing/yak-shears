import pytest
from playwright.async_api import BrowserContext, Page, ViewportSize, expect

from ._helpers import login, maybe_screenshot

IPHONE_14_VIEWPORT = ViewportSize(width=390, height=844)


async def _open_first_result_modal(page: Page) -> None:
    await page.goto("/search")
    await page.locator(".search-input").fill("yak")
    await page.wait_for_selector(".search-results-list", timeout=5000)
    await page.locator(".search-result").first.click()
    await expect(page.locator("#search-preview-modal")).to_be_visible()
    await expect(page.locator("#search-preview-modal-content")).not_to_be_empty(timeout=5000)


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

    # All three fixture yaks carry the exact word "yak" on line 1, so they tie on
    # the only relevance signal and the path tiebreak decides. This used to read
    # "yak1.dj", which passed on insertion order rather than on any rule.
    first_result = results.first
    await expect(first_result).to_contain_text("subdirectory-2/yak2.dj")

    raw_paths = [await item.get_attribute("data-path") for item in await results.all()]
    assert all(path is not None for path in raw_paths)
    ordering = [path for path in raw_paths if path is not None]
    assert ordering == sorted(ordering), "Equal-scoring matches must come back in path order"

    # Re-running the same query must produce the same order (previously it could
    # reshuffle whenever re-indexing moved a file's rows in storage).
    await search_input.fill("")
    await search_input.fill("yak")
    await page.wait_for_selector(".search-results-list", timeout=5000)
    repeated = [
        path
        for item in await page.locator(".search-result").all()
        if (path := await item.get_attribute("data-path")) is not None
    ]
    assert repeated == ordering, "Search ordering must be stable across identical queries"

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


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_search_modal_open_link_reachable_on_iphone(
    context: BrowserContext, page: Page, server_lifecycle, console_messages
):
    """On an iPhone viewport the modal's Open link sits in view without scrolling the body."""
    await login(context, page)
    await page.set_viewport_size(IPHONE_14_VIEWPORT)

    await _open_first_result_modal(page)

    open_link = page.locator("#search-preview-modal .search-preview__open")
    await expect(open_link).to_be_visible()
    await expect(open_link).to_be_in_viewport()

    href = await open_link.get_attribute("href")
    assert href is not None
    assert href.startswith("/edit?yak=")

    close_button = page.locator("#search-preview-modal-close")
    await expect(close_button).to_be_in_viewport()
    box = await close_button.bounding_box()
    assert box is not None
    assert box["height"] >= 44, f"Close button is too small to tap: {box}"


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_search_modal_closes_by_button_and_escape(
    context: BrowserContext, page: Page, server_lifecycle, console_messages
):
    """Both the Close button and the Escape key dismiss the mobile preview modal."""
    await login(context, page)
    await page.set_viewport_size(IPHONE_14_VIEWPORT)

    modal = page.locator("#search-preview-modal")

    await _open_first_result_modal(page)
    await page.locator("#search-preview-modal-close").click()
    await expect(modal).not_to_be_visible()

    await page.locator(".search-result").first.click()
    await expect(modal).to_be_visible()
    await page.keyboard.press("Escape")
    await expect(modal).not_to_be_visible()
