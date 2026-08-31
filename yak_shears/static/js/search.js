// Search functionality for Telescope-style UI
if (document.body) {
	document.body.classList.add("js-loaded");
} else {
	document.addEventListener("DOMContentLoaded", () => {
		document.body.classList.add("js-loaded");
	});
}

let selectedIndex = -1;

// Update visual selection
function updateSelection(items) {
	items.forEach((item, index) => {
		if (index === selectedIndex) {
			item.classList.add("selected");
		} else {
			item.classList.remove("selected");
		}
	});
}

// Check if screen is small (modal mode)
function isSmallScreen() {
	return window.innerWidth <= 768;
}

// Load preview for selected result
async function loadPreview(resultElement, useModal = false) {
	if (!resultElement) return;
	const previewPaneId = useModal
		? "search-preview-modal-content"
		: "search-preview-content";
	const previewPane = document.getElementById(previewPaneId);
	if (!previewPane) return;

	const searchInput = document.querySelector(".search-input");
	const path = resultElement.dataset.path;

	try {
		const response = await fetch(
			`/api/yak-preview?path=${encodeURIComponent(path)}&query=${encodeURIComponent(searchInput.value)}`,
			{
				credentials: "include",
			},
		);
		if (response.ok) {
			const data = await response.json();
			renderPreviewInto(previewPane, data);
			// Center the first highlighted match in the preview (3.2)
			scrollToFirstMatch(previewPane);
		}
	} catch (error) {
		console.error("Failed to load preview:", error);
	}
}

// Render the Djot source into the pane and highlight query matches
function renderPreviewInto(previewPane, data) {
	const rendered = window.djot
		? window.djot.renderHTML(window.djot.parse(data.source))
		: escapeHtml(data.source);

	previewPane.innerHTML =
		`<div class="search-preview__body"><div class="preview-content djot-rendered"></div></div>` +
		`<a href="${data.edit_url}" class="search-preview__open">Open` +
		`<span class="search-preview__hint">↵ Enter</span></a>`;

	const body = previewPane.querySelector(".djot-rendered");
	if (window.djot) {
		body.innerHTML = rendered;
	} else {
		body.textContent = data.source;
	}
	highlightTextNodes(body, data.query);
}

function escapeRegExp(text) {
	return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function escapeHtml(text) {
	return text.replace(
		/[&<>]/g,
		(c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[c],
	);
}

// Wrap query matches in <span class="search-highlight"> without corrupting
// markup: only text nodes are mutated, and code/pre are skipped.
function highlightTextNodes(root, query) {
	const terms = (query || "")
		.toLowerCase()
		.split(/\s+/)
		.filter(Boolean);
	if (!terms.length) return;

	const pattern = `(${terms.map(escapeRegExp).join("|")})`;
	const re = new RegExp(pattern, "gi");
	// A global regex carries lastIndex between calls, so the walker tests with its
	// own stateless copy and only the replace below scans from the start.
	const probe = new RegExp(pattern, "i");
	const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
		acceptNode(node) {
			const parent = node.parentElement;
			if (!parent || parent.closest("code, pre, .search-highlight")) {
				return NodeFilter.FILTER_REJECT;
			}
			return probe.test(node.nodeValue)
				? NodeFilter.FILTER_ACCEPT
				: NodeFilter.FILTER_REJECT;
		},
	});

	const targets = [];
	while (walker.nextNode()) targets.push(walker.currentNode);

	for (const node of targets) {
		const value = node.nodeValue;
		const frag = document.createDocumentFragment();
		let last = 0;
		value.replace(re, (match, _group, offset) => {
			if (offset > last) {
				frag.appendChild(document.createTextNode(value.slice(last, offset)));
			}
			const span = document.createElement("span");
			span.className = "search-highlight";
			span.textContent = match;
			frag.appendChild(span);
			last = offset + match.length;
			return match;
		});
		if (last < value.length) {
			frag.appendChild(document.createTextNode(value.slice(last)));
		}
		node.parentNode.replaceChild(frag, node);
	}
}

// Scroll to first match in preview
function scrollToFirstMatch(previewPane) {
	const firstHighlight = previewPane.querySelector(".search-highlight");
	if (firstHighlight) {
		firstHighlight.scrollIntoView({ behavior: "smooth", block: "center" });
	}
}

