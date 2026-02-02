/**
 * Editor save status states:
 * - "Synced": No difference from server, checked by polling
 * - "Modified": Local changes ready for submission
 * - "Saved": In sync because local changes were pushed
 * - "Saving...": In the process of sending changes to the server
 */

// List patterns for auto-continuation (order matters: more specific first)
const LIST_PATTERNS = {
	checklistUnchecked: /^(\s*)- \[ \] (.*)$/,
	checklistChecked: /^(\s*)- \[x\] (.*)$/,
	numbered: /^(\s*)(\d+)\. (.*)$/,
	bullet: /^(\s*)- (.*)$/,
};

const maxRetries = 50; // 5 seconds at 100ms intervals
let retries = 0;
let jar; // Global reference to CodeJar instance
let currentView = "editor"; // Current view mode
let metadataPanelVisible = false; // Track metadata panel visibility
let panelPinned = false; // Track if panel is pinned (desktop only)

function toggleMetadataPanel(forceState = null) {
	const panel = document.querySelector('.metadata-panel');
	const menuBtn = document.getElementById('menu-btn');
	const backdrop = document.querySelector('.metadata-backdrop');
	const layout = document.querySelector('.editor-layout');
	const pinBtn = document.querySelector('.panel-pin');
	const editor = document.querySelector('.editor');

	metadataPanelVisible = forceState !== null ? forceState : !metadataPanelVisible;

	// Clear pinned state when toggling via menu button
	if (panelPinned && !metadataPanelVisible) {
		panelPinned = false;
		layout.classList.remove('panel-pinned');
		if (pinBtn) pinBtn.setAttribute('aria-pressed', 'false');
		localStorage.setItem('panelPinned', 'false');
	}

	panel.classList.toggle('visible', metadataPanelVisible);
	if (menuBtn) {
		menuBtn.classList.toggle('active', metadataPanelVisible);
		menuBtn.setAttribute('aria-expanded', metadataPanelVisible.toString());
	}

	// Show backdrop when panel is open and not pinned
	if (backdrop && !panelPinned) {
		backdrop.classList.toggle('visible', metadataPanelVisible);
	}

	// Focus management
	if (metadataPanelVisible) {
		// Focus first interactive element in panel
		const firstFocusable = panel.querySelector('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
		if (firstFocusable) {
			requestAnimationFrame(() => firstFocusable.focus());
		}
	} else {
		// Return focus to editor
		if (editor) {
			requestAnimationFrame(() => editor.focus());
		}
	}

	localStorage.setItem('metadataPanelVisible', metadataPanelVisible);
}

function togglePanelPin() {
	const layout = document.querySelector('.editor-layout');
	const panel = document.querySelector('.metadata-panel');
	const pinBtn = document.querySelector('.panel-pin');
	const backdrop = document.querySelector('.metadata-backdrop');

	// Only allow pinning on desktop
	if (window.innerWidth <= 768) return;

	panelPinned = !panelPinned;

	layout.classList.toggle('panel-pinned', panelPinned);
	pinBtn.setAttribute('aria-pressed', panelPinned.toString());

	// When pinned, panel should be visible and backdrop hidden
	if (panelPinned) {
		panel.classList.add('visible');
		metadataPanelVisible = true;
		if (backdrop) backdrop.classList.remove('visible');
	}

	localStorage.setItem('panelPinned', panelPinned);
}

window.toggleMetadataPanel = toggleMetadataPanel;
window.togglePanelPin = togglePanelPin;

function renderPreview(content) {
	const previewContent = document.getElementById("preview-content");
	if (previewContent && window.djot) {
		try {
			const html = window.djot.renderHTML(window.djot.parse(content));
			previewContent.innerHTML = html;
			if (window.Prism) {
				const codes = previewContent.querySelectorAll(
					'code[class*="language-"]',
				);
				codes.forEach((code) => window.Prism.highlightElement(code));
			}
		} catch (error) {
			console.error("Error rendering preview:", error);
			previewContent.textContent = content;
		}
	}
}

function setViewMode(mode) {
	const container = document.getElementById("editor-container");
	const buttons = document.querySelectorAll(".view-toggle .button");

	// Remove active class from all buttons
	buttons.forEach((btn) => btn.classList.remove("active"));

	// Add active class to selected button
	const activeButton = document.querySelector(`[data-view="${mode}"]`);
	if (activeButton) {
		activeButton.classList.add("active");
	}

	// Update container classes
	// Map view modes to CSS class names
	const modeClassMap = {
		"editor": "editoronly",
		"side-by-side": "sidebyside",
		"preview": "previewonly"
	};
	container.className = "editor-container " + modeClassMap[mode];

	currentView = mode;

	// Update preview if switching to a mode that shows it
	if (mode === "side-by-side" || mode === "preview") {
		renderPreview(jar ? jar.toString() : window.serverContent);
	}
}

function initEditor() {
	const editor = document.querySelector(".editor");
	if (editor) {
		jar = CodeJar(editor, highlight, {
			addClosing: false,
			spellcheck: true,
			tab: " ".repeat(4),
		});
		window.jar = jar; // Expose for testing

		editor.addEventListener(
			"keydown",
			function (e) {
				// Cmd/Meta + Enter to save
				if (e.metaKey && e.key === "Enter") {
					e.preventDefault();
					document.getElementById("save-btn").click();
					return;
				}

				// Plain Enter for list continuation
				if (e.key === "Enter" && !e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey) {
					if (_handleListContinuation(editor, jar)) {
						e.preventDefault();
						return;
					}
				}

				// Tab/Shift+Tab for list indentation
				if (e.key === "Tab") {
					if (_handleListIndentation(editor, jar, e.shiftKey)) {
						e.preventDefault();
						return;
					}
				}

				// Ctrl+L to toggle checklist state
				if (e.ctrlKey && e.key === "l") {
					e.preventDefault();
					_toggleChecklistState(editor, jar);
					return;
				}
			},
			true,
		);

		// Use the full unique yak path from the URL for local storage
		const yak_path = new URLSearchParams(window.location.search).get("yak");
		if (yak_path === null) throw new Error("URL does not have file parameter.");
		const storageKey = `editor_${yak_path}`;
		const serverContent = window.serverContent;
		editor.textContent = serverContent;
		highlight(editor); // Highlight on load rather than waiting for key press

		// Auto-focus the editor on page load
		requestAnimationFrame(() => {
			editor.focus();
			const range = document.createRange();
			const sel = window.getSelection();
			if (editor.lastChild) {
				range.selectNodeContents(editor);
				range.collapse(false);
				sel.removeAllRanges();
				sel.addRange(range);
			}
		});

		const saved = localStorage.getItem(storageKey);
		if (saved && saved !== serverContent) {
			// TODO: Show UI for switching between server/local versions
			console.log("Unsaved local changes detected for this file");
		}

		// Set initial status
		updateSaveStatus(saved && saved !== serverContent ? "Modified" : "Synced");

		// HTMX event listeners for feedback
		document.body.addEventListener("htmx:beforeRequest", function (evt) {
			if (evt.target.id === "save-btn") {
				document.getElementById("save-btn").disabled = true;
				document.getElementById("save-status").textContent = "Saving...";
			}
		});

		document.body.addEventListener("htmx:afterRequest", function (evt) {
			if (evt.target.id === "save-btn") {
				document.getElementById("save-btn").disabled = false;
				if (evt.detail.successful) {
					updateSaveStatus("Saved");
					setTimeout(() => {
						updateSaveStatus("Synced");
					}, 2000);
					// Clear local storage on successful save
					localStorage.removeItem(storageKey);
				} else {
					document.getElementById("save-status").textContent = "Error saving!";
				}
			}
		});

		jar.onUpdate((code) => {
			if (code === serverContent) {
				localStorage.removeItem(storageKey);
				updateSaveStatus("Synced");
			} else {
				localStorage.setItem(storageKey, code);
				updateSaveStatus("Modified");
			}
			// Update preview if it's visible
			if (currentView === "side-by-side" || currentView === "preview") {
				renderPreview(code);
			}
			// PLANNED: Consider how to otherwise prune old unused local storage? Might need a separate local review page which compares against server?
		});

		// Initialize view toggle buttons
		document.querySelectorAll(".view-toggle .button").forEach((button) => {
			button.addEventListener("click", () => {
				const view = button.getAttribute("data-view");
				setViewMode(view);
			});
		});

		// Set initial view mode (default to editor-only)
		const isMobile = window.innerWidth <= 768;
		const initialView = "editor";
		setViewMode(initialView);

		// Initialize menu button toggle
		const menuBtn = document.getElementById('menu-btn');
		const pinBtn = document.querySelector('.panel-pin');
		const backdrop = document.querySelector('.metadata-backdrop');

		if (menuBtn) {
			menuBtn.addEventListener('click', () => toggleMetadataPanel());
		}

		// Pin button click
		if (pinBtn) {
			pinBtn.addEventListener('click', () => togglePanelPin());
		}

		// Backdrop click closes panel (when not pinned)
		if (backdrop) {
			backdrop.addEventListener('click', () => {
				if (!panelPinned) {
					toggleMetadataPanel(false);
				}
			});
		}

		// Keyboard shortcuts for menu panel
		document.addEventListener('keydown', (e) => {
			// Cmd/Ctrl+M to toggle menu
			if ((e.metaKey || e.ctrlKey) && e.key === 'm') {
				e.preventDefault();
				toggleMetadataPanel();
			}
			// Escape to close menu (when open and not pinned)
			if (e.key === 'Escape' && metadataPanelVisible && !panelPinned) {
				e.preventDefault();
				toggleMetadataPanel(false);
			}
		});

		// Restore panel state from localStorage
		const savedPinned = localStorage.getItem('panelPinned');
		const savedVisible = localStorage.getItem('metadataPanelVisible');

		// On desktop, restore pin state
		if (window.innerWidth > 768 && savedPinned === 'true') {
			togglePanelPin();
		} else if (savedVisible === 'true') {
			toggleMetadataPanel(true);
		}

		// Handle window resize
		let lastWidth = window.innerWidth;
		window.addEventListener("resize", () => {
			const wasMobile = lastWidth <= 768;
			const nowMobile = window.innerWidth <= 768;
			lastWidth = window.innerWidth;

			// Switch view mode if needed
			if (wasMobile !== nowMobile && currentView === "side-by-side") {
				setViewMode(nowMobile ? "editor" : "side-by-side");
			}

			// Unpin panel when switching to mobile
			if (!wasMobile && nowMobile && panelPinned) {
				const layout = document.querySelector('.editor-layout');
				layout.classList.remove('panel-pinned');
				panelPinned = false;
				const pinBtn = document.querySelector('.panel-pin');
				if (pinBtn) pinBtn.setAttribute('aria-pressed', 'false');
			}
		});
	} else if (retries < maxRetries) {
		retries++;
		setTimeout(initEditor, 100);
	}
}

function _getCursorPosition(editorEl) {
	const sel = window.getSelection();
	if (!sel.rangeCount) return 0;
	const range = sel.getRangeAt(0);
	return getTextOffset(editorEl, range.startContainer, range.startOffset);
}

function _setCursorPosition(editorEl, offset) {
	const { node, offset: nodeOffset } = getNodeAtOffset(editorEl, offset);
	if (node) {
		const range = document.createRange();
		range.setStart(node, nodeOffset);
		range.collapse(true);
		const sel = window.getSelection();
		sel.removeAllRanges();
		sel.addRange(range);
	}
}

function _getCurrentLine(text, cursorPos) {
	const lineStart = text.lastIndexOf("\n", cursorPos - 1) + 1;
	let lineEnd = text.indexOf("\n", cursorPos);
	if (lineEnd === -1) lineEnd = text.length;
	const lineText = text.substring(lineStart, lineEnd);
	return { lineStart, lineEnd, lineText };
}

function _handleListContinuation(editorEl, jarInstance) {
	const text = jarInstance.toString();
	const cursorPos = _getCursorPosition(editorEl);
	const { lineStart, lineEnd, lineText } = _getCurrentLine(text, cursorPos);

	// Check each pattern in order of specificity
	for (const [patternName, pattern] of Object.entries(LIST_PATTERNS)) {
		const match = lineText.match(pattern);
		if (match) {
			const indent = match[1];
			const content = match[patternName === "numbered" ? 3 : 2];

			// If content is empty, remove the list marker and exit list mode
			if (content === "") {
				const newText = text.substring(0, lineStart) + text.substring(lineEnd);
				jarInstance.updateCode(newText);
				requestAnimationFrame(() => _setCursorPosition(editorEl, lineStart));
				return true;
			}

			// Generate continuation marker
			let continuation;
			switch (patternName) {
				case "checklistUnchecked":
				case "checklistChecked":
					continuation = `${indent}- [ ] `;
					break;
				case "numbered":
					const nextNum = parseInt(match[2], 10) + 1;
					continuation = `${indent}${nextNum}. `;
					break;
				case "bullet":
					continuation = `${indent}- `;
					break;
			}

			// Insert newline and continuation at cursor position
			const newText =
				text.substring(0, cursorPos) + "\n" + continuation + text.substring(cursorPos);
			const newCursorPos = cursorPos + 1 + continuation.length;
			jarInstance.updateCode(newText);
			requestAnimationFrame(() => _setCursorPosition(editorEl, newCursorPos));
			return true;
		}
	}
	return false;
}

function _handleListIndentation(editorEl, jarInstance, outdent) {
	const text = jarInstance.toString();
	const cursorPos = _getCursorPosition(editorEl);
	const { lineStart, lineEnd, lineText } = _getCurrentLine(text, cursorPos);
	const indentSize = 4;
	const indentStr = " ".repeat(indentSize);

	// Check if current line is a list item
	const isListItem = Object.values(LIST_PATTERNS).some((p) => p.test(lineText));
	if (!isListItem) return false;

	let newLineText;
	let cursorDelta;

	if (outdent) {
		// Remove up to indentSize spaces from start
		const leadingSpaces = lineText.match(/^(\s*)/)[1];
		const spacesToRemove = Math.min(indentSize, leadingSpaces.length);
		if (spacesToRemove === 0) return false;
		newLineText = lineText.substring(spacesToRemove);
		cursorDelta = -spacesToRemove;
	} else {
		// Add indent at start
		newLineText = indentStr + lineText;
		cursorDelta = indentSize;
	}

	const newText = text.substring(0, lineStart) + newLineText + text.substring(lineEnd);
	const newCursorPos = Math.max(lineStart, cursorPos + cursorDelta);
	jarInstance.updateCode(newText);
	requestAnimationFrame(() => _setCursorPosition(editorEl, newCursorPos));
	return true;
}

function _toggleChecklistState(editorEl, jarInstance) {
	const text = jarInstance.toString();
	const cursorPos = _getCursorPosition(editorEl);
	const { lineStart, lineEnd, lineText } = _getCurrentLine(text, cursorPos);

	let newLineText;
	let cursorDelta = 0;

	// Cycle: checked -> bullet -> unchecked -> checked
	if (LIST_PATTERNS.checklistChecked.test(lineText)) {
		// Checked -> bullet (remove [x])
		newLineText = lineText.replace(/^(\s*)- \[x\] /, "$1- ");
		cursorDelta = -5;
	} else if (LIST_PATTERNS.checklistUnchecked.test(lineText)) {
		// Unchecked -> checked
		newLineText = lineText.replace(/^(\s*)- \[ \] /, "$1- [x] ");
		cursorDelta = 0;
	} else if (LIST_PATTERNS.bullet.test(lineText)) {
		// Bullet -> unchecked (add [ ])
		newLineText = lineText.replace(/^(\s*)- /, "$1- [ ] ");
		cursorDelta = 5;
	} else {
		// Plain text -> unchecked checklist
		const indent = lineText.match(/^(\s*)/)[1];
		const content = lineText.substring(indent.length);
		newLineText = `${indent}- [ ] ${content}`;
		cursorDelta = 6 + indent.length - indent.length;
		cursorDelta = 6;
	}

	const newText = text.substring(0, lineStart) + newLineText + text.substring(lineEnd);
	const newCursorPos = Math.max(lineStart, cursorPos + cursorDelta);
	jarInstance.updateCode(newText);
	requestAnimationFrame(() => _setCursorPosition(editorEl, newCursorPos));
}

// Function to update save status
function updateSaveStatus(status) {
	document.getElementById("save-status").textContent = status;
}

// Function to get current editor content for HTMX
function getEditorContent() {
	if (jar) {
		return jar.toString();
	}
	return "";
}

// Expose function globally for HTMX
window.getEditorContent = getEditorContent;

initEditor();
