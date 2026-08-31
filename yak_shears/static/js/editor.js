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
const HTTP_CONFLICT = 409; // The yak changed since this page loaded

// Assigned by initEditor, which is where the editor and its jar are in scope.
let showConflict = () => {};

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
	const panel = document.querySelector(".metadata-panel");
	const menuBtn = document.getElementById("menu-btn");
	const backdrop = document.querySelector(".metadata-backdrop");
	const layout = document.querySelector(".editor-layout");
	const pinBtn = document.querySelector(".panel-pin");
	const editor = document.querySelector(".editor");

	metadataPanelVisible =
		forceState !== null ? forceState : !metadataPanelVisible;

	// Clear pinned state when toggling via menu button
	if (panelPinned && !metadataPanelVisible) {
		panelPinned = false;
		layout.classList.remove("panel-pinned");
		if (pinBtn) pinBtn.setAttribute("aria-pressed", "false");
		localStorage.setItem("panelPinned", "false");
	}

	panel.classList.toggle("visible", metadataPanelVisible);
	if (menuBtn) {
		menuBtn.classList.toggle("active", metadataPanelVisible);
		menuBtn.setAttribute("aria-expanded", metadataPanelVisible.toString());
	}

	// Show backdrop when panel is open and not pinned
	if (backdrop && !panelPinned) {
		backdrop.classList.toggle("visible", metadataPanelVisible);
	}

	// Focus management
	if (metadataPanelVisible) {
		// Focus first interactive element in panel
		const firstFocusable = panel.querySelector(
			'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
		);
		if (firstFocusable) {
			requestAnimationFrame(() => firstFocusable.focus());
		}
	} else {
		// Return focus to editor
		if (editor) {
			requestAnimationFrame(() => editor.focus());
		}
	}

	localStorage.setItem("metadataPanelVisible", metadataPanelVisible);
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
	const layout = document.querySelector(".editor-layout");
	const panel = document.querySelector(".metadata-panel");
	const pinBtn = document.querySelector(".panel-pin");
	const backdrop = document.querySelector(".metadata-backdrop");

	// Only allow pinning on desktop (matches CSS layout capabilities)
	if (window.innerWidth <= MOBILE_BREAKPOINT) return;

	panelPinned = !panelPinned;

	layout.classList.toggle("panel-pinned", panelPinned);
	pinBtn.setAttribute("aria-pressed", panelPinned.toString());

	// When pinned, panel should be visible and backdrop hidden
	if (panelPinned) {
		panel.classList.add("visible");
		metadataPanelVisible = true;
		if (backdrop) backdrop.classList.remove("visible");
	}

	localStorage.setItem("panelPinned", panelPinned);
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
 * - /media video refs (Djot has no video syntax, so they arrive as `img`) become
 *   an HTML5 <video> with preload="none" and a poster frame (poster/full downloaded on play)
 * - images swap to their /thumb thumbnail, lazy-load, and link to the full-res file
 *
 * @param {HTMLElement} container - Rendered preview element
 */
