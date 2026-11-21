import re

import pytest
from playwright.async_api import BrowserContext, Locator, Page, ViewportSize, expect

from tests.conftest import MOCK_YAK_DIR

from ._helpers import login, maybe_screenshot, open_menu


async def _open_editor(context: BrowserContext, page: Page, yak: str = "yak1.dj") -> Locator:
    """Log in, open the editor on `yak`, and hand back the editor locator."""
    await login(context, page)
    await page.goto(f"/edit?yak={yak}")
    editor = page.locator(".editor")
    await expect(editor).to_be_editable()
    return editor


async def _fill_editor(page: Page, fill: str) -> None:
    editor = page.locator(".editor")
    # Typed rather than filled, so Enter and friends run the editor's key handlers
    await editor.fill("")
    await editor.type(fill)


async def _expect_editor_text(page: Page, expected: str) -> None:
    """Wait for the editor to hold exactly `expected`.

    A bare read races the keypress or click that drives the change, so this
    waits for the textarea's value to match exactly, indentation included.
    """
    await page.wait_for_function(
        "expected => document.querySelector('.editor').value === expected",
        arg=expected,
    )


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_editor_holds_plain_text(context: BrowserContext, page: Page, server_lifecycle):
    """The editor is a textarea: markup is kept as typed, never rendered or rewritten."""
    await login(context, page)

    await page.goto("/edit?yak=yak1.dj")
    await maybe_screenshot(page, ".github/screenshots/edit-page.png")
    editor = page.locator("textarea.editor")
    await expect(editor).to_be_editable()

    for fill in ("<tag> & *bold _and_ more*", "# Title\n\n- [x] done"):
        await _fill_editor(page=page, fill=fill)
        await expect(editor).to_have_value(fill)


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_edit_save_persistence(context: BrowserContext, page: Page, server_lifecycle):
    """Test that edits are saved and persist after page refresh.

    NOT SAFE FOR PARALLEL: Modifies shared MOCK_YAK_DIR.
    TODO: Refactor to use worker-specific test directories.
    """
    await login(context, page)

    # TODO: Find a way for server_lifecycle with configurable directories
    yak_path = MOCK_YAK_DIR / "yak0-untracked.dj"
    yak_path.write_text("Placeholder")
    try:
        await page.goto(f"/edit?yak={yak_path.name}")

        editor = page.locator(".editor")
        await expect(editor).to_be_editable()

        # Get initial content
        initial_content = await editor.input_value()

        modified_content = initial_content + "\n\nModified for test"
        await _fill_editor(page=page, fill=modified_content)
        await page.locator("#save-btn").click()
        await expect(page.locator("#save-status")).to_contain_text("Saved")

        # Refresh page to ensure changes are persisted
        await page.reload()
        await expect(editor).to_be_editable()
        await expect(editor).to_have_value(modified_content)

        # Restore original content
        await _fill_editor(page=page, fill=initial_content)
        await page.locator("#save-btn").click()
        await expect(page.locator("#save-status")).to_contain_text("Saved")
    finally:
        yak_path.unlink()


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_delete_yak(context: BrowserContext, page: Page, server_lifecycle):
    """Test that a yak can be deleted with confirmation.

    NOT SAFE FOR PARALLEL: Modifies shared MOCK_YAK_DIR.
    TODO: Refactor to use worker-specific test directories.
    """
    await login(context, page)

    # Create a test yak
    yak_path = MOCK_YAK_DIR / "yak-delete-test.dj"
    yak_path.write_text("Test content for deletion")
    try:
        await page.goto(f"/edit?yak={yak_path.name}")

        await open_menu(page)

        # Register handler for confirm dialog
        page.on("dialog", lambda dialog: dialog.accept())
        # Then click delete
        delete_button = page.locator("button.button--danger-ghost")
        await expect(delete_button).to_be_visible()
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

    await open_menu(page, pin=True)

    # Switch to side-by-side view to show preview
    await page.locator("button[data-view='side-by-side']").click()

    # Fill editor with content containing a code block
    test_content = "Some text\n\n```python\nimport os\nprint('hello')\n```\n"
    await _fill_editor(page=page, fill=test_content)

    # Check that the preview contains code block with correct language class
    preview = page.locator("#preview-content")
    code_block = preview.locator("pre code.language-python")
    await expect(code_block).to_be_visible()
    await expect(code_block.locator(".token.keyword").first).to_contain_text("import")
    await expect(code_block.locator(".token.punctuation").first).to_contain_text("(")


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_text_stability_during_editing(context: BrowserContext, page: Page, server_lifecycle):
    """Test that text doesn't jump around when editing with highlighting enabled."""
    editor = await _open_editor(context, page)

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
    await expect(editor).to_have_value(expected_content)


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_view_mode_toggles(context: BrowserContext, page: Page, server_lifecycle):
    """Test view mode toggles work correctly."""
    await login(context, page)

    await page.goto("/edit?yak=yak1.dj")

    await open_menu(page, pin=True)

    # Test Editor view
    editor_btn = page.locator("button[data-view='editor']")
    await editor_btn.click()
    container = page.locator(".editor-container")
    await expect(container).to_have_class(re.compile(r"editor\b"))

    # Test Side-by-side view
    sidebyside_btn = page.locator("button[data-view='side-by-side']")
    await sidebyside_btn.click()
    await expect(container).to_have_class(re.compile(r"sidebyside\b"))

    # Test Preview view
    preview_btn = page.locator("button[data-view='preview']")
    await preview_btn.click()
    await expect(container).to_have_class(re.compile(r"previewonly\b"))


