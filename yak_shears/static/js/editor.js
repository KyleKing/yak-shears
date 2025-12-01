/**
 * Editor save status states:
 * - "Synced": No difference from server, checked by polling
 * - "Modified": Local changes ready for submission
 * - "Saved": In sync because local changes were pushed
 * - "Saving...": In the process of sending changes to the server
 */

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
				if (e.metaKey && e.key === "Enter") {
					e.preventDefault();
					document.getElementById("save-btn").click();
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
