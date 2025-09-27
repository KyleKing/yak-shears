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
├── auth/           # Authentication system (password-based, JSON file storage)
├── file/           # File management
├── server/         # Main server routes and handlers
├── static/         # Static CSS and JS files
├── templates/      # Jinja2 HTML templates
└── cli.py          # CLI Tool for User management
```

### Authentication System

- Password-based authentication stored in-memory by the server
    - Session middleware enforces user authentication
- User persistence in a JSON file (`.yak-shears-users.json`) written to by the CLI and read by the server

### File Management

- Works with Djot files (`.dj` extension) stored in `~/Sync/yak-shears` by default
- Supports file listing with pagination and sorting (name/date)
- File editing with content preview

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

### Note Editor

Now implemented with CodeJar

- Indicates spelling and grammar mistakes
- Pasted links are auto-formatted as markdown
- When editing a bulleted or numbered list, there is logic to intelligently indent the current item right or left. On Desktop this is with Tab and Shift+Tab and on mobile, there are buttons added to the keyboard. The indentation is in increments of four spaces, can't be deeper than the parent item, and (TBD - adds a new line above when indenting and removes when out denting)
- When typing enter from a bulleted or numbered list, the next line is automatically started with a continuation with matching indentation
- Supports toggling italic and bold on the selected text. On mobile, the keyboard is extended with buttons to apply bullet or italic to highlighted text

### Note Preview

TODO: Not yet implemented

- Renders with djot library (`<script src="https://unpkg.com/@djot/djot@0.2.5/dist/djot.js"></script>` and `djot.renderHTML(djot.parse("- _example_"))`)

### Search

TODO: Not yet implemented

- Inspired by Telescope for nvim
- There is a text input, which is full width
- There is sidebar with is 1/2 width and a note preview
- The search sidebar shows each matched note with an abbreviated preview
- The search preview highlights what was matched during the search
- Search can either be a full page or a modal triggered by a button on the keyboard in mobile or ctrl-p on desktop

## Page Specifications

### Login

- Basic username/password
- Credentials last for 7 days

### View Notes

- URL is `/files`
- Preview each note in a flexbox-wrapped layout
- Clicking on a note opens the Note Page

### Note Page

- URL is `/file/<note-title>`
- On mobile, defaults to Note Editor component full screen. If the screen is wide enough, the preview is shown side-by-side
- There is a button to toggle between Editor and Preview components
- There is a feature to link notes (*TBD*)
- There is a feature to see similar notes (*TBD*)
- There is a feature to support configuring note metadata during edit and to view when viewing (*TBD*)

## Future Features

- Best tiny model for plain text RAG (https://www.baseten.com/blog/the-best-open-source-embedding-models/#the-best-reward-model-allanai-llama-31-tulu-3-8b-reward) or run something slightly better on my laptop? For the latter, would track new and modified files removed from RAG until I can next ingest them from my laptop.
- Revisit tests to ensure that private features aren't being tested
    - Consider revisiting automatic coverage overlap. See last item, which was too specific at line level when function level would be more useful: https://github.com/KyleKing/yak-shears/commit/ddc8b0c535b79317a13ef5accf32f0aa5018f49b
- Consider adding mutation testing, such as with https://github.com/boxed/mutmut or the more complicated https://github.com/sixty-north/cosmic-ray