# ============================================================================
# List Continuation Tests
# ============================================================================


@pytest.mark.playwright
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        ("- item 1", "- item 1\n- "),
        ("1. first item", "1. first item\n2. "),
        ("- [ ] task 1", "- [ ] task 1\n- [ ] "),
    ],
    ids=["bullet-repeats", "number-increments", "checklist-comes-back-unchecked"],
)
async def test_enter_continues_a_list(context: BrowserContext, page: Page, server_lifecycle, *, typed, expected):
    """Enter carries the list marker onto the next line."""
    editor = await _open_editor(context, page)

    await _fill_editor(page, typed)
    await page.keyboard.press("Enter")

    await _expect_editor_text(page, expected)


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_list_continuation_exit_on_empty(context: BrowserContext, page: Page, server_lifecycle):
    """Test empty list item removes marker and exits list mode."""
    editor = await _open_editor(context, page)

    # Type a list item, press Enter to get continuation, then Enter again to exit
    await _fill_editor(page, "- item")
    await page.keyboard.press("Enter")
    # Now we have "- item\n- ", pressing Enter should remove the empty marker
    await page.keyboard.press("Enter")

    await _expect_editor_text(page, "- item\n")


# ============================================================================
# Checklist Toggle Tests (Ctrl+L)
# ============================================================================


@pytest.mark.playwright
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        ("some text", "- [ ] some text"),
        ("- bullet item", "- [ ] bullet item"),
        ("- [ ] task", "- [x] task"),
        ("- [x] done task", "- done task"),
    ],
    ids=["plain-to-unchecked", "bullet-to-unchecked", "unchecked-to-checked", "checked-to-bullet"],
)
async def test_ctrl_l_cycles_the_checklist_marker(
    context: BrowserContext, page: Page, server_lifecycle, *, typed, expected
):
    """Ctrl+L walks a line around the checked, bullet, unchecked cycle."""
    editor = await _open_editor(context, page)

    await _fill_editor(page, typed)
    await page.keyboard.press("Control+l")

    await _expect_editor_text(page, expected)


# ============================================================================
# List Indentation Tests (Tab/Shift+Tab)
# ============================================================================


