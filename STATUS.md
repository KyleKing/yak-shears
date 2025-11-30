# Project Status

Quick overview of what's implemented, in progress, and planned.

## Implemented Features

| Feature | Status | Notes |
|---------|--------|-------|
| User authentication | ✅ | Email/password with sessions |
| Yak listing | ✅ | Pagination, sorting, categories |
| Editor | ✅ | CodeJar with live preview |
| Search | ✅ | DuckDB full-text, fuzzy matching |
| Frontmatter parsing | ✅ | YAML extraction on save |
| Link extraction | ✅ | `[[wikilinks]]` indexed |
| Backlinks storage | ✅ | Stored in DuckDB |
| Responsive design | ✅ | Mobile, tablet, desktop |
| E2E tests | ✅ | 26 Playwright tests |

## In Progress

| Feature | Status | Notes |
|---------|--------|-------|
| Metadata panel | 🔄 | Right sidebar for frontmatter |
| Backlinks UI | 🔄 | Display in metadata panel |

## Planned (Not Started)

| Feature | Phase | Priority |
|---------|-------|----------|
| Link autocomplete | Phase 3 | High |
| Data model validation | Phase 4 | Medium |
| Board/table views | Phase 5 | Medium |
| Graph visualization | Phase 6 | Low |

## Architecture

```
yak_shears/
├── _auth/              # Authentication
│   ├── storage.py      # UserStore class
│   ├── handlers.py     # Login/logout
│   └── middleware.py   # Session middleware
├── _yak/               # Yak management
│   ├── database.py     # DuckDB operations
│   ├── services.py     # Business logic
│   ├── request_utils.py# Request utilities
│   ├── handlers.py     # HTTP handlers
│   └── routes.py       # Route definitions
├── _templates/         # Jinja2 templates
├── static/             # CSS and JS
└── cli.py              # User management CLI
```

## Test Coverage

- Unit tests: `tests/test_*.py`
- E2E tests: `tests/e2e/test_*.py`
- Run: `mise run test`

## Documentation

| Document | Purpose |
|----------|---------|
| AGENTS.md | AI/developer reference |
| DEPLOYMENT.md | Production deployment |
| ROADMAP.md | Vision and phases |
| README.md | Getting started |