function enhanceMedia(container) {
	container.querySelectorAll('img[src^="/media/"]').forEach((img) => {
		const full = img.getAttribute("src");
		const thumb = full
			.replace("/media/", "/thumb/")
			.replace(/\.[^./]+$/, ".jpg");
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
			const html = window.djot.renderHTML(
				window.djot.parse(stripFrontmatter(content)),
			);
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
		editor: "editoronly",
		"side-by-side": "sidebyside",
		preview: "previewonly",
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

		// Upload failures have no status element of their own, so they hold the shared
		// save status until the next successful upload or save.
		let uploadError = false;

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
				if (
					e.key === "Enter" &&
					!e.metaKey &&
					!e.ctrlKey &&
					!e.shiftKey &&
					!e.altKey
				) {
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
		const caretKey = `editor_caret_${yak_path}`;
		let serverContent = window.serverContent; // Injected in template: <script>window.serverContent = {{ content | tojson }};</script>
		editor.textContent = serverContent;
		highlight(editor); // Apply initial syntax highlighting

		// Reopen where the last session left the caret. A note opened for the first
		// time starts at the top, because the end is only ever right for appending.
		requestAnimationFrame(() => {
			editor.focus();
			const stored = Number.parseInt(localStorage.getItem(caretKey), 10);
			const offset = Number.isNaN(stored)
				? 0
				: Math.min(Math.max(stored, 0), jar.toString().length);
			_setCursorPosition(editor, offset);
			_scrollCaretIntoView();
		});

		// The caret is worth remembering only while it is in the editor; anywhere
		// else on the page it says nothing about where this note was being read.
		document.addEventListener("selectionchange", () => {
			if (document.activeElement !== editor) return;
			const offset = _getCursorPosition(editor);
			if (offset !== null) localStorage.setItem(caretKey, String(offset));
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
				evt.detail.parameters.lease =
					document.getElementById("yak-lease").dataset.lease;
			}
		});

		// HTMX event listeners for save feedback (button clicks trigger HTMX POST)
		document.body.addEventListener("htmx:beforeRequest", function (evt) {
			if (evt.target.id === "save-btn") {
				if (_markersBlockSave()) {
					evt.preventDefault();
					return;
				}
				document.getElementById("save-btn").disabled = true;
				document.getElementById("save-status").textContent = "Saving...";
			}
		});

		document.body.addEventListener("htmx:afterRequest", function (evt) {
			if (evt.target.id === "save-btn") {
				document.getElementById("save-btn").disabled = false;
				if (evt.detail.successful) {
					uploadError = false;
					serverContent = getEditorContent();
					document.getElementById("yak-lease").dataset.lease =
						evt.detail.xhr.getResponseHeader("X-Yak-Lease") || "";
					updateSaveStatus("Saved");
					// Auto-transition "Saved" → "Synced" after 2 seconds
					setTimeout(() => {
						updateSaveStatus("Synced");
					}, SAVE_STATUS_RESET_DELAY);
					// Clear local storage on successful save
					localStorage.removeItem(storageKey);
				} else if (evt.detail.xhr.status === HTTP_CONFLICT) {
					// The file moved under us. The draft stays in localStorage and the
					// lease stays stale until the reader picks a side, so no second press
					// can force the write through.
					updateSaveStatus("Changed elsewhere");
					showConflict(
						evt.detail.xhr.responseText,
						evt.detail.xhr.getResponseHeader("X-Yak-Lease") || "",
						evt.detail.xhr.getResponseHeader("X-Yak-Conflict") ||
							"This note changed elsewhere",
					);
				} else {
					document.getElementById("save-status").textContent = "Error saving!";
				}
			}
		});

		// The conflict panel. Opening it is the only thing a refused save does; every
		// resolution is the reader's, because picking a side for them is how a note
		// loses text quietly.
		const conflict = document.getElementById("conflict");
		const conflictDiff = document.getElementById("conflict-diff");

		const closeConflict = () => {
			conflict.hidden = true;
			document.getElementById("save-btn").focus();
		};

		showConflict = (current, freshLease, message) => {
			document.getElementById("conflict-note").textContent = message;
			const rows = _lineDiff(current, getEditorContent());
			_paintDiff(conflictDiff, rows);
			conflict.hidden = false;
			conflictDiff.focus();

			// Resolving by hand needs the fresh lease for the same reason keeping mine
			// does: the save that follows is an overwrite the reader composed. What stops
			// it landing half-done is the marker guard on the way out, not the lease.
			document.getElementById("conflict-merge").onclick = () => {
				const merged = _conflictMarkup(rows);
				_applyEdit(editor, jar, merged, merged.length);
				document.getElementById("yak-lease").dataset.lease = freshLease;
				closeConflict();
				updateSaveStatus("Resolve the marked lines, then save");
			};

			// Taking the fresh lease is what makes this an overwrite the reader asked
			// for rather than the blind one the lease exists to stop.
			document.getElementById("conflict-mine").onclick = () => {
				document.getElementById("yak-lease").dataset.lease = freshLease;
				closeConflict();
				document.getElementById("save-btn").click();
			};

			document.getElementById("conflict-theirs").onclick = () => {
				_applyEdit(editor, jar, current, current.length);
				serverContent = current;
				document.getElementById("yak-lease").dataset.lease = freshLease;
				localStorage.removeItem(storageKey);
				closeConflict();
				updateSaveStatus("Synced");
			};

			document.getElementById("conflict-cancel").onclick = closeConflict;
		};

		conflict.addEventListener("keydown", (event) => {
			if (event.key === "Escape") closeConflict();
		});

		// localStorage already survives a reload, but it cannot survive the phone
		// evicting the tab, and a draft recovered later is worse than one never lost.
		window.addEventListener("beforeunload", (evt) => {
			if (getEditorContent() !== serverContent) evt.preventDefault();
		});

		// Track content changes for localStorage sync and preview updates
		jar.onUpdate((code) => {
			// Update save status based on whether content matches server
			if (code === serverContent) {
				localStorage.removeItem(storageKey); // No need to persist when synced
				if (!uploadError) updateSaveStatus("Synced");
			} else {
				localStorage.setItem(storageKey, code); // Persist unsaved changes
				if (!uploadError) updateSaveStatus("Modified");
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
				if (
					window.innerWidth > MOBILE_BREAKPOINT &&
					metadataPanelVisible &&
					!panelPinned
				) {
					toggleMetadataPanel(false);
				}
			});
		});

		// Initialize view mode based on screen size
		// Desktop defaults to side-by-side, mobile to editor-only
		const isMobile = window.innerWidth <= MOBILE_BREAKPOINT;
		const initialView = isMobile ? "editor" : "side-by-side";
		setViewMode(initialView);

		// Word wrap toggle. Defaults on; an explicit off is remembered in
		// localStorage and applies across pages until switched back on.
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
				applyWrap(
					!document
						.getElementById("editor-container")
						.classList.contains("wrap"),
				);
			});
		}
		applyWrap(localStorage.getItem("editorWrap") !== "false");

		// Media upload: toolbar button + paste. Uploaded files are transcoded
		// server-side; the returned Djot snippet is inserted at the cursor.
		const uploadBtn = document.getElementById("upload-btn");
		const mediaInput = document.getElementById("media-input");

		const insertAtCursor = (text) => {
			editor.focus();
			// execCommand fires an input event, so CodeJar re-highlights and onUpdate runs.
			if (document.execCommand("insertText", false, text)) return;
			// Splice it in by hand rather than appending, which would move the snippet
			// to the end of a note the reader never asked to reorder.
			const selection = _getSelectionRange(editor);
			const code = jar.toString();
			const { start, end } = selection || {
				start: code.length,
				end: code.length,
			};
			_applyEdit(
				editor,
				jar,
				code.substring(0, start) + text + code.substring(end),
				start + text.length,
			);
		};

		const uploadOne = async (file) => {
			const form = new FormData();
			form.append("file", file);
			form.append("yak", yak_path);
			updateSaveStatus(`Uploading ${file.name}...`);
			try {
				const res = await fetch("/media/upload", {
					method: "POST",
					body: form,
				});
				const data = await res.json();
				if (!res.ok) throw new Error(data.error || "Upload failed");
				uploadError = false;
				insertAtCursor(`\n${data.snippet}\n`);
				updateSaveStatus("Modified");
			} catch (err) {
				console.error("Media upload failed:", err);
				uploadError = true;
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
			const files = _mediaFilesFrom(e.clipboardData);
			if (files.length) {
				e.preventDefault();
				uploadFiles(files);
			}
			requestAnimationFrame(() => _stripInjectedElements(editor, jar));
		});

		const setDragover = (active) =>
			editor.classList.toggle("editor--dragover", active);

		editor.addEventListener("dragenter", (e) => {
			e.preventDefault();
			setDragover(true);
		});

		// preventDefault marks the editor a valid drop target; without it "drop" never fires
		editor.addEventListener("dragover", (e) => {
			e.preventDefault();
			setDragover(true);
		});

		editor.addEventListener("dragleave", (e) => {
			if (!editor.contains(e.relatedTarget)) setDragover(false);
		});

		// Always preventDefault: the browser default inserts a data-URL `img` node into the
		// contenteditable, which leaves an unscrollable editor and never uploads the file.
		editor.addEventListener("drop", (e) => {
			e.preventDefault();
			setDragover(false);
			const files = _mediaFilesFrom(e.dataTransfer);
			if (files.length) {
				uploadFiles(files);
			} else {
				const text = e.dataTransfer?.getData("text/plain");
				if (text) insertAtCursor(text);
			}
			requestAnimationFrame(() => _stripInjectedElements(editor, jar));
		});

		_setupCommandPanel(editor, jar);

		// Initialize menu button toggle
		const menuBtn = document.getElementById("menu-btn");
		const pinBtn = document.querySelector(".panel-pin");
		const backdrop = document.querySelector(".metadata-backdrop");

		if (menuBtn) {
			menuBtn.addEventListener("click", () => toggleMetadataPanel());
		}

		// Pin button click
		if (pinBtn) {
			pinBtn.addEventListener("click", () => togglePanelPin());
		}

		// Backdrop click closes panel (when not pinned)
		if (backdrop) {
			backdrop.addEventListener("click", () => {
				if (!panelPinned) {
					toggleMetadataPanel(false);
				}
			});
		}

		// Keyboard shortcuts for menu panel
		document.addEventListener("keydown", (e) => {
			// Cmd/Ctrl+M to toggle menu
			if ((e.metaKey || e.ctrlKey) && e.key === "m") {
				e.preventDefault();
				toggleMetadataPanel();
			}
			// Escape to close menu (when open and not pinned)
			if (e.key === "Escape" && metadataPanelVisible && !panelPinned) {
				e.preventDefault();
				toggleMetadataPanel(false);
			}
		});

		// Restore panel state from localStorage. Only a pinned panel is restored:
		// an unpinned panel is a transient overlay, so re-opening it on every load
		// would keep covering the split preview when returning to the editor.
		const savedPinned = localStorage.getItem("panelPinned");
		if (window.innerWidth > MOBILE_BREAKPOINT && savedPinned === "true") {
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
				const layout = document.querySelector(".editor-layout");
				layout.classList.remove("panel-pinned");
				panelPinned = false;
				const pinBtn = document.querySelector(".panel-pin");
				if (pinBtn) pinBtn.setAttribute("aria-pressed", "false");
			}
		});
	} else if (retries < EDITOR_INIT_MAX_RETRIES) {
		// Editor element not ready yet - retry
		retries++;
		setTimeout(initEditor, EDITOR_INIT_RETRY_INTERVAL);
	}
}

