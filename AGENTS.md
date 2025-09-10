# AGENTS.md

This file provides guidance to AI agents when working with code in this repository.

## Development Commands

### Package Management

- `uv sync` - Install dependencies
- `uv add <package>` - Add a new dependency
- Do not add new packages without asking and proposing at least two options

### Code Quality

- `mise run format` - Format code with Ruff (fix + format)
- `mise run typecheck` - Run mypy type checking
- `uv run ruff check --fix` - Run Ruff linter with fixes
- `uv run ruff format` - Format code with Ruff
- `uv run mypy` - Type check with mypy

### Testing

- `uv run pytest -v --ff -x` - Run tests with verbose output, fail-fast, exit on first failure
- `uv run pytest --snapshot-update` - Update test snapshots

### Server Development

- `uv run serve --reload` - Start development server with auto-reload and no auth
- `uv run serve --reload --no-auth` - Start development server without auth middleware for faster testing
- `uv run yak-shears-users list` - List all users
- `uv run yak-shears-users create <email>` - Create a new user

### Pre-commit

- `pre-commit install` - Install pre-commit hooks
- `pre-commit run --all-files` - Run all pre-commit hooks

## Architecture Overview

### Web Framework Stack

- **Starlette**: ASGI web framework for routing and request handling
- **Uvicorn**: ASGI server for development and production
- **Jinja2**: Template engine for HTML rendering
- **Alpine.js + Alpine-Ajax**: Frontend interactivity (loaded via CDN)

### Project Structure

```
yak_shears/
├── auth/           # Authentication system (password-based, JSON file storage)
├── file/           # File management (Djot files in ~/Sync/yak-shears)
├── server/         # Main server routes and handlers
├── templates/      # Jinja2 HTML templates
└── cli.py          # User management CLI tool
```

### Authentication System

- Password-based authentication with sessions
- In-memory storage with JSON file persistence (`.yak-shears-users.json`)
- Session middleware protects routes except public paths
- Development mode can skip auth with `--no-auth` flag

### File Management

- Works with Djot files (`.dj` extension) from `~/Sync/yak-shears`
- Supports file listing with pagination and sorting (name/date)
- File editing with content preview and truncation
- Uses pathlib for file operations

### Frontend Approach

- Server-side rendering with Jinja2 templates
- Alpine.js for client-side interactivity
- Minimal CSS approach, under 14KB page size target
- Mobile-first responsive design for iPhone 14, iPad, Desktop

### Configuration

- Python 3.12+ required (configured for 3.13.3 in mise.toml)
- Uses beartype for runtime type checking
- Ruff for linting/formatting with extensive rule configuration
- MyPy for static type checking with strict settings
- Test coverage requirement: 90% minimum

### Key Design Patterns

- TypedDict models for structured data (User, etc.)
- NewType for type safety (Password, HashedPassword, SessionId)
- Starlette route handlers with async/await
- Template rendering helpers in templates/__init__.py
- Centralized error handling with custom error pages

### Development Notes

- Use `uv` for all Python package management
- Run `mise run format ::: typecheck` after making changes
- Tests use pytest with parameterization and snapshot testing
- No comments in code unless explicitly requested
- Prefer server-side Python over client-side JavaScript when possible
- Update AGENTS.md when making relevant changes

## Design Guidelines

### Visual Vibe

- Clean and minimal with whimsical accents
- Font is clean and easy to read on Mobile and Desktop
- Be inspired by this color scheme from Welcome to the Jungle: #f7cf46 (primary accent), #f5f3ef (background), #000000 (text), #ffff (nav), and additional accent colors include #f19d71, #73c1e5, and #e99bc6
- Responsive for iPhone 14, iPad, and Desktop Monitor

### Code Standards

- Use Python 3.13
- Use pytest and liberally use `pytest.parameterize`. Test with `uv run pytest -v --ff`
- Write easy to read code, with no comments, no one letter variables, and follow DRY
- Update docstrings when making changes and check `mise run format ::: typecheck` after making changes
- Do not add dependencies unless absolutely necessary
- Prefer implementing features in server side Python when possible. Use Alpine.js and Alpine-Ajax for interactivity
- Keep CSS minimal and scoped to component. Use default styling whenever possible
- The whole page should not be larger than 14Kb
- Support recent versions of FireFox desktop and Safari mobile browsers

## Component Specifications

### Note Editor

- Indicates spelling and grammar mistakes
- Pasted links are auto-formatted as markdown
- When editing a bulleted or numbered list, there is logic to intelligently indent the current item right or left. On Desktop this is with Tab and Shift+Tab and on mobile, there are buttons added to the keyboard. The indentation is in increments of four spaces, can't be deeper than the parent item, and (TBD - adds a new line above when indenting and removes when out denting)
- When typing enter from a bulleted or numbered list, the next line is automatically started with a continuation with matching indentation
- Supports toggling italic and bold on the selected text. On mobile, the keyboard is extended with buttons to apply bullet or italic to highlighted text

### Note Preview

- Indicates spelling and grammar mistakes
- Renders with djot library (`<script src="https://unpkg.com/@djot/djot@0.2.5/dist/djot.js"></script>` and `djot.renderHTML(djot.parse("- _example_"))`)

### Search

- Inspired by Telescope for nvim
- There is a text input, which is full width
- There is sidebar with is 1/2 width and a note preview
- The search sidebar shows each matched note with an abbreviated preview
- The search preview highlights what was matched during the search
- Search can either be a full page or a modal triggered by a button on the keyboard in mobile or ctrl-p on desktop

## Page Specifications

### Login

- Basic username/password if no valid session credentials were found
- Credentials last for 7 days
- Login goes to last URL before redirect

### View Notes

- URL is `/`
- Preview each note in rectangle with any metadata and any content that will fit
- Rectangles are wrapped with flexbox for responsiveness
- Clicking on a note opens the Note Page

### Note Page

- URL is `/note/<note-title>`
- There is a button to go back to `/`
- On mobile, defaults to Note Editor component full screen. If the screen is wide enough, the preview is shown side-by-side
- There is a button to toggle between Editor and Preview components
- There is a feature to link notes (TBD)
- There is a feature to see similar notes (TBD)
- There is a feature to support configuring note metadata during edit and to view when viewing (TBD)

## Future Features

- Best tiny model for plain text RAG (https://www.baseten.com/blog/the-best-open-source-embedding-models/#the-best-reward-model-allanai-llama-31-tulu-3-8b-reward) or run something slightly better on my laptop? For the latter, would track new and modified files removed from RAG until I can next ingest them from my laptop.
