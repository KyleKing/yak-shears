import pytest
from playwright.async_api import Page, expect


# @pytest.mark.playwright
# @pytest.mark.asyncio
# async def test_login_page_loads(page: Page, server_lifecycle):
#     """Test that the login page loads correctly."""
#     await page.goto("/auth/login")
#     content = await page.content()
#     assert "Login" in content


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_server_starts_and_serves_homepage(page: Page, authenticated_session):
    """Test that the server starts and serves the homepage."""
    await page.goto("/")
    await expect(page.locator("body")).to_be_visible()
    title = await page.title()
    assert "Login" not in title, "Login page was not skipped"
    assert title == "Notes in ./Sync/yak-shears"


# @pytest.mark.playwright
# @pytest.mark.asyncio
# async def test_files_page_loads(page: Page, authenticated_session):
#     """Test that the files page loads correctly."""
#     await page.goto("/files")
#     content = await page.content()
#     assert "Notes" in content
