"""Logging utilities for yak_shears."""

import sys
import time
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TextIO


def log(message: str, *, file: TextIO | None = None) -> None:
    """Log a message to the specified file.

    Args:
        message: The message to log.
        file: The file to write the log message to. Defaults to the current `sys.stdout`,
            resolved per call so a redirected stdout is honoured.
    """
    print(message, file=file or sys.stdout, flush=True)


@dataclass
class StageTimer:
    """Collect wall-clock durations for named stages of a single request.

    Stages are reported in the order they finish. Not thread-safe; use one
    timer per request.
    """

    started_at: float = field(default_factory=time.perf_counter)
    durations_ms: dict[str, float] = field(default_factory=dict)

    @contextmanager
    def stage(self, name: str) -> Generator[None, None, None]:
        """Time a block and record it under `name`."""
        start = time.perf_counter()
        try:
            yield
        finally:
            self.durations_ms[name] = (time.perf_counter() - start) * 1000

    def format_line(self, label: str, **fields: object) -> str:
        """Render one structured log line: `LABEL key=value ... stage_ms=... total_ms=...`."""
        total_ms = (time.perf_counter() - self.started_at) * 1000
        parts = [label]
        parts.extend(f"{key}={value}" for key, value in fields.items())
        parts.extend(f"{name}_ms={duration:.1f}" for name, duration in self.durations_ms.items())
        parts.append(f"total_ms={total_ms:.1f}")
        return " ".join(parts)