@pytest.mark.playwright
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("typed", "key", "expected"),
    [
        ("- item", "Tab", "    - item"),
        ("1. numbered item", "Tab", "    1. numbered item"),
        ("    - indented item", "Shift+Tab", "- indented item"),
    ],
    ids=["bullet-indents", "number-keeps-its-content", "shift-tab-outdents"],
)
async def test_tab_shifts_one_list_item(context: BrowserContext, page: Page, server_lifecycle, *, typed, key, expected):
    """Tab and Shift+Tab move a single item one level."""
    editor = await _open_editor(context, page)

    await _fill_editor(page, typed)
    await page.keyboard.press(key)

    await _expect_editor_text(page, expected)


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_list_indent_inserts_blank_before_nested(context: BrowserContext, page: Page, server_lifecycle):
    """Indenting an item under a parent inserts the blank line Djot needs to nest it."""
    editor = await _open_editor(context, page)

    # Set a flat two-item list with the caret at the end of the child line so this
    # exercises only the indent path.
    await page.evaluate(
        """() => {
            window.jar.updateCode("- parent\\n- child");
            const ed = document.querySelector(".editor");
            ed.focus();
            ed.setSelectionRange(ed.value.length, ed.value.length);
        }"""
    )
    await page.keyboard.press("Tab")

    await _expect_editor_text(page, "- parent\n\n    - child")


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_list_outdent_removes_nested_blank(context: BrowserContext, page: Page, server_lifecycle):
    """Outdenting a nested item removes the blank separator that indenting added."""
    editor = await _open_editor(context, page)

    # Set the nested state directly with the caret at the end of the child line so
    # this exercises only the outdent path (chaining Tab+Shift+Tab races the caret).
    await page.evaluate(
        """() => {
            window.jar.updateCode("- parent\\n\\n    - child");
            const ed = document.querySelector(".editor");
            ed.focus();
            ed.setSelectionRange(ed.value.length, ed.value.length);
        }"""
    )
    await page.keyboard.press("Shift+Tab")

    await _expect_editor_text(page, "- parent\n- child")


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_list_indent_stops_beyond_one_level(context: BrowserContext, page: Page, server_lifecycle):
    """A child already one level under its parent cannot indent a second level deeper."""
    editor = await _open_editor(context, page)

    # Child is nested one level under a top-level parent; a further Tab would make it
    # two levels deeper than the parent, which Djot cannot parse, so it must no-op.
    await page.evaluate(
        """() => {
            window.jar.updateCode("- parent\\n\\n    - child");
            const ed = document.querySelector(".editor");
            ed.focus();
            ed.setSelectionRange(ed.value.length, ed.value.length);
        }"""
    )
    await page.keyboard.press("Tab")

    await _expect_editor_text(page, "- parent\n\n    - child")


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_wrap_toggle_rewraps_editor(context: BrowserContext, page: Page, server_lifecycle):
    """The wrap toggle flips the editor itself between soft-wrap and no-wrap."""
    await _open_editor(context, page)

    async def white_space() -> str:
        return await page.evaluate("() => getComputedStyle(document.querySelector('.editor')).whiteSpace")

    # Default is wrapped.
    assert await white_space() == "pre-wrap"

    await open_menu(page)
    wrap_toggle = page.locator("#wrap-toggle")
    await wrap_toggle.click()
    assert await white_space() == "pre"

    await wrap_toggle.click()
    assert await white_space() == "pre-wrap"


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_parked_metadata_panel_is_out_of_reach(context: BrowserContext, page: Page, server_lifecycle):
    """The closed panel sits offscreen, so its controls must leave the tab order rather than
    sit at x=1282 in a 1280px viewport waiting to be tabbed into."""
    await _open_editor(context, page)
    wrap_toggle = page.locator("#wrap-toggle")
    await expect(wrap_toggle).to_be_hidden()

    await page.locator(".editor").click()
    for _ in range(12):
        await page.keyboard.press("Tab")
        focused = await page.evaluate("() => document.activeElement?.id || ''")
        assert focused != "wrap-toggle"

    await open_menu(page)
    await expect(wrap_toggle).to_be_visible()


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_wrap_default_on_with_no_stored_preference(context: BrowserContext, page: Page, server_lifecycle):
    """With no localStorage entry at all, the editor loads wrapped."""
    await login(context, page)
    await page.goto("/edit?yak=yak1.dj")
    await page.evaluate("() => localStorage.removeItem('editorWrap')")

    await page.reload()
    editor = page.locator(".editor")
    await expect(editor).to_be_editable()

    white_space = await page.evaluate("() => getComputedStyle(document.querySelector('.editor')).whiteSpace")
    assert white_space == "pre-wrap"
    assert await page.evaluate("() => localStorage.getItem('editorWrap')") == "true"


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_wrap_off_preference_persists_across_pages(context: BrowserContext, page: Page, server_lifecycle):
    """Turning wrap off is written to localStorage and still applies after navigating away and back."""
    editor = await _open_editor(context, page)

    await open_menu(page)
    await page.locator("#wrap-toggle").click()
    assert await page.evaluate("() => localStorage.getItem('editorWrap')") == "false"

    async def white_space() -> str:
        return await page.evaluate("() => getComputedStyle(document.querySelector('.editor')).whiteSpace")

    assert await white_space() == "pre"

    # Navigate to a different yak entirely (not just a reload) to confirm the
    # preference is read from localStorage on every page load, not per-document state.
    await page.goto("/edit?yak=subdirectory-2/yak2.dj")
    await expect(editor).to_be_editable()
    assert await white_space() == "pre"
    assert await page.evaluate("() => localStorage.getItem('editorWrap')") == "false"