// Null when there is no caret in the editor to act on. Commands decline rather
// than coerce it, because a missing position reads as offset 0 and silently
// rewrites the first line.
function _getCursorPosition(editorEl) {
	const sel = window.getSelection();
	if (!sel.rangeCount) return null;
	const range = sel.getRangeAt(0);
	return getTextOffset(editorEl, range.startContainer, range.startOffset);
}

/**
 * Replace the note and put the caret at `caretPos`, as one undo step.
 *
 * CodeJar records history from its own keydown handler, which every command here
 * preventDefaults past, so an edit that does not bracket itself is invisible to
 * undo: Ctrl+Z skips it and lands on a much older state.
 */
function _applyEdit(editorEl, jarInstance, newText, caretPos) {
	jarInstance.recordHistory();
	jarInstance.updateCode(newText);
	_setCursorPosition(editorEl, Math.max(0, caretPos));
	jarInstance.recordHistory();
}

// A collapsed range still reports its place on the page; an all-zero rect means
// it has no box yet, so there is nothing to scroll to.
function _scrollCaretIntoView() {
	const sel = window.getSelection();
	if (!sel.rangeCount) return;
	const rect = sel.getRangeAt(0).getBoundingClientRect();
	if (!rect.height && !rect.top) return;
	if (rect.top >= 0 && rect.bottom <= window.innerHeight) return;
	window.scrollBy({ top: rect.top - window.innerHeight / 2 });
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
	if (cursorPos === null) return false;
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
				_applyEdit(editorEl, jarInstance, newText, lineStart);
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
				text.substring(0, cursorPos) +
				"\n" +
				continuation +
				text.substring(cursorPos);
			const newCursorPos = cursorPos + 1 + continuation.length;
			_applyEdit(editorEl, jarInstance, newText, newCursorPos);
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

const INDENT_SIZE = 4;
const INDENT_STR = " ".repeat(INDENT_SIZE);

function _isListItem(line) {
	return Object.values(LIST_PATTERNS).some((p) => p.test(line));
}

/**
 * Shift every line the selection touches by one level, and keep the selection on
 * those same lines so a second Tab carries on from here.
 *
 * The block moves as a unit: only its first line is measured against the item
 * above it, so the nesting the reader built inside the block survives the move.
 */
function _indentSelection(editorEl, jarInstance, outdent, start, end) {
	const text = jarInstance.toString();
	const first = _getCurrentLine(text, start);
	const last = _getCurrentLine(text, end);
	const lines = text.substring(first.lineStart, last.lineEnd).split("\n");
	if (!lines.some(_isListItem)) return false;

	const shift = (line) => {
		if (line.trim() === "") return line;
		if (!outdent) return INDENT_STR + line;
		return line.substring(Math.min(INDENT_SIZE, _leadingSpaces(line)));
	};
	const shifted = lines.map(shift);
	if (shifted.every((line, idx) => line === lines[idx])) return true;

	// Only the block's first line can break the one-level-at-a-time rule, since
	// the rest keep their offsets from it.
	const parentIndent = _previousNonBlankIndent(text, first.lineStart);
	if (
		!outdent &&
		parentIndent !== null &&
		_leadingSpaces(shifted[0]) > parentIndent + INDENT_SIZE
	) {
		return true;
	}

	// Djot only nests a list when a blank line precedes it, so the separator is
	// added or dropped ahead of the block rather than ahead of every line.
	const prev = _getPreviousLine(text, first.lineStart);
	let head = text.substring(0, first.lineStart);
	let headDelta = 0;
	if (
		!outdent &&
		prev &&
		prev.text.trim() !== "" &&
		_leadingSpaces(prev.text) < _leadingSpaces(shifted[0])
	) {
		head += "\n";
		headDelta = 1;
	} else if (outdent && prev && prev.text.trim() === "") {
		const grand = _getPreviousLine(text, prev.start);
		if (
			grand &&
			grand.text.trim() !== "" &&
			_leadingSpaces(grand.text) <= _leadingSpaces(shifted[0])
		) {
			head = text.substring(0, prev.start);
			headDelta = -1;
		}
	}

	_applyEdit(
		editorEl,
		jarInstance,
		head + shifted.join("\n") + text.substring(last.lineEnd),
		start,
	);
	const firstDelta = shifted[0].length - lines[0].length;
	const totalDelta = shifted.reduce(
		(sum, line, idx) => sum + line.length - lines[idx].length,
		0,
	);
	const newFirstStart = first.lineStart + headDelta;
	_setSelectionRange(
		editorEl,
		Math.max(newFirstStart, start + headDelta + firstDelta),
		Math.max(newFirstStart, end + headDelta + totalDelta),
	);
	return true;
}

function _handleListIndentation(editorEl, jarInstance, outdent) {
	const selection = _getSelectionRange(editorEl);
	if (!selection) return false;
	if (selection.start !== selection.end) {
		return _indentSelection(
			editorEl,
			jarInstance,
			outdent,
			selection.start,
			selection.end,
		);
	}

	const text = jarInstance.toString();
	const cursorPos = selection.start;
	const { lineStart, lineEnd, lineText } = _getCurrentLine(text, cursorPos);
	const indentSize = INDENT_SIZE;
	const indentStr = INDENT_STR;

	if (!_isListItem(lineText)) return false;

	const apply = (newText, newCursorPos) => {
		_applyEdit(editorEl, jarInstance, newText, newCursorPos);
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
			if (
				grand &&
				grand.text.trim() !== "" &&
				_leadingSpaces(grand.text) <= newIndent
			) {
				const newText =
					text.substring(0, prev.start) + newLineText + text.substring(lineEnd);
				return apply(newText, cursorPos - spacesToRemove - 1);
			}
		}

		const newText =
			text.substring(0, lineStart) + newLineText + text.substring(lineEnd);
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
	if (
		prev &&
		prev.text.trim() !== "" &&
		_leadingSpaces(prev.text) < newIndent
	) {
		const newText =
			text.substring(0, lineStart) +
			"\n" +
			newLineText +
			text.substring(lineEnd);
		return apply(newText, cursorPos + indentSize + 1);
	}

	const newText =
		text.substring(0, lineStart) + newLineText + text.substring(lineEnd);
	return apply(newText, cursorPos + indentSize);
}

function _toggleChecklistState(editorEl, jarInstance) {
	const text = jarInstance.toString();
	const cursorPos = _getCursorPosition(editorEl);
	if (cursorPos === null) return;
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

	const newText =
		text.substring(0, lineStart) + newLineText + text.substring(lineEnd);
	const newCursorPos = Math.max(lineStart, cursorPos + cursorDelta);
	_applyEdit(editorEl, jarInstance, newText, newCursorPos);
}

function _isMediaType(type) {
	return type.startsWith("image/") || type.startsWith("video/");
}

// DataTransfer exposes dropped files on .files and pasted ones on .items; a few
// browsers populate only one of the two, so both are consulted.
function _mediaFilesFrom(dataTransfer) {
	const fromFiles = Array.from(dataTransfer?.files || []).filter((file) =>
		_isMediaType(file.type),
	);
	if (fromFiles.length) return fromFiles;
	return Array.from(dataTransfer?.items || [])
		.filter((item) => item.kind === "file" && _isMediaType(item.type))
		.map((item) => item.getAsFile())
		.filter(Boolean);
}

// Extensions and browser quirks can still inject nodes into the contenteditable.
// highlight() erases them on the next keystroke, but the editor is unusable until
// then, so rebuild from the text immediately.
function _stripInjectedElements(editorEl, jarInstance) {
	if (!editorEl.querySelector("img, video, iframe, object, embed, svg")) return;
	jarInstance.updateCode(jarInstance.toString());
}

// Null when either end of the selection is outside the editor, for the same
// reason as _getCursorPosition.
function _getSelectionRange(editorEl) {
	const sel = window.getSelection();
	if (!sel.rangeCount) return null;
	const range = sel.getRangeAt(0);
	const anchor = getTextOffset(
		editorEl,
		range.startContainer,
		range.startOffset,
	);
	const focus = getTextOffset(editorEl, range.endContainer, range.endOffset);
	if (anchor === null || focus === null) return null;
	return anchor <= focus
		? { start: anchor, end: focus }
		: { start: focus, end: anchor };
}

const BULLET_PREFIX_RE = /^(\s*)- (\[[ x]\] )?/;

function _toggleBullet(editorEl, jarInstance) {
	const text = jarInstance.toString();
	const cursorPos = _getCursorPosition(editorEl);
	if (cursorPos === null) return;
	const { lineStart, lineEnd, lineText } = _getCurrentLine(text, cursorPos);

	const match = lineText.match(BULLET_PREFIX_RE);
	let newLineText;
	let cursorDelta;
	if (match) {
		newLineText = match[1] + lineText.substring(match[0].length);
		cursorDelta = -(match[0].length - match[1].length);
	} else {
		const indent = lineText.match(/^\s*/)[0];
		newLineText = `${indent}- ${lineText.substring(indent.length)}`;
		cursorDelta = 2;
	}

	const newText =
		text.substring(0, lineStart) + newLineText + text.substring(lineEnd);
	_applyEdit(
		editorEl,
		jarInstance,
		newText,
		Math.max(lineStart, cursorPos + cursorDelta),
	);
}

function _toggleInlineMarker(editorEl, jarInstance, marker) {
	const text = jarInstance.toString();
	const selection = _getSelectionRange(editorEl);
	if (!selection) return;
	const { start, end } = selection;
	const selected = text.substring(start, end);
	const width = marker.length;

	const apply = (newText, caret) => {
		_applyEdit(editorEl, jarInstance, newText, caret);
	};

	if (
		selected.length >= 2 * width &&
		selected.startsWith(marker) &&
		selected.endsWith(marker)
	) {
		const unwrapped = selected.substring(width, selected.length - width);
		apply(
			text.substring(0, start) + unwrapped + text.substring(end),
			start + unwrapped.length,
		);
		return;
	}
	if (
		start >= width &&
		text.substring(start - width, start) === marker &&
		text.substring(end, end + width) === marker
	) {
		apply(
			text.substring(0, start - width) + selected + text.substring(end + width),
			start - width + selected.length,
		);
		return;
	}

	const wrapped = marker + selected + marker;
	const caret = selected ? start + wrapped.length : start + width;
	apply(text.substring(0, start) + wrapped + text.substring(end), caret);
}

function _runToolbarAction(action, editorEl, jarInstance) {
	switch (action) {
		case "outdent":
			_handleListIndentation(editorEl, jarInstance, true);
			break;
		case "indent":
			_handleListIndentation(editorEl, jarInstance, false);
			break;
		case "bullet":
			_toggleBullet(editorEl, jarInstance);
			break;
		case "checklist":
			_toggleChecklistState(editorEl, jarInstance);
			break;
		case "bold":
			_toggleInlineMarker(editorEl, jarInstance, "*");
			break;
		case "italic":
			_toggleInlineMarker(editorEl, jarInstance, "_");
			break;
	}
}

// Height of the software keyboard, published to CSS so the panel opens clear of it.
function _syncKeyboardInset() {
	const viewport = window.visualViewport;
	const inset = viewport
		? Math.max(0, window.innerHeight - viewport.height - viewport.offsetTop)
		: 0;
	document.documentElement.style.setProperty("--keyboard-inset", `${inset}px`);
}

function _setSelectionRange(editorEl, start, end) {
	const from = getNodeAtOffset(editorEl, start);
	const to = getNodeAtOffset(editorEl, end);
	if (!from.node || !to.node) return;
	const range = document.createRange();
	range.setStart(from.node, from.offset);
	range.setEnd(to.node, to.offset);
	const sel = window.getSelection();
	sel.removeAllRanges();
	sel.addRange(range);
}

// Group 1 is indent plus any list marker, group 2 is the line's own text. Wrapping
// a whole line has to leave "1. " outside the markers or the list stops being one.
const LINE_CONTENT_RE = /^(\s*(?:[-*+] (?:\[[ x]\] )?|\d+[.)] )?)(.*?)\s*$/;

