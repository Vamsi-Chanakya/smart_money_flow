"""Rate limiter for API calls."""

import asyncio
import time
from collections import deque
from threading import Lock


class RateLimiter:
    """Simple rate limiter using token bucket algorithm.

    Args:
        calls_per_second: Maximum number of calls allowed per second
    """

    def __init__(self, calls_per_second: int = 10):
        self.calls_per_second = calls_per_second
        self.min_interval = 1.0 / calls_per_second
        self.timestamps: deque = deque(maxlen=calls_per_second)
        self._lock = Lock()

    def wait(self) -> None:
        """Block until a request can be made within rate limits."""
        with self._lock:
            now = time.monotonic()

            if len(self.timestamps) >= self.calls_per_second:
                oldest = self.timestamps[0]
                elapsed = now - oldest

                if elapsed < 1.0:
                    sleep_time = 1.0 - elapsed
                    time.sleep(sleep_time)
                    now = time.monotonic()

            self.timestamps.append(now)

    async def wait_async(self) -> None:
        """Async version of wait."""
        now = time.monotonic()

        if len(self.timestamps) >= self.calls_per_second:
            oldest = self.timestamps[0]
            elapsed = now - oldest

            if elapsed < 1.0:
                sleep_time = 1.0 - elapsed
                await asyncio.sleep(sleep_time)
                now = time.monotonic()

        self.timestamps.append(now)

    def __enter__(self):
        self.wait()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
