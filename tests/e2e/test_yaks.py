import pytest
from playwright.async_api import BrowserContext, Page

from ._helpers import login


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

    content = await page.content()
    assert "Yaks" in content