# ============================================================================
# Draft Recovery Tests
# ============================================================================


@pytest.mark.skip(reason="Pending editor.js/main.css wiring for #draft-toggle; see PLAN.md draft recovery item")
@pytest.mark.playwright
@pytest.mark.asyncio
async def test_draft_toggle_recovers_local_changes(context: BrowserContext, page: Page, server_lifecycle):
    """Draft bar appears for unsaved localStorage changes and swaps versions losslessly."""
    editor = await _open_editor(context, page)
    toggle = page.locator("#draft-toggle")
    await expect(toggle).to_be_hidden()

    server_content = await editor.input_value()
    draft = server_content + "\nlocal draft line"
    await page.evaluate("(draft) => localStorage.setItem('editor_yak1.dj', draft)", draft)

    await page.reload()
    await expect(editor).to_be_editable()
    await expect(toggle).to_be_visible()
    await expect(editor).not_to_have_value(re.compile(r"local draft line"))

    await page.locator("#draft-local-btn").click()
    await expect(editor).to_have_value(re.compile(r"local draft line"))
    await expect(page.locator("#save-status")).to_contain_text("Modified")

    await page.locator("#draft-server-btn").click()
    await expect(editor).not_to_have_value(re.compile(r"local draft line"))

    # Previewing the server version must not delete the stored draft
    stored = await page.evaluate("() => localStorage.getItem('editor_yak1.dj')")
    assert stored == draft
    await page.evaluate("() => localStorage.removeItem('editor_yak1.dj')")


# ============================================================================
# Mobile Accessory Toolbar and Drag-Drop Tests
# ============================================================================

IPHONE_14_VIEWPORT = ViewportSize(width=390, height=844)

_SET_CODE_AND_CARET = """
    ([code, start, end]) => {
        window.jar.updateCode(code);
        const ed = document.querySelector(".editor");
        ed.focus();
        ed.setSelectionRange(start, end);
    }
"""


async def _set_code_and_select(page: Page, code: str, start: int, end: int) -> None:
    await page.evaluate(_SET_CODE_AND_CARET, [code, start, end])