function _scopeRange(text, cursorPos, scope) {
	if (scope === "word") {
		let from = cursorPos;
		let to = cursorPos;
		while (from > 0 && /\S/.test(text[from - 1])) from -= 1;
		while (to < text.length && /\S/.test(text[to])) to += 1;
		return from === to ? null : { from, to };
	}
	const { lineStart, lineText } = _getCurrentLine(text, cursorPos);
	const [, prefix, content] = LINE_CONTENT_RE.exec(lineText);
	const from = lineStart + prefix.length;
	return content ? { from, to: from + content.length } : null;
}

const INLINE_ACTIONS = new Set(["bold", "italic"]);
const REPEATABLE_ACTIONS = new Set(["indent", "outdent"]);

/**
 * Run one command, repeating it up to `count` times when it is a command that
 * repeats. Stops early once a repetition changes nothing, which is what "no
 * longer valid Djot" looks like from here: outdenting five levels from three
 * levels deep outdents three times.
 */
function _applyCommand(action, editorEl, jarInstance, { count, scope }) {
	if (INLINE_ACTIONS.has(action)) {
		const selection = _getSelectionRange(editorEl);
		if (!selection) return;
		const { start, end } = selection;
		if (start === end) {
			const range = _scopeRange(jarInstance.toString(), start, scope);
			if (!range) return;
			_setSelectionRange(editorEl, range.from, range.to);
		}
	}

	const times = REPEATABLE_ACTIONS.has(action) ? count : 1;
	for (let i = 0; i < times; i += 1) {
		const before = jarInstance.toString();
		_runToolbarAction(action, editorEl, jarInstance);
		if (jarInstance.toString() === before) return;
	}
}

