"""Simple in-memory sliding-window rate limiter per user."""
from __future__ import annotations

import time
from collections import defaultdict, deque


class RateLimiter:
    """Allow up to `max_calls` events per `window_seconds` per user_id."""

    def __init__(self, max_calls: int = 5, window_seconds: float = 10.0):
        self._max = max_calls
        self._window = window_seconds
        self._events: dict[int, deque[float]] = defaultdict(deque)

    def allow(self, user_id: int) -> bool:
        now = time.monotonic()
        q = self._events[user_id]
        while q and now - q[0] > self._window:
            q.popleft()
        if len(q) >= self._max:
            return False
        q.append(now)
        return True
