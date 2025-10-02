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
	container.className = "editor-container " + mode.replace("-", "");

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

		const saved = localStorage.getItem(storageKey);
		if (saved && saved !== serverContent) {
			// TODO: Make this part of the jinja template instead of added dynamically!
			const toggleDiv = document.createElement("div");
			toggleDiv.className = "editor__toggle";
			toggleDiv.innerHTML = `
       <button id="server-btn" class="active">Server Version</button>
       <button id="local-btn">Unsaved Local Changes</button>
     `;
			document.querySelector(".editor__header").appendChild(toggleDiv);

			document.getElementById("server-btn").addEventListener("click", () => {
				editor.textContent = serverContent;
				jar.updateCode(serverContent);
				document.getElementById("server-btn").classList.add("active");
				document.getElementById("local-btn").classList.remove("active");
			});

			document.getElementById("local-btn").addEventListener("click", () => {
				editor.textContent = saved;
				jar.updateCode(saved);
				document.getElementById("local-btn").classList.add("active");
				document.getElementById("server-btn").classList.remove("active");
			});
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

		// Set initial view mode (default to editor-only for mobile, side-by-side for desktop)
		const isMobile = window.innerWidth <= 768;
		const initialView = isMobile ? "editor" : "side-by-side";
		setViewMode(initialView);

		// Handle window resize to switch modes
		let lastWidth = window.innerWidth;
		window.addEventListener("resize", () => {
			const wasMobile = lastWidth <= 768;
			const nowMobile = window.innerWidth <= 768;
			lastWidth = window.innerWidth;
			if (wasMobile !== nowMobile && currentView === "side-by-side") {
				setViewMode(nowMobile ? "editor" : "side-by-side");
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
