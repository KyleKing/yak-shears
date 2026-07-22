// Collapsible <details> regions in the page chrome: the header menu and the
// /yaks sort/filter rows.
//
// Both ship open in the markup and are collapsed here at phone widths. The
// reverse (ship closed, force open with CSS) does not work, because Chromium
// hides a closed <details> body with content-visibility on ::details-content
// and an author `display` rule cannot override that. Shipping open also
// degrades better: without JavaScript the content stays reachable.

const MOBILE_BREAKPOINT = 768; // px - matches the CSS media queries

const collapsibles = ["nav-menu", "yaks-controls"]
	.map((id) => document.getElementById(id))
	.filter(Boolean);

function isMobile() {
	return window.innerWidth <= MOBILE_BREAKPOINT;
}

function applyBreakpoint() {
	for (const region of collapsibles) {
		region.open = !isMobile();
	}
}

applyBreakpoint();

let wasMobile = isMobile();
window.addEventListener("resize", () => {
	if (isMobile() !== wasMobile) {
		wasMobile = isMobile();
		applyBreakpoint();
	}
});

const navMenu = document.getElementById("nav-menu");

if (navMenu) {
	const closeNav = () => {
		if (isMobile()) navMenu.open = false;
	};

	document.addEventListener("click", (event) => {
		if (navMenu.open && !navMenu.contains(event.target)) closeNav();
	});

	navMenu.addEventListener("click", (event) => {
		if (event.target.closest(".nav__link")) closeNav();
	});

	document.addEventListener("keydown", (event) => {
		if (event.key === "Escape" && navMenu.open && isMobile()) {
			closeNav();
			navMenu.querySelector(".nav__toggle")?.focus();
		}
	});
}
