"""Tiny in-memory sliding-window limiter (per process; fine for a single-instance demo)."""

import time
from collections import defaultdict, deque


class SlidingWindow:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, limit: int, window_s: float = 3600.0) -> bool:
        now = time.monotonic()
        q = self._hits[key]
        while q and now - q[0] > window_s:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        return True

    def reset(self) -> None:
        self._hits.clear()


explain_limiter = SlidingWindow()
report_limiter = SlidingWindow()
