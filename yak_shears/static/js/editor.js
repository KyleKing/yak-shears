/**
 * Yak Editor - Djot content editor with live preview
 *
 * ARCHITECTURE:
 * This module manages three interconnected state systems:
 * 1. CodeJar Editor State: The actual text content and cursor position
 * 2. UI View State: Which view mode is active (editor/preview/split)
 * 3. Persistence State: localStorage sync for unsaved changes
 *
 * STATE TRANSITIONS:
 * - "Synced": Content matches server (no local changes or successful save)
 * - "Modified": Local edits exist that haven't been saved
 * - "Saving...": HTTP POST in progress
 * - "Saved": Recently saved (transitions to "Synced" after 2s)
 *
 * VIEW MODES:
 * - "editor": Show only the CodeJar editor (default on mobile)
 * - "side-by-side": Split view with editor + live preview (default on desktop)
 * - "preview": Show only rendered Djot preview
 *
 * CONSTANTS
 */
const MOBILE_BREAKPOINT = 768; // px - matches CSS media query
const SAVE_STATUS_RESET_DELAY = 2000; // ms - "Saved" → "Synced" transition
const EDITOR_INIT_MAX_RETRIES = 50; // Wait up to 5 seconds for DOM
const EDITOR_INIT_RETRY_INTERVAL = 100; // ms between retries

/**
 * GLOBAL STATE
 * Note: These are module-level variables due to CodeJar's callback requirements.
 * Consider refactoring to a class-based approach for better encapsulation.
 */

// List patterns for auto-continuation (order matters: more specific first)
const LIST_PATTERNS = {
	checklistUnchecked: /^(\s*)- \[ \] (.*)$/,
	checklistChecked: /^(\s*)- \[x\] (.*)$/,
	numbered: /^(\s*)(\d+)\. (.*)$/,
	bullet: /^(\s*)- (.*)$/,
};
let retries = 0;
let jar; // CodeJar instance - provides text editing with syntax highlighting
let currentView = "editor"; // Active view mode: "editor" | "side-by-side" | "preview"
let metadataPanelVisible = false; // Sidebar panel state (mobile: modal, desktop: optional pin)
let panelPinned = false; // Desktop-only: panel stays open alongside editor

/**
 * Toggle the metadata/properties panel visibility
 *
 * BEHAVIOR:
 * - Mobile (≤768px): Panel appears as full-screen modal with backdrop
 * - Desktop (>768px): Panel can be toggled or pinned alongside editor
 * - Pinned state only available on desktop; auto-unpins on resize to mobile
 *
 * @param {boolean|null} forceState - Explicit show (true) or hide (false), or toggle (null)
 */
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

/**
 * Toggle pinned state for metadata panel (desktop only)
 *
 * PINNED BEHAVIOR:
 * - Panel becomes permanent part of layout (doesn't overlay)
 * - Backdrop is hidden (no need to click outside to dismiss)
 * - State persists in localStorage across page loads
 * - Automatically unpinned on resize to mobile
 *
 * @returns {void}
 */
