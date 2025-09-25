# FYI: Adapted from App-Template example and planning for auth
# Note: when modifying/dleeting this file, remove the ignore rules for ruff from pyproject.toml
#
# import pytest
#
# from playwright.async_api import Page, expect
#
# @pytest_asyncio.fixture
# async def authenticated_page(browser: Browser, temp_user_file, sample_user) -> Page:
#     """Create a page with authenticated session."""
#     context = browser.new_context()
#     page = context.new_page()
#
#     # Set up authentication cookie/session
#     # This would need to be implemented based on your auth system
#     # For now, we'll just return the page
#     yield page
#
#     context.close()
#
# @pytest.mark.playwright
# @pytest.mark.asyncio(loop_scope="session")
# async def test_comment_demo_works(page: Page):
#     """Test that the comment demo works with optimistic updates"""
#     page.goto("http://localhost:8081/comments")
#     expect(page.locator("h1")).to_contain_text("Comments")
#
#     # Check that HTMX is loaded
#     htmx_loaded = page.evaluate("typeof window.htmx !== 'undefined'")
#     assert htmx_loaded is True
#
#     # Wait for comments list to load
#     page.wait_for_selector("#comments-list li")
#
#     test_author = "Test User"
#     test_body = "This is a test comment for optimistic replacement"
#
#     # Fill in the form
#     page.fill("#author", test_author)
#     page.fill("#body", test_body)
#
#     # Note: Network interception for delay simulation removed for simplicity
#     # In a full implementation, you would use page.route() here
#
#     # Submit the form
#     page.click('button[type="submit"]')
#
#     # Check optimistic update
#     optimistic_comment = page.locator(".c-comment--optimistic")
#     expect(optimistic_comment.locator('[data-field="author"]')).to_contain_text(test_author)
#     expect(optimistic_comment.locator('[data-field="body"]')).to_contain_text(test_body)
#     expect(optimistic_comment.locator('[data-field="time"]')).to_contain_text("(sending…)")
#
#     # Wait for optimistic update to be replaced
#     page.wait_for_selector(".c-comment--optimistic", state="detached")
#
#     await page.setViewportSize({ width: 800, height: 1000 })
#     await page.screenshot({ path: ".github/screenshots/comments-sending.png" })
#
#     # Verify the comment was added
#     comments_list = page.locator("#comments-list")
#     first_comment = comments_list.locator("li").first
#     expect(first_comment.locator('[data-field="author"]')).to_contain_text(test_author)
#     expect(first_comment.locator('[data-field="body"]')).to_contain_text(test_body)
#     expect(first_comment.locator('[data-field="time"]')).not_to_contain_text("(sending…)")
