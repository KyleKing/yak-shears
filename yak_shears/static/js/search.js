// Search functionality for Telescope-style UI
if (document.body) {
	document.body.classList.add("js-loaded");
} else {
	document.addEventListener("DOMContentLoaded", () => {
		document.body.classList.add("js-loaded");
	});
}

const resultsList = document.getElementById("search-results-list");
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

// Load preview for selected result
async function loadPreview(resultElement) {
	if (!resultElement) return;
	const previewPane = document.getElementById("search-preview-content");
	if (!previewPane) return;

	const searchInput = document.querySelector(".search-input");
	const path = resultElement.dataset.path;
	const line = resultElement.dataset.line;

	try {
		const response = await fetch(
			`/api/yak-preview?path=${encodeURIComponent(path)}&line=${line}&query=${encodeURIComponent(searchInput.value)}`,
			{
				credentials: "include",
			},
		);
		if (response.ok) {
			const data = await response.json();
			previewPane.innerHTML = data.html;
		}
	} catch (error) {
		console.error("Failed to load preview:", error);
	}
}

// Setup results
function setupResults() {
	selectedIndex = -1;
	const results = document.querySelectorAll(".search-result");
	if (results.length > 0) {
		selectedIndex = 0;
		updateSelection(results);
		loadPreview(results[0]);

		// Attach click handlers to results
		results.forEach((result, index) => {
			result.addEventListener("click", function () {
				selectedIndex = index;
				updateSelection(results);
				loadPreview(result);
			});
		});
	}
}

// Expose function to window for HTMX
window.setupResults = setupResults;

// Handle initial results
setupResults();

// Keyboard navigation
document.addEventListener("keydown", function (e) {
	if (!resultsList) return;
	const resultItems = resultsList.querySelectorAll(".search-result");
	if (resultItems.length === 0) return;

	switch (e.key) {
		case "ArrowDown":
			e.preventDefault();
			if (selectedIndex < resultItems.length - 1) {
				selectedIndex++;
				updateSelection(resultItems);
				loadPreview(resultItems[selectedIndex]);
			}
			break;
		case "ArrowUp":
			e.preventDefault();
			if (selectedIndex > 0) {
				selectedIndex--;
				updateSelection(resultItems);
				loadPreview(resultItems[selectedIndex]);
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
			searchInput.blur();
			break;
	}
});
