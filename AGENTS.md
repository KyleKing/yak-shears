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
- Supports yak listing with pagination and sorting (name/date)
- Yak editing with content preview

### Frontend Approach

- Server-side rendering with Jinja2 templates
- Responsive design for iPhone 14, iPad, and Desktop
- Keep total assets under 14KB

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
- Keep CSS minimal and scoped to BEM component

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
- On small screens (≤768px width), the preview is shown in a closeable modal instead of side-by-side layout, scrolled to the first match
- PLANNED: support modal-based search without requiring a new page (ctrl-p), which opens in a new tab
- PLANNED: support embeddings as well as fuzzy matches

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

## Future Features

- Best tiny model for plain text RAG (https://www.baseten.com/blog/the-best-open-source-embedding-models/#the-best-reward-model-allanai-llama-31-tulu-3-8b-reward) or run something slightly better on my laptop? For the latter, would track new and modified yaks removed from RAG until I can next ingest them from my laptop.
- Revisit tests to ensure that private features aren't being tested
    - Consider revisiting automatic coverage overlap. See last item, which was too specific at line level when function level would be more useful: https://github.com/KyleKing/yak-shears/commit/ddc8b0c535b79317a13ef5accf32f0aa5018f49b
- Consider adding mutation testing, such as with https://github.com/boxed/mutmut or the more complicated https://github.com/sixty-north/cosmic-ray
