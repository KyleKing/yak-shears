# Yak Shears (py)

Minimal Python implementation of my yak-shears project with the goal of finishing the MVP more quickly

Will eventually be merged with the main branch and may or may not be re-implemented in go

```sh
# Initial Setup
brew install mise pre-commit uv
pre-commit install
uv sync

# Formatting
pre-commit run --all-files
mise run format ::: typecheck

# Testing
uv run pytest -v --ff -x
uv run pytest --snapshot-update
uv run ptw .

# Local Development
uv run yak-shears-users list
uv run serve --reload
```
