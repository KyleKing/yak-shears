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
			previewPane.innerHTML = data.html;
			if (useModal) {
				scrollToFirstMatch(previewPane);
			}
		}
	} catch (error) {
		console.error("Failed to load preview:", error);
	}
}

// Scroll to first match in preview
function scrollToFirstMatch(previewPane) {
	const firstHighlight = previewPane.querySelector(".search-highlight");
	if (firstHighlight) {
		firstHighlight.scrollIntoView({ behavior: "smooth", block: "center" });
	}
}

// Open modal
function openModal() {
	const modal = document.getElementById("search-preview-modal");
	if (modal) {
		modal.style.display = "flex";
		document.body.style.overflow = "hidden";
	}
}

// Close modal
function closeModal() {
	const modal = document.getElementById("search-preview-modal");
	if (modal) {
		modal.style.display = "none";
		document.body.style.overflow = "";
	}
}

// Setup results
function setupResults() {
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

// Modal event listeners
document.addEventListener("DOMContentLoaded", function () {
	const modalClose = document.getElementById("search-preview-modal-close");
	const modalOverlay = document.querySelector(".search-preview-modal__overlay");

	if (modalClose) {
		modalClose.addEventListener("click", closeModal);
	}
	if (modalOverlay) {
		modalOverlay.addEventListener("click", closeModal);
	}
});

// Keyboard navigation
document.addEventListener("keydown", function (e) {
	const resultsList = document.getElementById("search-results-list");
	if (!resultsList) return;
	const resultItems = resultsList.querySelectorAll(".search-result");
	if (resultItems.length === 0) return;

	const modal = document.getElementById("search-preview-modal");
	const modalIsOpen = modal && modal.style.display === "flex";

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
			const searchInput = document.querySelector(".search-input");
			if (searchInput) {
				searchInput.blur();
			}
			break;
	}
});
