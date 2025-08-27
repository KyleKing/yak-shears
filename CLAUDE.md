# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
- Update Claude memories and Claude.md when making relevant changes
