# 0006: Server-Side Rendering with HTMX

## Status

Accepted. Restates a decision originally recorded for the Deno-era prototype (Vento + HTMX, pre-Python rewrite) so the rationale survives in this repo; the stack changed, the architecture did not.

## Context

The app needs fast initial loads and moderate interactivity (editor, search, metadata panel) for a single user. The options considered when the architecture was first chosen: a full client-side SPA (React/Vue), traditional SSR with a templating engine, hybrid SSR with a lightweight client-side layer, or static site generation. A SPA adds a build pipeline, client-side routing, and state management that one person must maintain; SSG cannot serve authenticated, frequently-edited content.

## Decision

Hybrid SSR: the server renders full HTML pages (originally Vento on Deno, now Jinja on Starlette), and HTMX provides declarative AJAX for dynamic actions (save, delete, search) via `hx-*` attributes. Page-specific behavior that HTMX cannot express (the CodeJar editor, combobox, preview rendering) is vanilla JS modules served from `static/js/` with no bundler.

## Rationale

- First paint is a single HTML response; no hydration or client routing
- HTMX keeps interaction logic in templates next to the markup it affects
- No JS build step: modules are edited and served as-is (fingerprinted for caching)
- Plays well with a strict CSP; dynamic values are injected via `htmx:configRequest` listeners instead of `hx-vals="js:..."`, which would require `unsafe-eval`

## Consequences

- Interactivity beyond HTMX's model must be hand-written vanilla JS (accepted for the editor; the largest module, `editor.js`, stays under ~1k lines)
- Server templates are the single source of markup; snapshot tests (`test_server.py`) cover rendered HTML
- New dynamic features should reach for `hx-*` attributes first and custom JS second
