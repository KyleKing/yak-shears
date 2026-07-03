"""In-process fixed-window login throttle."""

import time
from collections import defaultdict
from threading import Lock

_MAX_ATTEMPTS = 5
_WINDOW_SECONDS = 300.0


class RateLimiter:
    """Fixed-window attempt counter keyed by an arbitrary string."""

    def __init__(self, max_attempts: int = _MAX_ATTEMPTS, window_seconds: float = _WINDOW_SECONDS) -> None:
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds
        self._hits: dict[str, tuple[float, int]] = defaultdict(lambda: (0.0, 0))
        self._lock = Lock()

    def is_blocked(self, key: str) -> bool:
        """Return True when the key has exhausted its attempts within the window."""
        now = time.monotonic()
        with self._lock:
            window_start, count = self._hits[key]
            if now - window_start > self._window_seconds:
                return False
            return count >= self._max_attempts

    def register_failure(self, key: str) -> None:
        """Record a failed attempt, starting a fresh window when the previous one expired."""
        now = time.monotonic()
        with self._lock:
            window_start, count = self._hits[key]
            if now - window_start > self._window_seconds:
                self._hits[key] = (now, 1)
            else:
                self._hits[key] = (window_start, count + 1)

    def reset(self, key: str) -> None:
        """Clear any recorded attempts for the key."""
        with self._lock:
            self._hits.pop(key, None)


login_limiter = RateLimiter()