/**
 * The command panel. See adr/0011.
 *
 * Offered only to a coarse pointer, because a touchscreen is what makes the
 * keyboard commands unreachable. That takes in iPad and leaves out a narrow
 * desktop window, which a width breakpoint gets backwards.
 */
function _setupCommandPanel(editorEl, jarInstance) {
	const root = document.getElementById("cmd");
	if (!root) return;

	const trigger = document.getElementById("cmd-trigger");
	const panel = document.getElementById("cmd-panel");
	const scopeRack = document.getElementById("cmd-scope");
	const composeBtn = document.getElementById("cmd-compose");
	const applyBtn = document.getElementById("cmd-apply");
	const coarse = window.matchMedia("(pointer: coarse)");

	const state = {
		open: false,
		count: 1,
		scope: "line",
		composing: false,
		lit: [],
	};

	const setPressed = (nodes, isOn) => {
		for (const node of nodes)
			node.setAttribute("aria-pressed", String(isOn(node)));
	};

	const render = () => {
		root.classList.toggle("cmd--open", state.open);
		root.classList.toggle("cmd--counted", state.count > 1);
		root.classList.toggle("cmd--composing", state.composing);
		panel.hidden = !state.open;
		trigger.setAttribute("aria-expanded", String(state.open));
		composeBtn.setAttribute("aria-pressed", String(state.composing));
		applyBtn.hidden = !state.composing;
		setPressed(
			panel.querySelectorAll(".cmd__count"),
			(n) => Number(n.dataset.count) === state.count,
		);
		setPressed(
			panel.querySelectorAll(".cmd__scope"),
			(n) => n.dataset.scope === state.scope,
		);
		for (const key of panel.querySelectorAll(".cmd__key")) {
			key.classList.toggle(
				"cmd__key--lit",
				state.lit.includes(key.dataset.action),
			);
		}
		// A selection is its own scope, so the switch has no say while one exists.
		const selection = _getSelectionRange(editorEl);
		scopeRack.classList.toggle(
			"cmd__rack--mute",
			Boolean(selection) && selection.start !== selection.end,
		);
	};

	const close = () => {
		state.open = false;
		state.composing = false;
		state.lit = [];
		state.count = 1;
		render();
	};

	// Opening away from the caret keeps the line being edited visible. The panel
	// hangs below the trigger when the caret is above it, and above it otherwise.
	const placePanel = () => {
		const sel = window.getSelection();
		if (!sel.rangeCount) return;
		const caret = sel.getRangeAt(0).getBoundingClientRect();
		const anchor = trigger.getBoundingClientRect();
		root.classList.toggle("cmd--above", caret.top >= anchor.bottom);
	};

	// The instruction is read before the panel closes, because closing resets it.
	const runInstruction = (actions) => {
		const instruction = { count: state.count, scope: state.scope };
		close();
		for (const action of actions) {
			_applyCommand(action, editorEl, jarInstance, instruction);
		}
	};

	trigger.addEventListener("click", () => {
		if (dragged) return;
		state.open = !state.open;
		if (state.open) placePanel();
		render();
	});

	// Suppressing the default keeps focus, and the keyboard, on the editor. Without
	// it the tap blurs the contenteditable and the selection the command needs is gone.
	panel.addEventListener("pointerdown", (event) => {
		if (event.target.closest("button")) event.preventDefault();
	});

	panel.addEventListener("click", (event) => {
		const button = event.target.closest("button");
		if (!button) return;

		if (button.dataset.count) {
			state.count = Number(button.dataset.count);
			render();
			return;
		}
		if (button.dataset.scope) {
			state.scope = button.dataset.scope;
			render();
			return;
		}
		if (button === composeBtn) {
			state.composing = !state.composing;
			state.lit = [];
			render();
			return;
		}
		if (button === applyBtn) {
			runInstruction(state.lit);
			return;
		}
		if (button.id === "cmd-cancel") {
			close();
			return;
		}
		// Media opens a file picker rather than transforming text, so a count and
		// compose have nothing to say about it. The panel's pointerdown handler has
		// already kept focus on the editor, so the upload lands at the caret.
		if (button.dataset.action === "media") {
			close();
			document.getElementById("media-input")?.click();
			return;
		}
		if (!button.dataset.action) return;

		// Composing lights a command instead of firing it, and a second tap puts it
		// out. Tapping twice never means doing it twice, because repeating is the
		// count's job.
		if (state.composing) {
			const action = button.dataset.action;
			state.lit = state.lit.includes(action)
				? state.lit.filter((lit) => lit !== action)
				: [...state.lit, action];
			render();
			return;
		}
		runInstruction([button.dataset.action]);
	});

	// Dragging the trigger moves it within the editor, so it can be kept away from
	// whichever hand is holding the phone. Past the halfway line it changes sides.
	//
	// A tap is never perfectly still, and a tap that moved the trigger a pixel and
	// then refused to open would be maddening, so travel has to clear a threshold
	// before any of this counts as a drag.
	const DRAG_THRESHOLD = 6; // px
	let dragged = false;
	let dragOrigin = null;
	let pointerId = null;

	const positionKey = "yakShears.cmdTrigger";
	const savedPosition = window.localStorage.getItem(positionKey);
	if (savedPosition) {
		const [side, top] = savedPosition.split(":");
		root.dataset.side = side === "left" ? "left" : "right";
		root.style.setProperty("--cmd-top", `${Number(top) || 0}px`);
	}

	trigger.addEventListener("pointerdown", (event) => {
		// Same reason as the panel above: without this the tap blurs the editor,
		// which dismisses the keyboard and throws away the selection the command
		// was going to act on. Capture still works through a prevented default.
		event.preventDefault();
		pointerId = event.pointerId;
		dragged = false;
		dragOrigin = { x: event.clientX, y: event.clientY };
		trigger.setPointerCapture(pointerId);
	});

	trigger.addEventListener("pointermove", (event) => {
		if (pointerId !== event.pointerId || !trigger.hasPointerCapture(pointerId))
			return;
		const travel = Math.hypot(
			event.clientX - dragOrigin.x,
			event.clientY - dragOrigin.y,
		);
		if (!dragged && travel < DRAG_THRESHOLD) return;
		dragged = true;

		const bounds = root.parentElement.getBoundingClientRect();
		const top = Math.min(
			Math.max(event.clientY - bounds.top - trigger.offsetHeight / 2, 0),
			Math.max(bounds.height - trigger.offsetHeight, 0),
		);
		root.dataset.side =
			event.clientX < bounds.left + bounds.width / 2 ? "left" : "right";
		root.style.setProperty("--cmd-top", `${top}px`);
	});

	const endDrag = (event) => {
		if (pointerId !== event.pointerId) return;
		trigger.releasePointerCapture(pointerId);
		pointerId = null;
		if (!dragged) return;
		const top = root.style.getPropertyValue("--cmd-top").replace("px", "");
		window.localStorage.setItem(positionKey, `${root.dataset.side}:${top}`);
		// The tap that ended the drag is not a request to open the panel.
		requestAnimationFrame(() => {
			dragged = false;
		});
	};
	trigger.addEventListener("pointerup", endDrag);
	trigger.addEventListener("pointercancel", endDrag);

	// Every command acts on a cursor, so a panel with nothing to act on is
	// occlusion for its own sake.
	const refresh = () => {
		const available = coarse.matches && document.activeElement === editorEl;
		root.hidden = !available;
		if (!available && state.open) close();
	};

	editorEl.addEventListener("focus", refresh);
	// Buttons cancel their own blur above, so a blur that survives a frame is real.
	editorEl.addEventListener("blur", () => requestAnimationFrame(refresh));
	document.addEventListener("selectionchange", () => {
		if (state.open) render();
	});
	coarse.addEventListener("change", refresh);

	_syncKeyboardInset();
	if (window.visualViewport) {
		window.visualViewport.addEventListener("resize", _syncKeyboardInset);
		window.visualViewport.addEventListener("scroll", _syncKeyboardInset);
	}

	document.addEventListener("keydown", (event) => {
		if (event.key === "Escape" && state.open) close();
	});

	render();
	refresh();
}

