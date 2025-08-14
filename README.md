# Yak Shears (py)

Minimal Python implementation of my yak-shears project with the goal of finishing the MVP more quickly

Will eventually be merged with the main branch and may or may not be reimplemented in go

```sh
# General commands

pre-commit install
pre-commit run --all-files
mise run typecheck
mise run format

uv run pytest -v --ff -x

uv run yak-shears-users list
uv run serve --reload
```
