# 0009: iOS Homescreen App Navigation and Offline Strategy

## Status

Accepted (2026-07-22) for the manifest decision. The offline half is deliberately left open, and this record says what would decide it.

## Context

The site was added to the iOS homescreen. Launching it and then navigating anywhere puts the page inside an in-app browser: a close button on the left, `yak-shears.kyleking.me` in a bar across the top, and a reader-view control on the right (screenshot `7-Overlay.PNG`). That bar eats a chunk of a phone screen that the editor already fights for (ADR 0008), and it makes the thing feel like a bookmark, which is what it was.

The cause is that the app shipped no web app manifest at all. `base.html.jinja` carried a viewport meta and nothing else. Per [WebKit's own description of Home Screen web apps](https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/), a site is treated as a web app only if it serves a manifest whose `display` member is `standalone` or `fullscreen`, and without that "the website will be saved as a Home Screen bookmark" that opens in the default browser. Apple's [WWDC23 "What's new in web apps"](https://developer.apple.com/videos/play/wwdc2023/10120/) adds the second half of the rule: every web app has a scope, links inside the scope stay in the web app, and on iOS links outside the scope open in Safari View Controller.

The question raised alongside the bug was broader: is the fix to become a SPA, or to go native?

## Decision

1. Ship a web app manifest with `display: standalone`, `scope: /`, `start_url: /yaks`, theme and background colors, and PNG plus maskable icons, together with `apple-touch-icon` and the `apple-mobile-web-app-*` meta tags (the icon precedence and title come from the same WebKit post, where `apple-touch-icon` wins over manifest icons if both are present).
2. Keep the server-rendered HTMX architecture of [ADR 0006](./0006-ssr-htmx-architecture.md). No SPA, no rewrite.
3. No service worker yet, and therefore no offline support yet. Treat offline as a separate decision, sketched below and not taken here.

## Why the overlay happens

Three rules interact, and all three matter for this app:

- Standalone display is what makes iOS open the icon as an app rather than as a browser tab. Without it there is no app context to stay inside, so every navigation is just a bookmark opening a browser
- Scope decides what counts as "inside". The default scope is the host of the page the web app was created from, and MDN's [scope reference](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Manifest/Reference/scope) notes that off-scope navigations are not blocked, they just lose the app chrome and gain a URL bar. Declaring `scope: /` explicitly is the safe move, since reports of iOS behaving badly with an omitted scope are common enough to not be worth testing the default
- `target="_blank"` is the gotcha that matters here specifically. `enhanceMedia()` in `editor.js` rewrites image embeds so the thumbnail links to the full-resolution file, and it sets `link.target = "_blank"`. Those URLs are in scope (`/media/...`), so scope alone does not save them. Whether a standalone iOS web app keeps a `_blank` link in-app or hands it to Safari View Controller has changed across iOS versions and is not something Apple documents clearly, so this needs checking on the device once the manifest is live. If full-resolution images do bounce out, the fix is a same-tab link or an in-page lightbox rather than a new browsing context

## Options considered for the navigation experience

### Option A: server-rendered pages with HTMX, as today (chosen)

Each navigation is a full HTML response, with HTMX handling save, delete, and search in place. Once the manifest declares standalone, those navigations stay inside the web app and the overlay is gone. Nothing to build beyond the manifest, and ADR 0006's reasoning (single-response first paint, no build step, no client router) holds unchanged.

The cost is a white flash and a full re-parse on each page change, which is the normal cost of server-rendered navigation and is small on a vault of a few hundred short notes.

### Option B: add `hx-boost`

[`hx-boost`](https://htmx.org/attributes/hx-boost/) on `<body>` turns same-domain anchors and forms into AJAX requests that swap the body and push history, keeping the header, scroll position, and any in-flight state across a navigation. It is one attribute, it degrades to plain links without JS, and it changes no server code.

Worth doing as a follow-up rather than now. It interacts with per-page JS init (the editor and search modules would need to re-run on `htmx:load` instead of `DOMContentLoaded`), and mixing it in during the same round as the mobile layout work would make regressions hard to attribute. It only boosts same-domain, non-anchor links, so `_blank` media links are unaffected either way.

### Option C: rewrite as a SPA

A client-side router and a JSON API under it. This is exactly the option ADR 0006 rejected, and nothing in this bug argues for revisiting it. The overlay came from a missing manifest, which the manifest fixes. A SPA would add a build pipeline, client routing, and state management for one person to maintain, and would not by itself make anything work offline (that still needs a service worker or a native store).

### Option D: native iOS app

Solves the overlay by not having a browser. Also the only option that makes real offline editing straightforward. It duplicates the entire product, needs an Xcode project and App Store distribution for a single user, and would leave two editors to keep in step. See ADR 0008, which reaches the same conclusion from the text-entry side.

## Recommendation

Option A now (already implemented), Option B when the mobile layout work has settled and there is appetite for the JS-lifecycle change. Options C and D stay closed for the navigation problem alone.

## Offline, as a separate question

A service worker is what the web platform offers, and it is worth being precise about what it would and would not buy:

- It can cache the app shell (templates' CSS, JS, icons, fingerprinted static assets) so a cold launch with no network paints something instead of failing
- It can cache rendered note pages for read-only access, which is genuinely useful on a phone with no signal
- It can queue a save with Background Sync and replay it when the network returns, which is fine for one edit made offline and dangerous for a session of them

The hard part is editing, and what makes it hard is the data, which caching does nothing for. Notes are files, and Syncthing already owns sync of that vault (ADR 0004 puts attachments in the same tree). An offline web client would become a third writer alongside the server and Syncthing, holding note text in IndexedDB with no view of what the vault did meanwhile. On reconnect it either overwrites whatever arrived (silent data loss) or has to merge, and merging Djot text is a real conflict-resolution problem that the app has never had to solve because the server has always been the single writer.

A native app sidesteps that differently: a sibling app reading and writing the Syncthing vault directly, as sketched in ROADMAP.md's "Workout planner (deferred)", has no separate store to reconcile. It edits the same files Syncthing syncs, and conflicts become Syncthing's `.sync-conflict` files, which is a known and inspectable failure mode rather than a new one.

Nothing is committed here. Adding a read-only service worker (app shell plus cached note pages, no write queue) is the cheap first step whenever offline reading starts to matter, and it can ship without deciding anything about offline editing.

## Consequences

- `manifest.webmanifest` and the icon set are now part of the static assets and must stay served under the app's own origin for scope to apply
- `scope: /` means the whole site is the web app. Adding any route that should open in a browser instead would need an explicit `target="_blank"` or a scope narrowed to a subpath
- The full-resolution media link in `editor.js` is the one known in-app-browser risk left, and needs a device check
- Skipping the service worker means the homescreen app still shows an error page with no network. That is the accepted state for now
- Revisit if offline reading becomes a regular need (add a read-only service worker), if offline editing does (reopen the native-app question with ADR 0008), or if page-transition flicker on mobile becomes annoying enough to justify `hx-boost`