async def _open_panel(page: Page) -> None:
    """Open the command panel, which closes itself after every applied change."""
    await page.click("#cmd-trigger")
    await expect(page.locator("#cmd-panel")).to_be_visible()


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_command_panel_indents_and_outdents(touch_page: Page, server_lifecycle):
    """The panel opens from its trigger and drives list indentation."""
    page = touch_page
    await _open_editor(page.context, page)

    await _set_code_and_select(page, "- item", 6, 6)
    await _open_panel(page)
    await page.locator("[data-action='indent']").click()
    await _expect_editor_text(page, "    - item")

    await _open_panel(page)
    await page.locator("[data-action='outdent']").click()
    await _expect_editor_text(page, "- item")


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_command_panel_closes_after_applying(touch_page: Page, server_lifecycle):
    """Every applied change closes the panel, so it never holds stale state."""
    page = touch_page
    await _open_editor(page.context, page)

    await _set_code_and_select(page, "- item", 6, 6)
    await _open_panel(page)
    await page.locator("[data-action='indent']").click()

    await expect(page.locator("#cmd-panel")).to_be_hidden()
    await expect(page.locator("#cmd-trigger")).to_have_attribute("aria-expanded", "false")


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_command_panel_cancel_applies_nothing(touch_page: Page, server_lifecycle):
    """Cancel closes the panel and leaves the note alone."""
    page = touch_page
    await _open_editor(page.context, page)

    await _set_code_and_select(page, "- item", 6, 6)
    await _open_panel(page)
    await page.click("#cmd-cancel")

    await expect(page.locator("#cmd-panel")).to_be_hidden()
    await _expect_editor_text(page, "- item")


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_command_panel_hidden_for_a_fine_pointer(context: BrowserContext, page: Page, server_lifecycle):
    """A touchscreen is what makes the key bindings unreachable, so a mouse gets no panel."""
    await login(context, page)
    await page.set_viewport_size({"width": 1280, "height": 900})
    await page.goto("/edit?yak=yak1.dj")

    await expect(page.locator(".editor")).to_be_editable()
    await expect(page.locator("#cmd")).to_be_hidden()


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_count_repeats_outdent(touch_page: Page, server_lifecycle):
    """A count of 3 outdents three levels in one press."""
    page = touch_page
    await _open_editor(page.context, page)

    await _set_code_and_select(page, "            - item", 18, 18)
    await _open_panel(page)
    await page.click("[data-count='3']")
    await page.locator("[data-action='outdent']").click()

    await _expect_editor_text(page, "- item")


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_count_stops_early_rather_than_refusing(touch_page: Page, server_lifecycle):
    """Outdenting five levels from two levels deep outdents twice."""
    page = touch_page
    await _open_editor(page.context, page)

    await _set_code_and_select(page, "        - item", 14, 14)
    await _open_panel(page)
    await page.click("[data-count='5']")
    await page.locator("[data-action='outdent']").click()

    await _expect_editor_text(page, "- item")


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_count_leaves_a_non_repeating_command_alone(touch_page: Page, server_lifecycle):
    """Bold at a count of 3 is bold once, and its key never goes dead."""
    page = touch_page
    await _open_editor(page.context, page)

    await _set_code_and_select(page, "hello world", 6, 11)
    await _open_panel(page)
    await page.click("[data-count='3']")

    bold = page.locator("[data-action='bold']")
    await expect(bold).to_be_enabled()
    await bold.click()

    await _expect_editor_text(page, "hello *world*")


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_compose_applies_several_commands(touch_page: Page, server_lifecycle):
    """Composing lights commands and applies them together."""
    page = touch_page
    await _open_editor(page.context, page)

    await _set_code_and_select(page, "- item", 6, 6)
    await _open_panel(page)
    await page.click("#cmd-compose")

    await page.locator("[data-action='indent']").click()
    await page.locator("[data-action='bold']").click()
    await _expect_editor_text(page, "- item")

    await page.click("#cmd-apply")
    await _expect_editor_text(page, "    - *item*")


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_compose_unlights_a_second_tap(touch_page: Page, server_lifecycle):
    """A second tap takes a command out rather than queueing it twice."""
    page = touch_page
    await _open_editor(page.context, page)

    await _set_code_and_select(page, "    - item", 10, 10)
    await _open_panel(page)
    await page.click("#cmd-compose")

    outdent = page.locator("[data-action='outdent']")
    await outdent.click()
    await expect(outdent).to_have_class(re.compile(r"cmd__key--lit"))
    await outdent.click()
    await expect(outdent).not_to_have_class(re.compile(r"cmd__key--lit"))

    await page.click("#cmd-apply")
    await _expect_editor_text(page, "    - item")


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_scope_line_wraps_past_the_list_marker(touch_page: Page, server_lifecycle):
    """With no selection, line scope wraps the line's text and leaves the marker outside."""
    page = touch_page
    await _open_editor(page.context, page)

    await _set_code_and_select(page, "- buy more milk", 8, 8)
    await _open_panel(page)
    await page.locator("[data-action='bold']").click()

    await _expect_editor_text(page, "- *buy more milk*")


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_scope_word_wraps_only_the_caret_word(touch_page: Page, server_lifecycle):
    """Thrown to word, the same press wraps just the word the caret is touching."""
    page = touch_page
    await _open_editor(page.context, page)

    await _set_code_and_select(page, "- buy more milk", 8, 8)
    await _open_panel(page)
    await page.click("[data-scope='word']")
    await page.locator("[data-action='bold']").click()

    await _expect_editor_text(page, "- buy *more* milk")


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_command_panel_bold_wraps_selection(touch_page: Page, server_lifecycle):
    """Bold wraps the selection in Djot strong markers."""
    page = touch_page
    await _open_editor(page.context, page)

    await _set_code_and_select(page, "hello world", 6, 11)
    await _open_panel(page)
    await page.locator("[data-action='bold']").click()
    await _expect_editor_text(page, "hello *world*")


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_command_panel_bold_unwraps_selection(touch_page: Page, server_lifecycle):
    """Bold strips the markers when the selection is already strong."""
    page = touch_page
    await _open_editor(page.context, page)

    await _set_code_and_select(page, "hello *world*", 6, 13)
    await _open_panel(page)
    await page.locator("[data-action='bold']").click()
    await _expect_editor_text(page, "hello world")


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_dropped_image_uploads_instead_of_embedding(context: BrowserContext, page: Page, server_lifecycle):
    """A dropped image is uploaded and inserted as Djot, never dropped in as a path or data URL."""
    editor = await _open_editor(context, page)

    uploads: list[str] = []

    async def handle_upload(route):
        uploads.append(route.request.method)
        await route.fulfill(
            status=200,
            content_type="application/json",
            body='{"snippet": "![drop](/media/drop.png)"}',
        )

    await page.route("**/media/upload", handle_upload)

    await page.evaluate('() => window.jar.updateCode("start")')
    await page.evaluate(
        """() => {
            const transfer = new DataTransfer();
            transfer.items.add(new File([new Uint8Array([1, 2, 3])], "drop.png", { type: "image/png" }));
            const ed = document.querySelector(".editor");
            ed.focus();
            ed.dispatchEvent(new DragEvent("drop", { dataTransfer: transfer, bubbles: true, cancelable: true }));
        }"""
    )

    await expect(editor).to_have_value(re.compile(re.escape("![drop](/media/drop.png)")))
    assert uploads == ["POST"], f"Expected one POST to /media/upload but got {uploads}"


