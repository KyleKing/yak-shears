# Project Status

Quick overview of what's implemented and what's next. Last updated: 2026-07-06.

## Current Focus

**Deploy to Hetzner** (PLAN.md Phase 1): fix cloud-config port/branch/ffmpeg issues, relocate the search DB out of the Syncthing folder, then harden auth/sessions.

## Implemented Features

| Feature | Status | Notes |
|---------|--------|-------|
| User authentication | ✅ | Email/password with sessions (in-memory; persistence planned) |
| Yak listing | ✅ | Pagination, sorting, categories, rendered card previews |
| Editor | ✅ | CodeJar with live preview, wrap toggle, list indent rules |
| Search | ✅ | DuckDB word table with fuzzy matching (backend swap planned) |
| Frontmatter parsing | ✅ | YAML fences and Apple Notes export format; read-only panel (ADR 0003) |
| Link extraction | ✅ | `[[wikilinks]]` and `#tags` indexed (duplicate-link bug open) |
| Backlinks storage | ✅ | Stored in DuckDB |
| Media upload | ✅ | Paste/toolbar upload, HEIC/video transcoding, thumbnails, doctor view (ADR 0004) |
| Responsive design | ✅ | Mobile, tablet, desktop |
| E2E tests | ✅ | Playwright coverage of auth, yaks, editor, search, new, media paste path |

## Next Up (see PLAN.md for details)

Priority order (2026-07-06): deploy, then hardening, then product features; infrastructure polish is opportunistic around them.

| Work | Phase | Priority |
|------|-------|----------|
| Hetzner deployment fixes | 1 | Now |
| Session persistence, link dedupe, auth hardening | 2 | High |
| Link autocomplete, cross-link modal, related-notes panel | 3 | High |
| Frontmatter query engine + metadata/text store split | 4 | High |
| Prune queue, streams/backlog views | 5 | High |
| Grouping and network navigation (hubs, local graph, health digest) | 6 | Medium |
| Read-only external references | 7 | Medium |
| Media hardening, ripgrep/FTS backend, semantic CLI, lint | opportunistic | Around product phases |
| Workout planner | deferred | Decision pending |

## Architecture

```
yak_shears/
├── _auth/              # Authentication (storage, handlers, middleware)
├── _yak/               # Yak management (database, services, media, handlers, routes)
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
| DEPLOYMENT.md | Production deployment to Hetzner |
| AGENTS.md | AI/developer command reference |
| adr/ | Decision records (CSS, search, frontmatter, media, hosting) |
| archive/ | Superseded plans and completed-work reports |
| agent-research-platform/ | Unrelated pydantic-ai research sub-project (quarantined; see its README) |
