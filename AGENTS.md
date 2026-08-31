# AGENTS.md

This file provides guidance to AI agents when working with code in this repository.

## Development Commands

### General

- `mise --help` - information about mise for task and system dependency management
    - `mise task` - list all mise tasks
- `uv --help` - information about uv for package management
- `git` - use git for history, but never commit

### Package Management

- `uv sync` - Install dependencies
- `uv add <package>` - Add a new dependency
    - Do not add new packages without asking and proposing at least two options

### Code Quality

- `mise run format` - Format code with multiple tools
- `mise run typecheck` - Run mypy type checking
- `hk run pre-commit --all` - run hk against all files and not just incrementally with git

### Testing

- `ptw .` - Run tests on file changes
- `mise run test` - Run all tests with coverage and performance reports
- `mise run test:e2e` - Run only Playwright tests
- `mise run test:unit` - Run non-Playwright tests
- `mise run test --snapshot-update` - Run all tests and update test snapshots

### Server Development

- `uv run serve` - Start production server
- `mise run dev` - Start development server with auto-reload and no auth
- `uv run yak-shears-users list` - List all users
- `uv run yak-shears-users create <email>` - Create a new user (AI should never run this. Use the test user below instead)
    - Note: the default test user has email: `test@example.com` and password `secure123`

## Architecture Overview

### Web Framework Stack

- **Starlette**: Minimal ASGI web framework for routing and request handling
- **Uvicorn**: ASGI server for development and production
- **Jinja2**: Template engine for HTML rendering
- **HTMX**: Frontend interactivity

### Project Structure

```
yak_shears/
├── _auth/              # Authentication system
│   ├── storage.py      # UserStore class for user/session management
│   ├── handlers.py     # Auth HTTP handlers (login, logout)
│   └── middleware.py   # Session middleware
├── _yak/               # Yak management
│   ├── database.py     # DuckDB operations for search index
│   ├── services.py     # Business logic (CRUD, search, pagination)
│   ├── request_utils.py# Request utilities (path extraction, HTMX detection)
│   ├── handlers.py     # HTTP request handlers
│   └── routes.py       # Route definitions
├── _templates/         # Jinja2 HTML templates
├── static/             # Static CSS and JS files
└── cli.py              # CLI Tool for User management
```

### Authentication System

- UserStore class manages users and sessions with JSON file persistence
- Password-based authentication with PBKDF2 hashing
- Session middleware enforces user authentication
- User persistence in a JSON file (`.yak-shears-users.json`)

### Yak Management

- Works with Djot yaks (`.dj` extension) stored in `~/Sync/yak-shears` by default
- Yaks are named after their creation instant in UTC: `2026-07-22T14_03_51Z.dj` (`filenames.CANONICAL_FORMAT`). Keep every writer going through `canonical_stem()`, because the listing sort is a plain filename compare and a second naming shape breaks it
- The search index lives outside the vault (`$XDG_STATE_HOME/yak-shears`, or `SEARCH_DB_DIR`). Never default it back inside: DuckDB holds a `.wal` while open and a synced copy is unreadable (ADR 0010)
- Supports yak listing with pagination and sorting (name/date)
- Yak editing with content preview

### Frontend Approach

- **Read [DESIGN.md](./docs/DESIGN.md) before changing anything visual.** The interface is a console panel: three materials (panel face, milled well, engraved groove) build every component, amber is the only lit color and means armed, state is reported by indicator lamps, and category color owns whole rows. New components are composed from those materials rather than styled ad hoc
- Server-side rendering with Jinja2 templates
- Responsive design for iPhone 14 (390x844), iPad, and Desktop
- Installable as a homescreen web app via `static/manifest.webmanifest` (`display: standalone`). Without it, iOS opens every navigation in an in-app browser overlay (ADR 0009)
- Keep total assets under 14KB

#### Mobile layout rules

The 768px breakpoint is the mobile/desktop split and is duplicated in `editor.js`, `search.js`, and `nav.js` as `MOBILE_BREAKPOINT`. Changing it means changing all four.

- Below 768px the header collapses to a hamburger and the wordmark is hidden, otherwise the four nav labels overflow the viewport
- The header menu and the `/yaks` sort/filter rows are `<details>` elements that ship **open** and are closed by `nav.js` on phones. Do not invert this: a closed `<details>` hides its body with `content-visibility` on `::details-content`, which author CSS cannot force back open, and the content becomes unclickable
- `--header-height`, `--action-bar-height`, `--tap-target`, `--keyboard-inset`, and the `--safe-*` insets are defined in `:root`. Fixed bars offset themselves with these rather than hardcoding pixels
- Use `dvh`, not `vh`, for full-height panels. iOS Safari's `100vh` assumes a hidden URL bar and runs content off-screen
- Interactive targets are at least `var(--tap-target)` (44px)
- Watch specificity when overriding view modes: `.editor-container.sidebyside form` outranks `.editor-container form`, which is why the split view stayed half-width on phones

### Key Design Patterns

- TypedDict models for structured data (User, etc.)
- "Opaque types" for special strings (Password, HashedPassword, SessionId)
- Starlette route handlers with async/await
- Template rendering helpers in `yak_shears/templates/__init__.py`
- Centralized error handling with custom error pages

### Code Standards

- Keep `AGENTS.md` up to date
- Run `mise run format ::: typecheck ::: test` after making changes
- Liberally use `pytest.mark.parametrize` when writing tests
    - Write the fewest number of tests to avoid coverage overlap
    - Always test at the consumer level on the public interface
    - Avoid mocking and spying whenever possible
    - See example of these practices in `tests/test_cli.py`
