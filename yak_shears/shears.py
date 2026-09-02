"""CLI dispatcher for `shears` subcommands.

Run with:

```sh
uv run shears lsp
```

"""

import argparse


def main() -> None:
    """Entry point registered as the `shears` console script."""
    parser = argparse.ArgumentParser(description="Yak Shears command-line tools", prog="shears")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("lsp", help="Run the shears language server over stdio")

    args = parser.parse_args()

    if args.command == "lsp":
        from yak_shears.lsp.server import server  # ruff: ignore[import-outside-top-level]

        server.start_io()
