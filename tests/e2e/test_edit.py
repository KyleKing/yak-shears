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

    file_path = MOCK_YAK_DIR / "file1.dj"
    await page.goto(f"/edit?file={file_path}")
    editor = page.locator(".editor")
    await expect(editor).to_be_editable()

    await _validate_highlight(page, "_em_", "em")
    await _validate_highlight(page, "*strong*", "strong")
    for idx in (1, 3, 6):
        await _validate_highlight(page, f"{'#' * idx} Title", f".heading.h{idx}")
    await _validate_highlight(page, "- [x] done", ".checkbox.checked", "[x]")
    await _validate_highlight(page, "- [ ] incomplete", ".checkbox.unchecked", "[ ]")

    # PLANNED: Integrate with Prism.js (v2 on master) or Highlight.js for syntax highlighting within code blocks

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

    file_path = MOCK_YAK_DIR / "file1.dj"
    await page.goto(f"/edit?file={file_path}")

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
