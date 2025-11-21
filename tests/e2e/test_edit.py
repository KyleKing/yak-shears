import pytest
from playwright.async_api import BrowserContext, Page, expect

from tests.conftest import MOCK_YAK_DIR

from ._helpers import login


async def _fill_editor(page: Page, fill: str) -> None:
    editor = page.locator(".editor")
    # Fill sets the content directly, bypassing the KeyUp event expected by CodeJar
    await editor.fill("")
    await editor.type(fill)


async def _validate_highlight(page: Page, fill: str, editor_locator: str, expected: str = "") -> None:
    """Enter specified text into the editor and verify expected highlighting."""
    await _fill_editor(page=page, fill=fill)

    editor = page.locator(".editor")
    highlighted = editor.locator(editor_locator)
    await expect(highlighted).to_be_visible()
    await expect(highlighted).to_contain_text(expected or fill)


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_editor_highlight_behavior(context: BrowserContext, page: Page, server_lifecycle):
    await login(context, page)

    await page.goto("/edit?yak=yak1.dj")
    await page.screenshot(path=".github/screenshots/edit-page.png")
    editor = page.locator(".editor")
    await expect(editor).to_be_editable()

    await _validate_highlight(page, "_em_", "em")
    await _validate_highlight(page, "*strong*", "strong")
    for idx in (1, 3, 6):
        await _validate_highlight(page, f"{'#' * idx} Title", f".heading.h{idx}")
    await _validate_highlight(page, "- [x] done", ".checkbox.checked", "[x]")
    await _validate_highlight(page, "- [ ] incomplete", ".checkbox.unchecked", "[ ]")

    # TODO: Implement and test auto-completion for:
    # = List indention (tab and shift-tab to cycle list or not, and introduce newline above if indenting beyond prior)
    # - Ctrl-L to toggle checklist state (none, unchecked, checked)
    # - List items (on enter, auto-complete `-`, `1.`, or `- [ ]`)
    # = Doesn't autocomplete brackets, parenthesis, or `

    # PLANNED: Test HTML Escaping
    await editor.fill("<tag>")
    await expect(editor).to_contain_text("<tag>")

    # Test does not lose characters
    fill = "*bold _and_ more*\n Next line"
    await _validate_highlight(page, fill, "strong em", "_and_")
    await expect(editor).to_contain_text(fill.replace("\n", ""))


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_edit_save_persistence(context: BrowserContext, page: Page, server_lifecycle):
    """Test that edits are saved and persist after page refresh."""
    await login(context, page)

    # TODO: Find a way for server_lifecycle with configurable directories
    yak_path = MOCK_YAK_DIR / "yak0-untracked.dj"
    yak_path.write_text("Placeholder")
    try:
        await page.goto(f"/edit?yak={yak_path}")

        editor = page.locator(".editor")
        await expect(editor).to_be_editable()

        # Get initial content
        initial_content = await editor.text_content()
        assert initial_content is not None

        modified_content = initial_content + "\n\nModified for test"
        await _fill_editor(page=page, fill=modified_content)
        await page.locator("#save-btn").click()
        await expect(page.locator("#save-status")).to_contain_text("Saved")

        # Refresh page to ensure changes are persisted
        await page.reload()
        await expect(editor).to_be_editable()
        await expect(editor).to_contain_text(modified_content)

        # Restore original content
        await _fill_editor(page=page, fill=initial_content)
        await page.locator("#save-btn").click()
        await expect(page.locator("#save-status")).to_contain_text("Saved")
    finally:
        yak_path.unlink()


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_delete_yak(context: BrowserContext, page: Page, server_lifecycle):
    """Test that a yak can be deleted with confirmation."""
    await login(context, page)

    # Create a test yak
    yak_path = MOCK_YAK_DIR / "yak-delete-test.dj"
    yak_path.write_text("Test content for deletion")
    try:
        await page.goto(f"/edit?yak={yak_path}")

        # Click delete button and confirm
        delete_button = page.locator("button:has-text('Delete Yak')")
        await expect(delete_button).to_be_visible()

        # Handle the confirm dialog
        page.on("dialog", lambda dialog: dialog.accept())

        await delete_button.click()

        # Should redirect to /yaks
        await page.wait_for_url("**/yaks")

    finally:
        # Clean up if not deleted
        if yak_path.exists():
            yak_path.unlink()


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_preview_syntax_highlighting(context: BrowserContext, page: Page, server_lifecycle):
    """Test that code blocks in the preview are syntax highlighted using Prism.js."""
    await login(context, page)

    await page.goto("/edit?yak=yak1.dj")

    # Switch to side-by-side view to show preview
    await page.locator("button[data-view='side-by-side']").click()

    # Fill editor with content containing a code block
    test_content = "Some text\n\n```python\nimport os\nprint('hello')\n```"
    await _fill_editor(page=page, fill=test_content)

    # Wait for preview to update
    await page.wait_for_timeout(1000)

    # Check that the preview contains code block with correct language class
    preview = page.locator("#preview-content")
    code_block = preview.locator("pre code.language-python")
    await expect(code_block).to_be_visible()
    await expect(code_block).to_contain_text("import")


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_text_stability_during_editing(context: BrowserContext, page: Page, server_lifecycle):
    """Test that text doesn't jump around when editing with highlighting enabled."""
    await login(context, page)

    await page.goto("/edit?yak=yak1.dj")
    editor = page.locator(".editor")
    await expect(editor).to_be_editable()

    # Test case: clicking after "1" in "line 1\n\n```py\nimport *\n```" and pressing backspace
    # should not cause newlines to disappear
    test_content = "line 1\n\n```py\nimport *\n```"
    await _fill_editor(page=page, fill=test_content)

    # Position cursor after "1" by moving left from the end
    # Total length is 26, position after "1" is 6, so move left 20 times
    for _ in range(20):
        await page.keyboard.press("ArrowLeft")

    # Press backspace
    await page.keyboard.press("Backspace")

    # Verify the content is correct (should be "line \n\n```py\nimport *\n```")
    expected_content = "line \n\n```py\nimport *\n```"
    await expect(editor).to_contain_text(expected_content)

    # Also verify the full content matches exactly
    actual_content = await editor.text_content()
    assert actual_content == expected_content


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_view_mode_toggles(context: BrowserContext, page: Page, server_lifecycle):
    """Test view mode toggles work correctly."""
    await login(context, page)

    await page.goto("/edit?yak=yak1.dj")

    # Test Editor-only view
    editor_btn = page.locator("button[data-view='editor-only']")
    await editor_btn.click()
    container = page.locator(".editor-container")
    await expect(container).to_have_class(/editor-only/)

    # Test Side-by-side view
    sidebyside_btn = page.locator("button[data-view='side-by-side']")
    await sidebyside_btn.click()
    await expect(container).to_have_class(/side-by-side/)

    # Test Preview-only view
    preview_btn = page.locator("button[data-view='preview-only']")
    await preview_btn.click()
    await expect(container).to_have_class(/preview-only/)