# ============================================================================
# Caret Stability Tests
# ============================================================================

_READ_CARET = """() => document.querySelector(".editor").selectionStart"""

# The editor handles keys in the capture phase, so a bubble-phase listener on the
# document reads the caret the handler left behind, within the same event.
_RECORD_CARET_AFTER_KEYDOWN = f"""
    () => {{
        const read = {_READ_CARET};
        document.addEventListener("keydown", () => {{
            window.__caretAfterKeydown = read();
        }});
    }}
"""


def _long_document() -> str:
    """A document long enough that a caret slipping to either end is unmistakable."""
    lines = ["# Long note", ""]
    for idx in range(20):
        lines += [f"## Section {idx}", "", f"Prose paragraph {idx} with *bold* and _em_ text.", ""]
    lines += ["- alpha", "- bravo", "- charlie", ""]
    for idx in range(20):
        lines += [f"Trailing paragraph {idx}.", ""]
    return "\n".join(lines)


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_reopening_a_note_restores_the_caret(context: BrowserContext, page: Page, server_lifecycle):
    """A note reopens where it was left, and one never edited opens at the top."""
    editor = await _open_editor(context, page)
    await expect(editor).to_be_editable()

    opened_at = await page.evaluate(_READ_CARET)
    assert opened_at == 0, f"An unvisited note opened at {opened_at}"

    await page.evaluate(
        """() => {
            const ed = document.querySelector(".editor");
            ed.focus();
            ed.setSelectionRange(5, 5);
            ed.dispatchEvent(new Event("selectionchange"));
        }"""
    )
    await page.reload()
    await expect(page.locator(".editor")).to_be_editable()

    reopened_at = await page.evaluate(_READ_CARET)
    assert reopened_at == 5, f"The note reopened at {reopened_at}"


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_typing_a_wikilink_offers_other_notes(context: BrowserContext, page: Page, server_lifecycle):
    """`[[` opens the completion over every note but the one being edited, and picking one closes the link."""
    await _open_editor(context, page)
    await _fill_editor(page=page, fill="see [[yak")

    popup = page.locator("#linkbar")
    await expect(popup).to_be_visible()
    rows = popup.locator(".linkbar__row")
    await expect(rows).to_have_count(2)
    assert "yak1" not in " ".join(await rows.all_text_contents())

    await page.keyboard.press("ArrowDown")
    await page.keyboard.press("Enter")

    await expect(popup).to_be_hidden()
    text = await page.evaluate("() => window.jar.toString()")
    assert text.startswith("see [[yak3]]"), text

    # Ctrl+K is the second trigger on the same resolver, and a selection becomes the query.
    await _fill_editor(page=page, fill="yak2")
    await page.keyboard.press("ControlOrMeta+a")
    await page.keyboard.press("ControlOrMeta+k")
    await expect(rows).to_have_count(1)
    await page.keyboard.press("Enter")
    assert await page.evaluate("() => window.jar.toString()") == "[[yak2]]"


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_indent_never_parks_the_caret_at_the_end(context: BrowserContext, page: Page, server_lifecycle):
    """Indenting mid-document leaves the caret on the line being edited.

    The caret is read inside the keydown that triggered the indent, so a restore
    deferred to a later frame reads as the jump to the end of the document that
    it looks like on screen.
    """
    await _open_editor(context, page)

    document_text = _long_document()
    caret = document_text.index("- bravo") + len("- bravo")
    await page.evaluate(_RECORD_CARET_AFTER_KEYDOWN)
    await _set_code_and_select(page, document_text, caret, caret)

    await page.keyboard.press("Tab")

    # Four spaces of indent plus the blank line Djot needs ahead of a nested list.
    expected = caret + 5
    during = await page.evaluate("() => window.__caretAfterKeydown")
    assert during == expected, f"Caret was at {during} rather than {expected} when the indent finished"
    assert await page.evaluate(_READ_CARET) == expected


