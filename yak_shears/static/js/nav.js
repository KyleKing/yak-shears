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

// The back control is an anchor to /yaks so it works with scripting off and in
// a fresh tab. When there is a same-origin page behind this one, go there
// instead, which is the only real back a standalone homescreen app has.
const backLink = document.getElementById("header-back");

if (backLink) {
	backLink.addEventListener("click", (event) => {
		const sameOrigin =
			document.referrer && new URL(document.referrer).origin === window.location.origin;
		if (sameOrigin && window.history.length > 1) {
			event.preventDefault();
			window.history.back();
		}
	});
}

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

// A homescreen app resumes where it was left instead of reloading, so the server
// never gets to say the session ended. The page is covered as soon as it hides,
// and uncovered on return only once the session checks out, so a stale session
// never shows notes. A short absence uncovers at once and checks behind it.
const AUTH_COVER_AFTER_MS = 60 * 1000;
const root = document.documentElement;
let hiddenAt = null;

function goToLogin() {
	const here = window.location.pathname + window.location.search;
	// Read by editor.js, whose leave-page prompt would otherwise block the redirect.
	// The draft is already in localStorage and reopens after login.
	root.dataset.authExpired = "";
	window.location.replace(`/auth/login?redirect=${encodeURIComponent(here)}`);
}

async function checkSession() {
	try {
		const response = await fetch("/api/session", {
			cache: "no-store",
			redirect: "manual",
		});
		if (response.type === "opaqueredirect" || response.status === 401) {
			goToLogin();
			return;
		}
	} catch {
		// Offline. The page is already here, and locking the reader out of a draft
		// they cannot save anyway helps no one.
	}
	root.classList.remove("is-auth-pending");
}

if (!window.location.pathname.startsWith("/auth/")) {
	document.addEventListener("visibilitychange", () => {
		if (document.visibilityState === "hidden") {
			hiddenAt = Date.now();
			root.classList.add("is-auth-pending");
			return;
		}
		if (hiddenAt !== null && Date.now() - hiddenAt < AUTH_COVER_AFTER_MS) {
			root.classList.remove("is-auth-pending");
		}
		hiddenAt = null;
		checkSession();
	});

	// Restored from the back-forward cache, which no-store should prevent but
	// is not guaranteed to on every browser.
	window.addEventListener("pageshow", (event) => {
		if (!event.persisted) return;
		root.classList.add("is-auth-pending");
		checkSession();
	});

	// A save or search made after the session ended gets a 401 with HX-Redirect,
	// which htmx follows. Flag it first so nothing prompts on the way out.
	document.body.addEventListener("htmx:beforeOnLoad", (event) => {
		if (event.detail.xhr.status === 401) root.dataset.authExpired = "";
	});
}
