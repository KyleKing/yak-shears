// Generic text input + filtered listbox, keyboard-first (replaces native
// <datalist>, whose suggestion popup cannot be styled in any browser).
// Markup contract: `[data-combobox]` wraps a `.combobox__input` and a
// `.combobox__list` of `.combobox__option[data-value]` elements.
function setupCombobox(root) {
	const input = root.querySelector(".combobox__input");
	const list = root.querySelector(".combobox__list");
	const options = Array.from(list.querySelectorAll(".combobox__option"));
	let activeIndex = -1;

	function visibleOptions() {
		return options.filter((opt) => !opt.hidden);
	}

	function isOpen() {
		return !list.hidden;
	}

	function open() {
		list.hidden = false;
		input.setAttribute("aria-expanded", "true");
	}

	function close() {
		list.hidden = true;
		input.setAttribute("aria-expanded", "false");
		setActive(-1);
	}

	function setActive(index) {
		const visible = visibleOptions();
		visible.forEach((opt) => opt.classList.remove("combobox__option--active"));
		activeIndex = index;
		const active = visible[index];
		if (active) {
			active.classList.add("combobox__option--active");
			active.scrollIntoView({ block: "nearest" });
			input.setAttribute("aria-activedescendant", active.id);
		} else {
			input.removeAttribute("aria-activedescendant");
		}
	}

	function filter() {
		const query = input.value.trim().toLowerCase();
		options.forEach((opt) => {
			opt.hidden = query.length > 0 && !opt.dataset.value.toLowerCase().includes(query);
		});
		setActive(-1);
	}

	function selectOption(opt) {
		input.value = opt.dataset.value;
		close();
		input.focus();
	}

	input.addEventListener("input", () => {
		filter();
		open();
	});

	input.addEventListener("focus", () => {
		filter();
		open();
	});

	input.addEventListener("keydown", (e) => {
		switch (e.key) {
			case "ArrowDown":
				e.preventDefault();
				if (!isOpen()) {
					open();
					filter();
				}
				setActive(Math.min(activeIndex + 1, visibleOptions().length - 1));
				break;
			case "ArrowUp":
				e.preventDefault();
				if (!isOpen()) {
					open();
					filter();
				}
				setActive(Math.max(activeIndex - 1, 0));
				break;
			case "Enter":
				if (isOpen() && activeIndex >= 0) {
					const active = visibleOptions()[activeIndex];
					if (active) {
						e.preventDefault();
						selectOption(active);
					}
				}
				// Otherwise let Enter submit the form as usual.
				break;
			case "Escape":
				if (isOpen()) {
					e.preventDefault();
					close();
				}
				break;
			case "Tab":
				close();
				break;
		}
	});

	options.forEach((opt) => {
		// mousedown (not click) fires before the input's blur/close.
		opt.addEventListener("mousedown", (e) => {
			e.preventDefault();
			selectOption(opt);
		});
	});

	document.addEventListener("click", (e) => {
		if (!root.contains(e.target)) close();
	});
}

function initComboboxes() {
	document.querySelectorAll("[data-combobox]").forEach(setupCombobox);
}

if (document.readyState === "loading") {
	document.addEventListener("DOMContentLoaded", initComboboxes);
} else {
	initComboboxes();
}
