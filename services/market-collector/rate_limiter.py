"""Rate limit budgeter for Binance Futures API.

Binance USD-M Futures imposes a 2400 weight/minute limit (default).
We operate within a conservative budget (e.g. 1200 weight/minute) to guarantee
zero 429 rate limit errors even during backfilling spikes.
"""

import asyncio
import logging
import time

log = logging.getLogger("market-collector.rate-limiter")


class RateLimitBudgeter:
    def __init__(self, max_weight_per_min: int = 1200):
        self.max_weight = max_weight_per_min
        self.current_weight = 0
        self.last_reset = time.time()
        self.lock = asyncio.Lock()
        self.header_reported_weight = 0

    def update_from_headers(self, headers: dict):
        """Update current weight from Binance response headers if present."""
        used = headers.get("x-mbx-used-weight-1m")
        if used is not None:
            try:
                self.header_reported_weight = int(used)
                if self.header_reported_weight > self.current_weight:
                    self.current_weight = self.header_reported_weight
            except (ValueError, TypeError):
                pass

    async def acquire(self, weight: int = 1):
        """Acquire permission to execute a request with given weight. Sleeps if budget is exceeded."""
        async with self.lock:
            now = time.time()
            if now - self.last_reset >= 60.0:
                self.current_weight = 0
                self.last_reset = now

            effective_weight = max(self.current_weight, self.header_reported_weight)
            if effective_weight + weight > self.max_weight:
                sleep_time = max(1.0, 60.0 - (now - self.last_reset))
                log.warning(
                    "Rate limit budget reached (weight=%d/%d). Sleeping %.1fs",
                    effective_weight,
                    self.max_weight,
                    sleep_time,
                )
                await asyncio.sleep(sleep_time)
                self.current_weight = 0
                self.last_reset = time.time()
                self.header_reported_weight = 0

            self.current_weight += weight

    @property
    def used_weight(self) -> int:
        now = time.time()
        if now - self.last_reset >= 60.0:
            return 0
        return max(self.current_weight, self.header_reported_weight)

