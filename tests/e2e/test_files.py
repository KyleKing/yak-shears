import pytest
from playwright.async_api import BrowserContext, Page

from ._helpers import login


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_redirect_to_files(context: BrowserContext, page: Page, server_lifecycle):
    await login(context, page)

    await page.goto("/")

    title = await page.title()
    assert "Login" not in title, "Login page was not skipped"
    assert "/files" in page.url, "Did not redirect to files"
    assert title == "Yaks in ./test_data/mock_djot_files"


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_files_page_loads(context: BrowserContext, page: Page, server_lifecycle):
    """Test that the files page loads correctly."""
    await login(context, page)

    await page.goto("/files")

    content = await page.content()
    assert "Yaks" in content