/**
 * Line-level diff between the saved note and the draft.
 *
 * Longest common subsequence over lines, which is the same shape `diff` uses. The
 * table is O(n*m); notes are short enough that this is cheaper than shipping a
 * library, and the editor is already blocked on a failed save when it runs.
 *
 * @param {string} theirs - Text as it now sits on disk
 * @param {string} mine - Text in the editor
 * @returns {Array<{kind: "same"|"theirs"|"mine", text: string}>}
 */
function _lineDiff(theirs, mine) {
	const left = theirs.split("\n");
	const right = mine.split("\n");
	const lcs = Array.from({ length: left.length + 1 }, () =>
		new Array(right.length + 1).fill(0),
	);
	for (let i = left.length - 1; i >= 0; i--) {
		for (let j = right.length - 1; j >= 0; j--) {
			lcs[i][j] =
				left[i] === right[j]
					? lcs[i + 1][j + 1] + 1
					: Math.max(lcs[i + 1][j], lcs[i][j + 1]);
		}
	}
	const rows = [];
	let i = 0;
	let j = 0;
	while (i < left.length && j < right.length) {
		if (left[i] === right[j]) {
			rows.push({ kind: "same", text: left[i] });
			i++;
			j++;
		} else if (lcs[i + 1][j] >= lcs[i][j + 1]) {
			rows.push({ kind: "theirs", text: left[i++] });
		} else {
			rows.push({ kind: "mine", text: right[j++] });
		}
	}
	while (i < left.length) rows.push({ kind: "theirs", text: left[i++] });
	while (j < right.length) rows.push({ kind: "mine", text: right[j++] });
	return rows;
}

