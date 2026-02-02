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
function renderPreview(content) {
	const previewContent = document.getElementById("preview-content");
	if (previewContent && window.djot) {
		try {
			// Parse Djot → AST → HTML
			const html = window.djot.renderHTML(window.djot.parse(content));
			previewContent.innerHTML = html;
			
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
	container.className = "editor-container " + modeClassMap[mode];

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
				if (e.metaKey && e.key === "Enter") {
					e.preventDefault();
					document.getElementById("save-btn").click();
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
			});
		});

		// Initialize view mode based on screen size
		// Desktop defaults to side-by-side, mobile to editor-only
		const isMobile = window.innerWidth <= MOBILE_BREAKPOINT;
		const initialView = isMobile ? "editor" : "editor"; // TODO: Consider defaulting to "side-by-side" on desktop
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

		// On desktop, restore pinned state if it was previously pinned
		if (window.innerWidth > MOBILE_BREAKPOINT && savedPinned === 'true') {
			togglePanelPin();
		} else if (savedVisible === 'true') {
			// Or just show panel if it was visible (but not pinned)
			toggleMetadataPanel(true);
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
 * Called by HTMX via hx-vals="js:{content: getEditorContent(), yak: '...'}"
 * See edit.html.jinja line 33
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
window.getEditorContent = getEditorContent;
window.toggleMetadataPanel = toggleMetadataPanel;
window.togglePanelPin = togglePanelPin;

// Initialize editor on page load
initEditor();