# ============================================================================
# Undo, Multi-line Indentation, and Media Insertion Tests
# ============================================================================


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_undo_steps_back_over_a_list_command(context: BrowserContext, page: Page, server_lifecycle):
    """Indenting is one undo step, on the browser's own undo stack.

    Commands replace only the changed span through execCommand("insertText"), which
    joins native undo; assigning the textarea's value would wipe it instead.
    """
    await _open_editor(context, page)

    flat = "- alpha\n- bravo"
    caret = len(flat)
    await _set_code_and_select(page, flat, caret, caret)
    await page.keyboard.press("Tab")
    await _expect_editor_text(page, "- alpha\n\n    - bravo")

    await page.keyboard.press("ControlOrMeta+z")

    await _expect_editor_text(page, flat)
    # Native undo puts the caret where the undone change began, which is on the
    # line that was indented, not wherever it was before the command.
    bravo_line = flat.index("- bravo")
    assert bravo_line - 1 <= await page.evaluate(_READ_CARET) <= caret


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_tab_indents_every_selected_list_item(context: BrowserContext, page: Page, server_lifecycle):
    """A selection spanning several items indents all of them, not just the first."""
    await _open_editor(context, page)

    # From inside "alpha" to inside "charlie", so every item is touched.
    await _set_code_and_select(page, "- intro\n\n- alpha\n- bravo\n- charlie", 12, 31)
    await page.keyboard.press("Tab")

    await _expect_editor_text(page, "- intro\n\n    - alpha\n    - bravo\n    - charlie")


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_tab_keeps_the_selection_across_the_indent(context: BrowserContext, page: Page, server_lifecycle):
    """The selection still covers the same items, so a second Tab indents them again."""
    await _open_editor(context, page)

    await _set_code_and_select(page, "- intro\n\n- alpha\n- bravo", 11, 24)
    await page.keyboard.press("Tab")
    await _expect_editor_text(page, "- intro\n\n    - alpha\n    - bravo")

    selected = await page.evaluate(
        """() => {
            const ed = document.querySelector(".editor");
            return ed.value.substring(ed.selectionStart, ed.selectionEnd);
        }"""
    )
    assert selected == "alpha\n    - bravo", f"Selection became {selected!r}"


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_shift_tab_outdents_every_selected_list_item(context: BrowserContext, page: Page, server_lifecycle):
    """Shift+Tab walks the whole selected block back one level."""
    await _open_editor(context, page)

    await _set_code_and_select(page, "- intro\n\n    - alpha\n    - bravo", 16, 30)
    await page.keyboard.press("Shift+Tab")

    await _expect_editor_text(page, "- intro\n- alpha\n- bravo")


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_media_snippet_lands_at_the_caret_without_exec_command(
    context: BrowserContext, page: Page, server_lifecycle
):
    """With execCommand refused, the snippet still goes where the caret is.

    The fallback used to append to the end of the note, which moves content the
    reader never asked to move.
    """
    await _open_editor(context, page)

    async def handle_upload(route):
        await route.fulfill(
            status=200,
            content_type="application/json",
            body='{"snippet": "![drop](/media/drop.png)"}',
        )

    await page.route("**/media/upload", handle_upload)

    await _set_code_and_select(page, "alpha\nbravo\ncharlie", 5, 5)
    await page.evaluate("() => { document.execCommand = () => false; }")
    await page.evaluate(
        """() => {
            const transfer = new DataTransfer();
            transfer.items.add(new File([new Uint8Array([1])], "drop.png", { type: "image/png" }));
            const ed = document.querySelector(".editor");
            ed.dispatchEvent(new DragEvent("drop", { dataTransfer: transfer, bubbles: true, cancelable: true }));
        }"""
    )

    await _expect_editor_text(page, "alpha\n![drop](/media/drop.png)\n\nbravo\ncharlie")


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_command_panel_media_key_opens_the_picker(touch_page: Page, server_lifecycle):
    """The bottom bar's Media button sits under the keyboard, so the panel carries one too."""
    page = touch_page
    await _open_editor(page.context, page)

    await page.evaluate(
        """() => {
            window.pickerOpened = 0;
            document.getElementById("media-input").addEventListener("click", (event) => {
                event.preventDefault();
                window.pickerOpened += 1;
            });
        }"""
    )

    await _set_code_and_select(page, "- item", 6, 6)
    await _open_panel(page)
    await page.click('#cmd-panel [data-action="media"]')

    assert await page.evaluate("() => window.pickerOpened") == 1
    await expect(page.locator("#cmd-panel")).to_be_hidden()
    await _expect_editor_text(page, "- item")


