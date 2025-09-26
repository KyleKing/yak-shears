"""Logging utilities for yak_shears."""

import sys
from typing import TextIO


def log(message: str, *, file: TextIO = sys.stdout) -> None:
    """Log a message to the specified file.

    Args:
        message: The message to log.
        file: The file to write the log message to. Defaults to sys.stdout.
    """
    print(message, file=file)