const DIFF_MARKS = { same: " ", theirs: "−", mine: "+" };

const CONFLICT_OPEN = "<<<<<<< on disk";
const CONFLICT_SPLIT = "=======";
const CONFLICT_CLOSE = ">>>>>>> my draft";

/**
 * Any line that would read as a conflict marker to `_conflictMarkup`'s reader.
 *
 * Deliberately loose about what follows the seven characters: a note that saved
 * with a bare `=======` under a heading is still caught, and a false stop costs one
 * extra press while a false pass costs the text the lease exists to protect.
 */
const CONFLICT_MARKER_RE = /^(?:<{7}|={7}|>{7})/m;

/**
 * Weave the two versions into one buffer, marking every run the sides disagree on.
 *
 * A run of consecutive non-`same` rows is exactly one conflict hunk, so the diff
 * already computed for the panel is all this needs. Agreed lines pass through bare,
 * which keeps the markers down to the parts actually in dispute.
 *
 * Both sides are emitted even when one is empty, because an unmarked deletion is
 * indistinguishable from text that was never there.
 *
 * @param {Array<{kind: string, text: string}>} rows - Output of _lineDiff
 * @returns {string} Buffer text carrying git-style conflict markers
 */
function _conflictMarkup(rows) {
	const out = [];
	for (let i = 0; i < rows.length; ) {
		if (rows[i].kind === "same") {
			out.push(rows[i].text);
			i++;
			continue;
		}
		const theirs = [];
		const mine = [];
		while (i < rows.length && rows[i].kind !== "same") {
			(rows[i].kind === "theirs" ? theirs : mine).push(rows[i].text);
			i++;
		}
		out.push(CONFLICT_OPEN, ...theirs, CONFLICT_SPLIT, ...mine, CONFLICT_CLOSE);
	}
	return out.join("\n");
}