function togglePanelPin() {
	const layout = document.querySelector('.editor-layout');
	const panel = document.querySelector('.metadata-panel');
	const pinBtn = document.querySelector('.panel-pin');
	const backdrop = document.querySelector('.metadata-backdrop');

	// Only allow pinning on desktop (matches CSS layout capabilities)
	if (window.innerWidth <= MOBILE_BREAKPOINT) return;

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

/**
 * Render Djot content as HTML preview with syntax highlighting
 *
 * DEPENDENCIES:
 * - window.djot: Djot parser/renderer library (loaded via CDN in template)
 * - window.Prism: Code syntax highlighting (loaded from static files)
 *
 * @param {string} content - Raw Djot/Markdown text content
 */
function stripFrontmatter(content) {
	if (!content.startsWith("---\n")) return content;
	const end = content.indexOf("\n---\n", 4);
	if (end === -1) return content;
	return content.slice(end + 5);
}

const VIDEO_EXT_RE = /\.(mp4|webm|mov|m4v)$/i;

/**
 * Upgrade rendered media so previews stay cheap:
 * - /media video refs (Djot has no video syntax, so they arrive as <img>) become
 *   an HTML5 <video> with preload="none" and a poster frame (poster/full downloaded on play)
 * - images swap to their /thumb thumbnail, lazy-load, and link to the full-res file
 *
 * @param {HTMLElement} container - Rendered preview element
 */
function enhanceMedia(container) {
	container.querySelectorAll('img[src^="/media/"]').forEach((img) => {
		const full = img.getAttribute("src");
		const thumb = full.replace("/media/", "/thumb/").replace(/\.[^./]+$/, ".jpg");
		if (VIDEO_EXT_RE.test(full)) {
			const video = document.createElement("video");
			video.controls = true;
			video.preload = "none";
			video.poster = thumb;
			video.setAttribute("playsinline", "");
			const source = document.createElement("source");
			source.src = full;
			source.type = "video/mp4";
			video.appendChild(source);
			video.className = "preview-media preview-media--video";
			img.replaceWith(video);
		} else {
			img.src = thumb;
			img.loading = "lazy";
			img.decoding = "async";
			img.className = "preview-media preview-media--image";
			const link = document.createElement("a");
			link.href = full;
			link.target = "_blank";
			link.rel = "noopener";
			link.className = "preview-media__link";
			img.replaceWith(link);
			link.appendChild(img);
		}
	});
}

function renderPreview(content) {
	const previewContent = document.getElementById("preview-content");
	if (previewContent && window.djot) {
		try {
			// Parse Djot → AST → HTML, excluding YAML frontmatter
			const html = window.djot.renderHTML(window.djot.parse(stripFrontmatter(content)));
			previewContent.innerHTML = html;

			enhanceMedia(previewContent);

			// Apply Prism syntax highlighting to code blocks
			if (window.Prism) {
				const codes = previewContent.querySelectorAll(
					'code[class*="language-"]',
				);
				codes.forEach((code) => window.Prism.highlightElement(code));
			}
		} catch (error) {
			console.error("Error rendering preview:", error);
			// Fallback to plain text on parse error
			previewContent.textContent = content;
		}
	}
}

/**
 * Switch between editor view modes
 *
 * CSS CLASS MAPPING:
 * - "editor" → "editoronly" class: Shows only CodeJar editor
 * - "side-by-side" → "sidebyside" class: 50/50 split editor + preview
 * - "preview" → "previewonly" class: Shows only rendered preview
 *
 * SIDE EFFECTS:
 * - Updates button active states in view toggle
 * - Re-renders preview if switching to a mode that displays it
 * - Updates global currentView state
 *
 * @param {"editor"|"side-by-side"|"preview"} mode - Target view mode
 */
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

	// Update container classes - note: CSS class names differ from mode names
	// This mapping exists for historical reasons (shorter CSS class names)
	const modeClassMap = {
		"editor": "editoronly",
		"side-by-side": "sidebyside",
		"preview": "previewonly"
	};
	// Use classList so unrelated state (e.g. the .wrap toggle) is preserved
	container.classList.remove("editoronly", "sidebyside", "previewonly");
	container.classList.add(modeClassMap[mode]);

	currentView = mode;

	// Update preview if switching to a mode that shows it
	if (mode === "side-by-side" || mode === "preview") {
		renderPreview(jar ? jar.toString() : window.serverContent);
	}
}

/**
 * Initialize the CodeJar editor with all event handlers and state management
 *
 * INITIALIZATION FLOW:
 * 1. Wait for DOM element '.editor' to be available (retry up to 5s)
 * 2. Create CodeJar instance with syntax highlighting
 * 3. Load content from server (window.serverContent, injected in template)
 * 4. Check localStorage for unsaved local changes
 * 5. Set up save status tracking
 * 6. Attach event handlers for:
 *    - HTMX save button feedback
 *    - Content changes (localStorage sync + preview updates)
 *    - View mode toggle buttons
 *    - Metadata panel toggle/pin
 *    - Keyboard shortcuts (Cmd+Enter = save, Cmd+M = toggle panel, Esc = close panel)
 * 7. Restore panel state from localStorage (desktop only)
 * 8. Set initial view mode based on screen size
 *
 * RETRY MECHANISM:
 * If .editor element isn't in DOM, retries every 100ms up to 50 times (5 seconds total).
 * This handles race conditions with external script loading.
 *
 * CRITICAL DATA ATTRIBUTES:
 * - data-manual: Prevents CodeJar from auto-initializing (we control initialization)
 * - data-gramm="false": Disables Grammarly extension interference
 *
 * @returns {void}
 */
