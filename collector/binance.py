import asyncio
import logging

import httpx

from . import config

log = logging.getLogger('collector.binance')

METRIC_PATH = {
    'oi': '/futures/data/openInterestHist',
    'lsr': '/futures/data/globalLongShortAccountRatio',
    'taker': '/futures/data/takerlongshortRatio',
}


class BinanceError(Exception):
    pass


class Binance:
    """Minimal public Binance USD-M Futures client. No API key is needed or used."""

    def __init__(self):
        self.client = httpx.AsyncClient(
            base_url=config.BINANCE_FAPI_URL, timeout=20,
            headers={'User-Agent': 'trade-ai-dashboard/0.1'})

    async def close(self):
        await self.client.aclose()

    async def get(self, path, params=None, retries=5):
        delay = 2
        for _ in range(retries):
            try:
                r = await self.client.get(path, params=params)
            except httpx.HTTPError as e:
                log.warning('network error on %s: %s', path, type(e).__name__)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)
                continue
            if r.status_code == 200:
                if int(r.headers.get('x-mbx-used-weight-1m', 0) or 0) > 1800:
                    log.info('request weight is high, pausing 30s')
                    await asyncio.sleep(30)
                return r.json()
            if r.status_code in (418, 429):
                wait = max(int(r.headers.get('Retry-After', delay) or delay), delay)
                log.warning('rate limited (HTTP %s), sleeping %ss', r.status_code, wait)
                await asyncio.sleep(wait)
                delay = min(delay * 2, 120)
                continue
            if r.status_code in (403, 451):
                raise BinanceError('HTTP %s from Binance: region or IP is blocked' % r.status_code)
            if r.status_code >= 500:
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)
                continue
            raise BinanceError('HTTP %s on %s: %s' % (r.status_code, path, r.text[:200]))
        raise BinanceError('gave up on %s after %s attempts' % (path, retries))

    async def exchange_info(self):
        return await self.get('/fapi/v1/exchangeInfo')

    async def klines(self, symbol, tf, start_ms=None, limit=1500):
        p = {'symbol': symbol, 'interval': tf, 'limit': limit}
        if start_ms is not None:
            p['startTime'] = start_ms
        return await self.get('/fapi/v1/klines', p)

    async def funding(self, symbol, start_ms=None, limit=1000):
        p = {'symbol': symbol, 'limit': limit}
        if start_ms is not None:
            p['startTime'] = start_ms
        return await self.get('/fapi/v1/fundingRate', p)

    async def metric(self, kind, symbol, period, start_ms=None, end_ms=None, limit=500):
        p = {'symbol': symbol, 'period': period, 'limit': limit}
        if start_ms is not None:
            p['startTime'] = start_ms
        if end_ms is not None:
            p['endTime'] = end_ms
        return await self.get(METRIC_PATH[kind], p)
