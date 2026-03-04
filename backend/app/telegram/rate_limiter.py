import time
from collections import defaultdict


class RateLimiter:
    def __init__(self, max_requests: int = 20, window_seconds: int = 60):
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._requests: dict[int, list[float]] = defaultdict(list)

    def _cleanup(self, chat_id: int) -> None:
        now = time.monotonic()
        cutoff = now - self._window_seconds
        self._requests[chat_id] = [
            t for t in self._requests[chat_id] if t > cutoff
        ]

    def is_allowed(self, chat_id: int) -> bool:
        self._cleanup(chat_id)
        if len(self._requests[chat_id]) >= self._max_requests:
            return False
        self._requests[chat_id].append(time.monotonic())
        return True

    def remaining(self, chat_id: int) -> int:
        self._cleanup(chat_id)
        return max(0, self._max_requests - len(self._requests[chat_id]))
