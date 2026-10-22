"""Guards on assistant usage, so an open demo cannot spend the API credit freely."""

from __future__ import annotations

import hmac
import threading
from collections.abc import Callable
from datetime import date


def code_matches(given: str, expected: str) -> bool:
    """Compare an access code in constant time, ignoring surrounding whitespace."""
    return hmac.compare_digest(given.strip().encode(), expected.strip().encode())


class DailyCounter:
    """Questions asked today across every session of the app process. None means unlimited."""

    def __init__(self, limit: int | None, today: Callable[[], date] = date.today) -> None:
        self.limit = limit
        self._today = today
        self._day = today()
        self._count = 0
        self._lock = threading.Lock()

    def try_acquire(self) -> bool:
        """Count one question if today's limit allows it."""
        with self._lock:
            day = self._today()
            if day != self._day:
                self._day, self._count = day, 0
            if self.limit is not None and self._count >= self.limit:
                return False
            self._count += 1
            return True
