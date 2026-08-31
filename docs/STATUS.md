# Project Status

What exists today. Sequenced work lives in [PLAN.md](./PLAN.md) and the vision in [ROADMAP.md](./ROADMAP.md), so this file does not carry a plan of its own. Last updated: 2026-08-30.

## Current Focus

**Deployed to Hetzner** (PLAN.md Phase 1, done 2026-07-22; see [DEPLOY_LOG.md](./DEPLOY_LOG.md) for the run). Live at `https://yak-shears.kyleking.me`.

**Deploys and observability (2026-08-16).** The GitOps timer now deploys only a commit whose CI is green, health-checks the restart, and rolls back to the previous commit if the new one does not answer, notifying ntfy either way. A daily timer exports the journal as JSONL into a send-only Syncthing folder read on the laptop with `tail-jsonl`, which settles [ADR 0007](./adr/0007-observability-strategy.md) as Option E. Push-on-error is the deliberate gap: deploy failures and downtime notify, a 500 does not.

**Typed notes and their benches (2026-08).** `/streams` renders the canal (three reaches, latch and command deck, undo holding the exact inverse of each write), `/habits` the practice bench (schedules, streaks, grace, makeup), `/lists` the reference rack, and `/benches` the hub over all three. Every write goes through `rewrite_frontmatter_field`, so a note round-trips byte for byte. These read frontmatter directly and are what PLAN.md Phase 4 moves onto the query engine.

**Visual redesign (2026-07-26), merged.** The Scandinavian-minimal look was replaced with a console-panel world recorded in [DESIGN.md](./DESIGN.md), which also carries what the redesign has not reached: the patchbay, `/new`, login, and error pages, and the unverified phone and dark-mode passes.

**Mobile round (2026-07-22)**, driven by a batch of iPhone 14 bug reports: responsive layout and header menu, the search modal, an editor accessory toolbar above the software keyboard, drag-and-drop upload, the PWA manifest, a timezone-stable filename format, and the first pass of search performance work. Two ADRs came out of it, [0008](./adr/0008-mobile-text-entry-affordances.md) on iOS text entry and [0009](./adr/0009-ios-homescreen-app-and-offline.md) on the homescreen app and offline. Next: harden auth/sessions (Phase 2), and verify the mobile fixes on the device.

## Implemented Features

| Feature | Status | Notes |
|---------|--------|-------|
| User authentication | ✅ | Email/password with sessions (in-memory; persistence planned) |
| Yak listing | ✅ | Pagination, sorting, categories, rendered card previews |
| Editor | ✅ | CodeJar with live preview, wrap toggle, list indent rules, mobile keyboard toolbar (ADR 0008) |
| Search | ✅ | DuckDB word table with fuzzy matching (backend swap planned); reused connection, prefix prefilter, stage timing logs |
| Frontmatter parsing | ✅ | YAML fences and Apple Notes export format; read-only panel (ADR 0003) |
| Link extraction | ✅ | `[[wikilinks]]` and `#tags` indexed (duplicate-link bug open) |
| Backlinks storage | ✅ | Stored in DuckDB |
| Doctor | ✅ | Attachment integrity, filename migration, search index location (ADR 0010) |
| Media upload | ✅ | Paste/toolbar/drag-drop upload, HEIC/video transcoding, thumbnails, doctor view (ADR 0004) |
| Responsive design | ✅ | Mobile, tablet, desktop; iPhone 14 pass 2026-07-22 (header menu, search modal, editor sizing) |
| Console design system | 🚧 | DESIGN.md written; yaks, editor, search, and doctor rebuilt. `/new`, login, and error pages still inherit tokens without the world |
| Homescreen web app | ✅ | `manifest.webmanifest` with `display: standalone`, icons, apple meta tags (ADR 0009) |
| Offline support | ❌ | No service worker. Read-only shell caching is the cheap first step; offline editing is undecided (ADR 0009) |
| Streams canal | ✅ | `/streams`: backlog, queue, in progress; latch plus command deck; undo carries the inverse action |
| Habits bench | ✅ | `/habits`: schedules, heat rows, streaks with earned grace and makeup days |
| Lists rack | ✅ | `/lists`: reference checklists with in-place toggles |
| Benches hub | ✅ | `/benches`: one nav entry over every kind-specific surface, with live counts |
| E2E tests | ✅ | Playwright coverage of auth, yaks, editor, search, new, media paste path |

## Architecture

```
yak_shears/
├── _auth/              # Authentication (storage, handlers, middleware)
├── _yak/               # Yak management (database, services, media, handlers, routes)
│                       # plus the benches: board, streams, habits, lists, benches
├── _templates/         # Jinja2 templates
├── frontmatter.py      # Frontmatter parsing (YAML + Apple Notes export format)
├── links.py            # Wikilink/tag extraction
├── server/             # App factories and startup
├── static/             # CSS and JS (editor.js, main.css)
└── cli.py              # User management CLI
```

## Documentation Map

| Document | Purpose |
|----------|---------|
| PLAN.md | Phased implementation plan (the single source for "what's next") |
| ROADMAP.md | Vision, principles, future ideas |
| DEPLOYMENT.md | Production deployment to Hetzner (evergreen how-to) |
| DEPLOY_LOG.md | Narrative record of the actual first deployment, issues hit and fixes |
| AGENTS.md | AI/developer command reference |
| DESIGN.md | The console design system, its glossary, and what the redesign has not reached |
| STREAMS-DESIGN.md | The canal: data model, command grammar, and what Phase 4 must provide |
| ASSETS.md | What ships to the browser and what it costs |
| adr/ | Decision records (CSS, search, frontmatter, media, hosting, SSR/HTMX, observability, mobile text entry, homescreen app) |
| archive/ | Superseded plans and completed-work reports |
| agent-research-platform/ | Unrelated pydantic-ai research sub-project (quarantined; see its README) |