const MARKER_OVERRIDE_MS = 8000;
let markerOverrideUntil = 0;

/**
 * Whether the save should be refused because conflict markers are still in the buffer.
 *
 * Half-resolved text saved as a note is the loss the lease exists to prevent, so the
 * first press always stops. A second press inside the window goes through, for the
 * note that genuinely wants those characters in it.
 *
 * @returns {boolean} True when the caller must abandon the save
 */
function _markersBlockSave() {
	if (!CONFLICT_MARKER_RE.test(getEditorContent())) return false;
	if (Date.now() < markerOverrideUntil) {
		markerOverrideUntil = 0;
		return false;
	}
	markerOverrideUntil = Date.now() + MARKER_OVERRIDE_MS;
	updateSaveStatus("Conflict markers left. Save again to keep them.");
	return true;
}

/**
 * Paint a diff into the conflict panel. Built with the DOM rather than innerHTML,
 * so note text can never be parsed as markup.
 *
 * @param {HTMLElement} target - Container to fill
 * @param {Array<{kind: string, text: string}>} rows - Output of _lineDiff
 */
function _paintDiff(target, rows) {
	target.replaceChildren();
	for (const row of rows) {
		const line = document.createElement("div");
		line.className = `diffline diffline--${row.kind}`;
		const mark = document.createElement("span");
		mark.className = "diffline__mark";
		mark.setAttribute("aria-hidden", "true");
		mark.textContent = DIFF_MARKS[row.kind];
		const text = document.createElement("span");
		text.className = "diffline__text";
		text.textContent = row.text;
		line.append(mark, text);
		target.append(line);
	}
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
