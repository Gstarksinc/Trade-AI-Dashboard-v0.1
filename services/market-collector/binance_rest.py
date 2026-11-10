"""Binance USD-M Futures REST client with jittered backoff and rate limit budgeter."""

import asyncio
import logging
import random
from typing import Any, Dict, List, Optional
import httpx

try:
    from .rate_limiter import RateLimitBudgeter
except (ImportError, ValueError):
    from rate_limiter import RateLimitBudgeter

log = logging.getLogger("market-collector.binance-rest")


class BinanceRestError(Exception):
    pass


class BinanceRestClient:
    def __init__(self, base_url: str = "https://fapi.binance.com", budgeter: Optional[RateLimitBudgeter] = None):
        self.base_url = base_url.rstrip("/")
        self.budgeter = budgeter or RateLimitBudgeter()
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=25.0,
            headers={"User-Agent": "TradeAI-Collector/1.0"},
        )

    async def close(self):
        await self.client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        weight: int = 1,
        retries: int = 5,
    ) -> Any:
        base_delay = 1.0
        for attempt in range(1, retries + 1):
            await self.budgeter.acquire(weight)
            try:
                resp = await self.client.request(method, path, params=params)
                self.budgeter.update_from_headers(dict(resp.headers))

                if resp.status_code == 200:
                    return resp.json()

                if resp.status_code in (418, 429):
                    retry_after = int(resp.headers.get("Retry-After", 10))
                    jitter = random.uniform(0.8, 1.3)
                    wait_sec = max(retry_after, 5) * jitter
                    log.warning("Rate limited (HTTP %s) on %s. Sleeping %.1fs", resp.status_code, path, wait_sec)
                    await asyncio.sleep(wait_sec)
                    continue

                if resp.status_code in (403, 451):
                    raise BinanceRestError(f"IP/Geo blocked (HTTP {resp.status_code}) on {path}")

                if resp.status_code >= 500:
                    jitter = random.uniform(0.7, 1.3)
                    sleep_sec = min(base_delay * (2 ** (attempt - 1)), 60.0) * jitter
                    log.warning("Server error HTTP %d on %s (attempt %d/%d). Retrying in %.1fs", resp.status_code, path, attempt, retries, sleep_sec)
                    await asyncio.sleep(sleep_sec)
                    continue

                raise BinanceRestError(f"HTTP {resp.status_code} on {path}: {resp.text[:200]}")

            except (httpx.NetworkError, httpx.TimeoutException) as exc:
                jitter = random.uniform(0.8, 1.2)
                sleep_sec = min(base_delay * (2 ** (attempt - 1)), 30.0) * jitter
                log.warning("Network failure on %s (%s, attempt %d/%d). Sleeping %.1fs", path, type(exc).__name__, attempt, retries, sleep_sec)
                await asyncio.sleep(sleep_sec)

        raise BinanceRestError(f"Exhausted {retries} retries on {path}")

    async def exchange_info(self) -> Dict[str, Any]:
        return await self._request("GET", "/fapi/v1/exchangeInfo", weight=1)

    async def klines(
        self,
        symbol: str,
        interval: str,
        start_ms: Optional[int] = None,
        end_ms: Optional[int] = None,
        limit: int = 1000,
    ) -> List[List[Any]]:
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        if start_ms is not None:
            params["startTime"] = start_ms
        if end_ms is not None:
            params["endTime"] = end_ms
        # Kline weight is 5 on binance fapi for limit 1000
        return await self._request("GET", "/fapi/v1/klines", params=params, weight=5)

    async def funding_rates(self, symbol: str, start_ms: Optional[int] = None, limit: int = 100) -> List[Dict[str, Any]]:
        params = {"symbol": symbol, "limit": limit}
        if start_ms is not None:
            params["startTime"] = start_ms
        return await self._request("GET", "/fapi/v1/fundingRate", params=params, weight=1)

    async def open_interest_hist(
        self,
        symbol: str,
        period: str = "15m",
        start_ms: Optional[int] = None,
        end_ms: Optional[int] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        params = {"symbol": symbol, "period": period, "limit": limit}
        if start_ms is not None:
            params["startTime"] = start_ms
        if end_ms is not None:
            params["endTime"] = end_ms
        return await self._request("GET", "/futures/data/openInterestHist", params=params, weight=1)

    async def taker_long_short_ratio(
        self,
        symbol: str,
        period: str = "15m",
        start_ms: Optional[int] = None,
        end_ms: Optional[int] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        params = {"symbol": symbol, "period": period, "limit": limit}
        if start_ms is not None:
            params["startTime"] = start_ms
        if end_ms is not None:
            params["endTime"] = end_ms
        return await self._request("GET", "/futures/data/takerlongshortRatio", params=params, weight=1)