@pytest.mark.allow_console_errors
@pytest.mark.playwright
@pytest.mark.asyncio
async def test_a_refused_save_shows_the_difference(context: BrowserContext, page: Page, server_lifecycle):
    """Being told the note changed is not enough to decide with, so the panel shows what changed."""
    await _open_editor(context, page)
    await _fill_editor(page=page, fill="mine only\nshared line")
    # A stale lease is what the server sees when the file moved underneath, without
    # this test writing to the committed fixture vault to arrange it.
    await page.evaluate('() => { document.getElementById("yak-lease").dataset.lease = "0000000000000000"; }')

    await page.click("#save-btn")

    conflict = page.locator("#conflict")
    await expect(conflict).to_be_visible()
    await expect(page.locator("#conflict-diff .diffline--mine").filter(has_text="mine only")).to_be_visible()
    await expect(page.locator("#conflict-diff .diffline--theirs").first).to_be_visible()


@pytest.mark.allow_console_errors
@pytest.mark.playwright
@pytest.mark.asyncio
async def test_resolving_by_hand_marks_the_buffer_and_guards_the_save(
    context: BrowserContext, page: Page, server_lifecycle
):
    """Markers are ordinary text to the server, so the guard is the only thing keeping them out of a note."""
    await _open_editor(context, page)
    await _fill_editor(page=page, fill="mine only\nshared line")
    await page.evaluate('() => { document.getElementById("yak-lease").dataset.lease = "0000000000000000"; }')
    await page.click("#save-btn")
    await expect(page.locator("#conflict")).to_be_visible()

    # Every save from here would write markers into the committed fixture vault.
    saves: list[str] = []

    async def record(route):
        saves.append(route.request.post_data or "")
        await route.fulfill(status=200, body="")

    await page.route("**/edit", record)

    await page.click("#conflict-merge")

    await expect(page.locator("#conflict")).to_be_hidden()
    merged = await page.evaluate("() => window.jar.toString()")
    assert "<<<<<<< on disk" in merged
    assert ">>>>>>> my draft" in merged
    assert "mine only" in merged

    await page.click("#save-btn")

    await expect(page.locator("#save-status")).to_have_text("Conflict markers left. Save again to keep them.")
    assert saves == []

    # The override is deliberate: a second press inside the window keeps the markers.
    await page.click("#save-btn")

    await expect(page.locator("#save-status")).not_to_have_text("Conflict markers left. Save again to keep them.")
    assert len(saves) == 1


@pytest.mark.allow_console_errors
@pytest.mark.playwright
@pytest.mark.asyncio
async def test_taking_theirs_loads_the_saved_note_and_clears_the_conflict(
    context: BrowserContext, page: Page, server_lifecycle
):
    """Taking theirs has to leave the editor synced, or the next save reopens the same conflict."""
    await _open_editor(context, page)
    await _fill_editor(page=page, fill="a draft that loses")
    await page.evaluate('() => { document.getElementById("yak-lease").dataset.lease = "0000000000000000"; }')
    await page.click("#save-btn")
    await expect(page.locator("#conflict")).to_be_visible()

    await page.click("#conflict-theirs")

    await expect(page.locator("#conflict")).to_be_hidden()
    await expect(page.locator("#save-status")).to_have_text("Synced")
    # The saved note is whatever the vault holds, so this asserts the draft is gone
    # rather than pinning the fixture's text.
    assert await page.evaluate("() => window.jar.toString()") != "a draft that loses"
    assert await page.evaluate("() => window.jar.toString() === window.serverContent")
