"""E2E tests for authentication functionality."""

import pytest
from playwright.async_api import BrowserContext, Page, expect


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_login_success(context: BrowserContext, page: Page, server_lifecycle):
    """Test successful login flow."""
    await page.goto("/")

    # Should redirect to login page
    assert "/auth/login" in page.url, f"Expected login page, got: {page.url}"
    await expect(page).to_have_title("Login to Yak-Shears")

    # Fill in credentials
    await page.fill("input[name='email']", "test@example.com")
    await page.fill("input[name='password']", "secure123")

    # Submit login form
    await page.click("button[type='submit']")

    # Should redirect to yaks page after successful login
    await page.wait_for_url("**/yaks")
    assert "/yaks" in page.url, f"Expected yaks page, got: {page.url}"
    await expect(page.locator("h1")).to_contain_text("Yaks")


@pytest.mark.playwright
@pytest.mark.asyncio
@pytest.mark.allow_console_errors
@pytest.mark.parametrize(
    ("email", "password"),
    [
        ("test@example.com", "wrongpassword"),
        ("nonexistent@example.com", "anypassword"),
    ],
    ids=["wrong_password", "nonexistent_user"],
)
async def test_login_failure(
    context: BrowserContext,
    page: Page,
    server_lifecycle,
    email,
    password,
):
    """Test login failure (wrong password and nonexistent user)."""
    await page.goto("/auth/login")

    await page.fill("input[name='email']", email)
    await page.fill("input[name='password']", password)

    await page.click("button[type='submit']")

    # Should stay on login page and show error
    await expect(page).to_have_url("/auth/login")
    error_message = page.locator(".alert, .error, [role='alert']")
    await expect(error_message).to_be_visible()


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_redirect_to_login_when_not_authenticated(unauthenticated_page: Page, server_lifecycle):
    """Test that unauthenticated users are redirected to login."""
    # Try to access protected pages without logging in
    protected_urls = ["/yaks", "/edit?yak=test.dj", "/search", "/new"]

    for url in protected_urls:
        await unauthenticated_page.goto(url)
        # Should redirect to login with redirect parameter
        assert "/auth/login?redirect=" in unauthenticated_page.url, (
            f"Expected redirect to login with redirect param, got: {unauthenticated_page.url}"
        )


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_session_persistence(context: BrowserContext, page: Page, server_lifecycle):
    """Test that session persists across page loads."""
    # Login
    await page.goto("/auth/login")
    await page.fill("input[name='email']", "test@example.com")
    await page.fill("input[name='password']", "secure123")
    await page.click("button[type='submit']")
    await expect(page).to_have_url("/yaks")

    # Navigate to different pages
    await page.goto("/search")
    await expect(page).to_have_url("/search")

    await page.goto("/yaks")
    await expect(page).to_have_url("/yaks")

    # Reload page
    await page.reload()
    await expect(page).to_have_url("/yaks")

    # Should still be authenticated
    await expect(page.locator("h1")).to_contain_text("Yaks")
