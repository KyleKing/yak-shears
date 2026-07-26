# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

The primary user is the author, running a personal instance against a Syncthing-synced vault. The secondary audience is a self-hoster who found the project through the README and runs their own instance: they get accounts and an install path, so onboarding, docs, and multi-account behavior have to stay usable for a stranger, but no feature is designed for collaboration between accounts.

Two usage scenes drive design, and they carry different jobs:

- Phone (iPhone 14, often installed to the homescreen): capture and reading. Short bursts, one hand, software keyboard on screen
- Desktop: editing, search, organizing, and anything that involves moving between notes

Connectivity is not assumed. Notes get read and written where the network is flaky, so offline behavior is a product constraint rather than a nice-to-have (currently unmet; see Capabilities and Constraints).

## Product Purpose

Yak Shears is a self-hosted note-taking web app over a folder of Djot files. It exists so notes stay ordinary files the author owns, while the app adds the parts a plain folder cannot give: fast fuzzy search, wiki-style linking with backlinks, frontmatter metadata, and media attachments that live in the vault.

Success is that the app is the pleasant way to work with the vault and never the thing that owns it. Deleting the app leaves the notes intact and usable.

## Positioning

The vault is the source of truth and every derived structure is a query over it, not app-owned state. Files round-trip verbatim. A stream, a backlog, a hub, and a triage bucket are all the same primitive (query and aggregate notes by frontmatter, then render), so nothing becomes a stored list that can drift from the files.

The stance on network navigation is deliberate and contrarian: compute and surface, do not draw. No global force-directed graph. Navigation runs on an explainable related-notes panel, a bounded local graph, and living hub notes whose membership is derived.

Derived data stays out of the synced vault by design, because sync and a live database do not mix (ADR 0010).

## Operating Context

- Notes are `.dj` (Djot) files in `~/Sync/yak-shears` by default, synced between machines with Syncthing
- Filenames are the UTC creation instant (`2026-07-22T14_03_51Z.dj`); listing order is a plain filename compare
- The search index is DuckDB, stored outside the vault at `$XDG_STATE_HOME/yak-shears` (`SEARCH_DB_DIR` overrides), rebuilt lazily on search
- Metadata is YAML frontmatter, plus the Apple Notes export format for imported material. Frontmatter is edited as plain text and rendered read-only (ADR 0003)
- Links are `[[wikilinks]]` and `#tags`, indexed for backlinks
- Deployed to a Hetzner VPS at `https://yak-shears.kyleking.me`; other people run it by self-hosting the same way
- Installed to the iOS homescreen via `manifest.webmanifest` with `display: standalone` (ADR 0009)

## Capabilities and Constraints

Working today: email/password auth with sessions, yak listing with pagination and sorting, a CodeJar editor with live Djot preview and three view modes, fuzzy search over a DuckDB word table, frontmatter parsing, link and backlink extraction, media upload with HEIC/video transcoding and thumbnails, and a `/doctor` integrity report.

Standing constraints:

- Server-rendered Jinja2 over Starlette with HTMX for interactivity. Favor server-side Python over client-side JavaScript when all else is equal
- Total assets stay under 14KB
- 768px is the mobile/desktop split, duplicated in `editor.js`, `search.js`, and `nav.js`
- Interactive targets are at least 44px
- Layout must work on iPhone 14 (390x844), iPad, and desktop
- CSS stays minimal and scoped to BEM components (ADR 0001)

Undecided or unmet:

- No offline support. No service worker exists; read-only shell caching is the identified first step and offline editing is an open decision (ADR 0009)
- Sessions are in-memory; persistence is planned, not built
- The search text backend (ripgrep vs DuckDB FTS) is an open swap
- Embeddings-based search is wanted but unbuilt

Terminology: a note is a "yak". The vault is the folder of `.dj` files.

## Brand Commitments

- Name: Yak Shears
- The project states "Scandinavian minimalism: clean, functional, subtle" as a design principle. Recorded as the author gave it, without expansion
- README voice is dry and self-deprecating: it opens by listing thirty-odd alternatives the reader should probably use instead. Marketing language would be off-key

## Evidence on Hand

- Screenshots of login, yaks, edit, and search at `.github/screenshots/`
- Ten ADRs in `adr/` recording decisions with measurements behind them (notably ADR 0010, where 20 of 20 copies of an open DuckDB file were unreadable)
- `STATUS.md`, `ROADMAP.md`, `PLAN.md`, `DEPLOYMENT.md`, and `DEPLOY_LOG.md` track state and sequencing
- Playwright E2E coverage of auth, yaks, editor, search, new, and the media paste path
- A live deployment at `https://yak-shears.kyleking.me`; MIT licensed

There are no users besides the author, no testimonials, no usage numbers, no pricing, and no company. Future work must not invent any.

## Product Principles

1. File-first. Djot files are the source of truth and round-trip verbatim; the app is replaceable, the vault is not
2. Derived, never stored. Views are queries over frontmatter; anything computed must be rebuildable from the vault, and only user-accepted actions write to files
3. Optional metadata. A note with no frontmatter is a complete note; advanced features are additive
4. Two devices, two jobs. Phone is capture and reading, desktop is editing and navigating; neither is a shrunken version of the other
5. Compute and surface, do not draw. Prefer explainable, bounded, ranked signals over impressive-looking visualizations that cannot be acted on

## Accessibility & Inclusion

No binding standard. Full keyboard operation is wanted where it fits (search already has arrow-key navigation) but is not a requirement, and no WCAG conformance level has been committed to.