// The result that was selected before the modal opened, refocused when it closes
let previouslyFocusedResult = null;
let modalHandlersBound = false;

function getModal() {
	return document.getElementById("search-preview-modal");
}

function isModalOpen() {
	const modal = getModal();
	return Boolean(modal && modal.classList.contains("is-open"));
}

// Open modal
function openModal() {
	const modal = getModal();
	if (!modal) return;
	const results = document.querySelectorAll(".search-result");
	previouslyFocusedResult = results[selectedIndex] || null;
	modal.hidden = false;
	modal.classList.add("is-open");
	document.body.style.overflow = "hidden";
	const closeButton = document.getElementById("search-preview-modal-close");
	if (closeButton) {
		requestAnimationFrame(() => closeButton.focus());
	}
}

// Close modal
function closeModal() {
	const modal = getModal();
	if (!modal) return;
	modal.classList.remove("is-open");
	modal.hidden = true;
	document.body.style.overflow = "";
	if (previouslyFocusedResult && previouslyFocusedResult.isConnected) {
		previouslyFocusedResult.focus();
	}
	previouslyFocusedResult = null;
}

// Delegated so repeated HTMX swaps of the modal markup never stack listeners
function bindModalHandlers() {
	if (modalHandlersBound) return;
	modalHandlersBound = true;
	document.addEventListener("click", (event) => {
		const target = event.target;
		if (!(target instanceof Element)) return;
		if (
			target.closest(".search-preview-modal__close") ||
			target.classList.contains("search-preview-modal__overlay")
		) {
			closeModal();
		}
	});
}

// Setup results
function setupResults() {
	bindModalHandlers();
	selectedIndex = -1;
	const results = document.querySelectorAll(".search-result");
	if (results.length > 0) {
		selectedIndex = 0;
		updateSelection(results);
		if (!isSmallScreen()) {
			loadPreview(results[0]);
		}

		// Attach click handlers to results
		results.forEach((result, index) => {
			result.addEventListener("click", function () {
				selectedIndex = index;
				updateSelection(results);
				if (isSmallScreen()) {
					loadPreview(result, true);
					openModal();
				} else {
					loadPreview(result);
				}
			});
		});
	}
}

// Expose function to window for HTMX
window.setupResults = setupResults;

// Handle initial results. This script is loaded in <head>, so on a full-page
// load the results are not in the DOM yet; wait for DOMContentLoaded.
if (document.readyState === "loading") {
	document.addEventListener("DOMContentLoaded", setupResults);
} else {
	setupResults();
}

document.addEventListener("DOMContentLoaded", bindModalHandlers);

// Keyboard navigation
document.addEventListener("keydown", function (e) {
	const resultsList = document.getElementById("search-results-list");
	if (!resultsList) return;
	const resultItems = resultsList.querySelectorAll(".search-result");
	if (resultItems.length === 0) return;

	const modalIsOpen = isModalOpen();

	switch (e.key) {
		case "ArrowDown":
			e.preventDefault();
			if (selectedIndex < resultItems.length - 1) {
				selectedIndex++;
				updateSelection(resultItems);
				loadPreview(resultItems[selectedIndex], modalIsOpen);
			}
			break;
		case "ArrowUp":
			e.preventDefault();
			if (selectedIndex > 0) {
				selectedIndex--;
				updateSelection(resultItems);
				loadPreview(resultItems[selectedIndex], modalIsOpen);
			}
			break;
		case "Enter":
			if (
				selectedIndex >= 0 &&
				resultItems[selectedIndex] &&
				!e.shiftKey &&
				!e.ctrlKey
			) {
				e.preventDefault();
				const path = resultItems[selectedIndex].dataset.path;
				const searchInput = document.querySelector(".search-input");
				const query = searchInput ? searchInput.value : "";
				window.location.href = `/edit?yak=${encodeURIComponent(path)}&query=${encodeURIComponent(query)}`;
			}
			break;
		case "Escape":
			if (modalIsOpen) {
				e.preventDefault();
				closeModal();
				break;
			}
			const searchInput = document.querySelector(".search-input");
			if (searchInput) {
				searchInput.blur();
			}
			break;
	}
});