- Favor server-side Python over client-side HTMX and JavaScript when all else equal
- Write easy to read code, *no one letter variables*, and follow YAGNI and DRY
- Update docstrings when making changes
- Keep CSS minimal and scoped to BEM component, and keep literal values on the DESIGN.md ramps (type sizes, radii, palette). A one-off literal is either drift or a system addition that belongs in DESIGN.md

## Component Specifications

### Yak Editor

Now implemented with CodeJar

- Indicates spelling and grammar mistakes
- Pasted links are auto-formatted as markdown
- When editing a bulleted or numbered list, there is logic to intelligently indent the current item right or left. On Desktop this is with Tab and Shift+Tab and on mobile, there are buttons added to the keyboard. The indentation is in increments of four spaces, can't be deeper than the parent item, and (TBD - adds a new line above when indenting and removes when out denting)
- When typing enter from a bulleted or numbered list, the next line is automatically started with a continuation with matching indentation
- Supports toggling italic and bold on the selected text. On mobile, the keyboard is extended with buttons to apply bullet or italic to highlighted text
- Toggle between three view modes: Editor-only, Side-by-side (editor and preview), and Preview-only
- Preview includes syntax highlighting for code blocks using Prism.js v1.29.0, with language detection from Djot AST "lang" attribute
- Word wrap defaults on at every width. Turning it off is remembered in localStorage and persists across pages until switched back on
- Dropped and pasted images and videos are uploaded through `/media/upload` and replaced with a Djot snippet. The `drop` handler must always `preventDefault()`, or the browser inserts a full-size data-URL `<img>` into the contenteditable and the note becomes uneditable
- On phones an accessory toolbar (`.editor-toolbar`) rides above the software keyboard with indent, outdent, bullet, checklist, bold, and italic. `editor.js` writes `--keyboard-inset` from `visualViewport`; its buttons must `preventDefault()` on pointerdown so tapping one does not dismiss the keyboard. iOS gives web content no way to extend the system keyboard itself (ADR 0008)

Prism's stock theme is loaded from a CDN *after* `main.css` and hardcodes black text with a white halo, which is unreadable on the dark surface. `main.css` overrides it under `.editor` and `.preview-content` with scheme-aware token variables; those selectors need a class ancestor to outrank it.

### Note Preview

- Renders with djot library (`djot.renderHTML(djot.parse("<content>"))`)
- Includes syntax highlighting for code blocks using Prism.js v1.29.0 with language detection from Djot AST "lang" attribute

### Search

Implemented as a full page at /search with fuzzy search using persistent and lazily updated DuckDB database.

- Database layer in `_yak/database.py` centralizes all DuckDB operations
- Uses DuckDB levenshtein distance for fuzzy matching
- Persistent database (`yak_shears_search.db`) stores indexed words from all yak files and updated lazily on search
    - Lazy updates: only re-indexes when files change and not more than once per minute
- Also stores frontmatter metadata and yak links for backlink queries
- UI is inspired by Telescope for nvim
    - There is a text input, which is full width
    - There is sidebar which is 40% of the browser width. The other 60% is a Yak preview window, which shows a preview of the currently selected Yak
    - The search sidebar shows each matched yak with a single, unwrapped line of preview text in the space available
    - The search preview shows highlighted text for what was matched during the search
- Keyboard navigation: Use arrow keys to navigate results, Enter to open the currently selected yak
- On small screens (≤768px width), the preview is shown in a closeable modal instead of side-by-side layout, scrolled to the first match. The modal is a three-part column: a header bar with a labelled Close button, a scrolling body, and an "Open" bar pinned to the bottom so the way into the editor is always on screen
- PLANNED: support modal-based search without requiring a new page (ctrl-p), which opens in a new tab
- PLANNED: support embeddings as well as fuzzy matches

### Doctor

A read-mostly integrity report at `/doctor`, covering attachments, filenames, and the search index.

- Attachments: `/media/...` references with no file on disk, and attachment files no note references
- Filenames: yaks whose name is a timestamp in a superseded format, with the canonical replacement. `POST /doctor/fix-filenames` renames them all, rewrites wikilinks that named the old stems, and forces an index rebuild because renames do not change mtimes and would otherwise slip past the staleness guard
- Names that are not a timestamp in any known format are listed and never renamed. A hand-written filename is a choice, not a defect
- A rename that would collide with an existing name is reported instead of resolved
- Search index: where it resolved to, a warning when that is inside the synced vault, and any stray copy left by the old default

## Page Specifications

### Login

- Basic username/password
- Credentials last for 7 days

### View Yaks

- URL is `/yaks`
- Preview each yak in a flexbox-wrapped layout
- Clicking on a yak opens the Yak Page

### Yak Page

- URL is `/yak?yak=<yak-path>` (PLANNED: this is currently `/edit?yak=...`)
- Toggle buttons to switch between Editor-only, Side-by-side (editor and preview), and Preview-only modes
- On mobile, defaults to Editor-only mode. On desktop, defaults to Side-by-side mode
- There is a feature to link yaks (*TBD*)
- There is a feature to see similar yaks (*TBD*)
- There is a feature to support configuring yak metadata during edit and to view when viewing (*TBD*)

## Related Documentation

- **[STATUS.md](docs/STATUS.md)** - Current implementation status
- **[PLAN.md](docs/PLAN.md)** - Phased plan, the single source for what is next
- **[ROADMAP.md](docs/ROADMAP.md)** - Vision and planned features
- **[DESIGN.md](docs/DESIGN.md)** - The console design system and its glossary
- **[DEPLOYMENT.md](docs/DEPLOYMENT.md)** - Production deployment guide
