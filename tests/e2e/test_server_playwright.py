import pytest
from playwright.async_api import BrowserContext, Page

from .helpers import login


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_login_page_loads(page: Page, server_lifecycle):
    """Test that the login page loads correctly."""
    await page.goto("/auth/login")
    content = await page.content()
    assert "Login" in content


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_server_starts_and_serves_homepage(context: BrowserContext, page: Page, server_lifecycle):
    """Test that the server starts and serves the homepage."""
    await login(context, page)
    await page.goto("/")
    title = await page.title()
    assert "Login" not in title, "Login page was not skipped"
    assert "/files" in page.url, "Did not redirect to files"
    assert title == "Notes in ./Sync/yak-shears"


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_files_page_loads(context: BrowserContext, page: Page, server_lifecycle):
    """Test that the files page loads correctly."""
    await login(context, page)
    await page.goto("/files")
    content = await page.content()
    assert "Notes" in content