function initEditor() {
	const editor = document.querySelector(".editor");
	if (editor) {
		// Initialize CodeJar with custom syntax highlighter
		jar = CodeJar(editor, highlight, {
			addClosing: false, // Don't auto-close brackets (Djot doesn't need it)
			spellcheck: true, // Enable browser spell check
			tab: " ".repeat(4), // Convert tabs to 4 spaces
		});
		window.jar = jar; // Expose for testing and debugging

		// Cmd/Ctrl+Enter saves the document
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
			true, // Use capture phase to handle before CodeJar
		);

		// Load yak path from URL for localStorage key uniqueness
		const yak_path = new URLSearchParams(window.location.search).get("yak");
		if (yak_path === null) throw new Error("URL does not have file parameter.");
		const storageKey = `editor_${yak_path}`;
		const serverContent = window.serverContent; // Injected in template: <script>window.serverContent = {{ content | tojson }};</script>
		editor.textContent = serverContent;
		highlight(editor); // Apply initial syntax highlighting

		// Auto-focus editor and place cursor at end
		requestAnimationFrame(() => {
			editor.focus();
			const range = document.createRange();
			const sel = window.getSelection();
			if (editor.lastChild) {
				range.selectNodeContents(editor);
				range.collapse(false); // Collapse to end
				sel.removeAllRanges();
				sel.addRange(range);
			}
		});

		// Check for unsaved local changes from previous session
		const saved = localStorage.getItem(storageKey);
		if (saved && saved !== serverContent) {
			// TODO: Show UI for switching between server/local versions
			// Currently we silently prefer server content but notify in console
			console.log("Unsaved local changes detected for this file");
		}

		// Set initial status based on whether we have local changes
		updateSaveStatus(saved && saved !== serverContent ? "Modified" : "Synced");

		// Inject current editor content into the save request. Avoids hx-vals="js:...",
		// which requires 'unsafe-eval' and is blocked by the page's Content-Security-Policy.
		document.body.addEventListener("htmx:configRequest", function (evt) {
			if (evt.target.id === "save-btn") {
				evt.detail.parameters.content = getEditorContent();
			}
		});

		// HTMX event listeners for save feedback (button clicks trigger HTMX POST)
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
					// Auto-transition "Saved" → "Synced" after 2 seconds
					setTimeout(() => {
						updateSaveStatus("Synced");
					}, SAVE_STATUS_RESET_DELAY);
					// Clear local storage on successful save
					localStorage.removeItem(storageKey);
				} else {
					document.getElementById("save-status").textContent = "Error saving!";
				}
			}
		});

		// Track content changes for localStorage sync and preview updates
		jar.onUpdate((code) => {
			// Update save status based on whether content matches server
			if (code === serverContent) {
				localStorage.removeItem(storageKey); // No need to persist when synced
				updateSaveStatus("Synced");
			} else {
				localStorage.setItem(storageKey, code); // Persist unsaved changes
				updateSaveStatus("Modified");
			}
			// Update preview if it's visible in current view mode
			if (currentView === "side-by-side" || currentView === "preview") {
				renderPreview(code);
			}
			// TODO: Consider localStorage pruning strategy for old/unused entries
			// PLANNED: Separate page to review local vs server differences
		});

		// Initialize view toggle buttons
		document.querySelectorAll(".view-toggle .button").forEach((button) => {
			button.addEventListener("click", () => {
				const view = button.getAttribute("data-view");
				setViewMode(view);
				if (window.innerWidth > MOBILE_BREAKPOINT && metadataPanelVisible && !panelPinned) {
					toggleMetadataPanel(false);
				}
			});
		});

		// Initialize view mode based on screen size
		// Desktop defaults to side-by-side, mobile to editor-only
		const isMobile = window.innerWidth <= MOBILE_BREAKPOINT;
		const initialView = isMobile ? "editor" : "side-by-side";
		setViewMode(initialView);

		// Word wrap toggle (default off; persisted per browser)
		const wrapToggle = document.getElementById("wrap-toggle");
		const applyWrap = (on) => {
			const container = document.getElementById("editor-container");
			container.classList.toggle("wrap", on);
			// CodeJar sets white-space inline, which beats a CSS class, so set it directly.
			const editorEl = document.querySelector(".editor");
			if (editorEl) {
				editorEl.style.whiteSpace = on ? "pre-wrap" : "pre";
				editorEl.style.overflowWrap = on ? "break-word" : "normal";
			}
			if (wrapToggle) {
				wrapToggle.textContent = on ? "on" : "off";
				wrapToggle.setAttribute("aria-pressed", on.toString());
				wrapToggle.classList.toggle("active", on);
			}
			localStorage.setItem("editorWrap", on ? "true" : "false");
		};
		if (wrapToggle) {
			wrapToggle.addEventListener("click", () => {
				applyWrap(!document.getElementById("editor-container").classList.contains("wrap"));
			});
		}
		applyWrap(localStorage.getItem("editorWrap") === "true");

		// Media upload: toolbar button + paste. Uploaded files are transcoded
		// server-side; the returned Djot snippet is inserted at the cursor.
		const uploadBtn = document.getElementById("upload-btn");
		const mediaInput = document.getElementById("media-input");

		const insertAtCursor = (text) => {
			editor.focus();
			// execCommand fires an input event, so CodeJar re-highlights and onUpdate runs.
			const ok = document.execCommand("insertText", false, text);
			if (!ok) {
				jar.updateCode(`${jar.toString()}\n${text}`);
			}
		};

		const uploadOne = async (file) => {
			const form = new FormData();
			form.append("file", file);
			form.append("yak", yak_path);
			updateSaveStatus(`Uploading ${file.name}...`);
			try {
				const res = await fetch("/media/upload", { method: "POST", body: form });
				const data = await res.json();
				if (!res.ok) throw new Error(data.error || "Upload failed");
				insertAtCursor(`\n${data.snippet}\n`);
				updateSaveStatus("Modified");
			} catch (err) {
				console.error("Media upload failed:", err);
				updateSaveStatus(`Upload failed: ${err.message}`);
			}
		};

		const uploadFiles = async (files) => {
			for (const file of files) {
				if (file.type.startsWith("image/") || file.type.startsWith("video/")) {
					await uploadOne(file);
				}
			}
		};

		if (uploadBtn && mediaInput) {
			uploadBtn.addEventListener("click", () => mediaInput.click());
			mediaInput.addEventListener("change", () => {
				if (mediaInput.files.length) uploadFiles(mediaInput.files);
				mediaInput.value = "";
			});
		}

		editor.addEventListener("paste", (e) => {
			const items = Array.from(e.clipboardData?.items || []);
			const files = items
				.filter((it) => it.kind === "file" && (it.type.startsWith("image/") || it.type.startsWith("video/")))
				.map((it) => it.getAsFile())
				.filter(Boolean);
			if (files.length) {
				e.preventDefault();
				uploadFiles(files);
			}
		});

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

		// Restore panel state from localStorage. Only a pinned panel is restored:
		// an unpinned panel is a transient overlay, so re-opening it on every load
		// would keep covering the split preview when returning to the editor.
		const savedPinned = localStorage.getItem('panelPinned');
		if (window.innerWidth > MOBILE_BREAKPOINT && savedPinned === 'true') {
			togglePanelPin();
		}

		// Handle window resize - adjust view mode and panel state
		let lastWidth = window.innerWidth;
		window.addEventListener("resize", () => {
			const wasMobile = lastWidth <= MOBILE_BREAKPOINT;
			const nowMobile = window.innerWidth <= MOBILE_BREAKPOINT;
			lastWidth = window.innerWidth;

			// Switch from side-by-side to editor-only when entering mobile mode
			if (wasMobile !== nowMobile && currentView === "side-by-side") {
				setViewMode(nowMobile ? "editor" : "side-by-side");
			}

			// Unpin panel when switching to mobile (pinning not supported on mobile)
			if (!wasMobile && nowMobile && panelPinned) {
				const layout = document.querySelector('.editor-layout');
				layout.classList.remove('panel-pinned');
				panelPinned = false;
				const pinBtn = document.querySelector('.panel-pin');
				if (pinBtn) pinBtn.setAttribute('aria-pressed', 'false');
			}
		});
	} else if (retries < EDITOR_INIT_MAX_RETRIES) {
		// Editor element not ready yet - retry
		retries++;
		setTimeout(initEditor, EDITOR_INIT_RETRY_INTERVAL);
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

function _leadingSpaces(line) {
	return (line.match(/^ */) || [""])[0].length;
}

// Return the line immediately above `lineStart` (without its newline), or null.
function _getPreviousLine(text, lineStart) {
	if (lineStart <= 0) return null;
	const prevEnd = lineStart - 1; // index of the '\n' terminating the previous line
	const prevStart = text.lastIndexOf("\n", prevEnd - 1) + 1;
	return { start: prevStart, text: text.substring(prevStart, prevEnd) };
}

// Indent of the nearest non-blank line above `lineStart` (the effective parent),
// or null when there is none. Used to bound how deep an item may indent.
function _previousNonBlankIndent(text, lineStart) {
	let start = lineStart;
	while (start > 0) {
		const prev = _getPreviousLine(text, start);
		if (!prev) return null;
		if (prev.text.trim() !== "") return _leadingSpaces(prev.text);
		start = prev.start;
	}
	return null;
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

	const apply = (newText, newCursorPos) => {
		jarInstance.updateCode(newText);
		requestAnimationFrame(() => _setCursorPosition(editorEl, Math.max(0, newCursorPos)));
		return true;
	};

	if (outdent) {
		// Remove up to indentSize spaces from start
		const spacesToRemove = Math.min(indentSize, _leadingSpaces(lineText));
		if (spacesToRemove === 0) return false;
		const newLineText = lineText.substring(spacesToRemove);
		const newIndent = _leadingSpaces(newLineText);

		// Drop the blank separator that a matching indent inserted, once this item
		// is no longer nested deeper than the line above the blank (Djot nesting).
		const prev = _getPreviousLine(text, lineStart);
		if (prev && prev.text.trim() === "") {
			const grand = _getPreviousLine(text, prev.start);
			if (grand && grand.text.trim() !== "" && _leadingSpaces(grand.text) <= newIndent) {
				const newText = text.substring(0, prev.start) + newLineText + text.substring(lineEnd);
				return apply(newText, cursorPos - spacesToRemove - 1);
			}
		}

		const newText = text.substring(0, lineStart) + newLineText + text.substring(lineEnd);
		return apply(newText, cursorPos - spacesToRemove);
	}

	// Indent
	const newLineText = indentStr + lineText;
	const newIndent = _leadingSpaces(newLineText);

	// Keep nesting valid: an item may be at most one level deeper than the nearest
	// non-blank line above it. Consume the Tab without over-indenting past that.
	const parentIndent = _previousNonBlankIndent(text, lineStart);
	if (parentIndent !== null && newIndent > parentIndent + indentSize) {
		return true;
	}

	// Djot only renders a nested list when a blank line precedes it, so insert one
	// when this item becomes indented under a non-blank parent line.
	const prev = _getPreviousLine(text, lineStart);
	if (prev && prev.text.trim() !== "" && _leadingSpaces(prev.text) < newIndent) {
		const newText = text.substring(0, lineStart) + "\n" + newLineText + text.substring(lineEnd);
		return apply(newText, cursorPos + indentSize + 1);
	}

	const newText = text.substring(0, lineStart) + newLineText + text.substring(lineEnd);
	return apply(newText, cursorPos + indentSize);
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

/**
 * Update the save status indicator text
 *
 * STATUS VALUES:
 * - "Synced": Content matches server (green background in CSS)
 * - "Modified": Unsaved local changes exist
 * - "Saving...": HTTP request in progress
 * - "Saved": Recently saved successfully (transitions to "Synced" after 2s)
 * - "Error saving!": HTTP request failed
 *
 * @param {string} status - New status text to display
 */
function updateSaveStatus(status) {
	document.getElementById("save-status").textContent = status;
}

/**
 * Get current editor content for HTMX form submission
 *
 * Injected into the save request via the htmx:configRequest listener above.
 *
 * @returns {string} Current editor text content
 */
function getEditorContent() {
	if (jar) {
		return jar.toString();
	}
	return "";
}

// Expose functions globally for template/HTMX usage
window.toggleMetadataPanel = toggleMetadataPanel;
window.togglePanelPin = togglePanelPin;

// Initialize editor on page load
initEditor();
