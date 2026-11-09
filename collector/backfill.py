import asyncio
import logging
import time

from . import config
from .binance import BinanceError
from .parse import METRIC_TABLE, TF_MS, candle_rows, funding_rows, metric_rows

log = logging.getLogger('collector.backfill')
DAY_MS = 86_400_000


def _ms(dt):
    return int(dt.timestamp() * 1000)


async def backfill_klines(api, db, symbol, tf, start_ms):
    """Resumes after the newest stored candle, so it is safe to run repeatedly."""
    step = TF_MS[tf]
    last = await db.scalar('SELECT max(open_time) FROM candles WHERE symbol=%s AND timeframe=%s', (symbol, tf))
    cursor = max(start_ms, _ms(last) + step) if last else start_ms
    total = 0
    while True:
        now_ms = int(time.time() * 1000)
        if cursor >= now_ms:
            break
        raw = await api.klines(symbol, tf, start_ms=cursor, limit=1500)
        if not raw:
            break
        total += await db.insert('candles', candle_rows(symbol, tf, raw, now_ms))
        nxt = int(raw[-1][0]) + step
        if nxt <= cursor or len(raw) < 1500:
            break
        cursor = nxt
        await asyncio.sleep(0.2)
    return total


async def backfill_funding(api, db, symbol, start_ms):
    last = await db.scalar('SELECT max(funding_time) FROM funding_rates WHERE symbol=%s', (symbol,))
    cursor = max(start_ms, _ms(last) + 1) if last else start_ms
    total = 0
    while True:
        raw = await api.funding(symbol, start_ms=cursor, limit=1000)
        if not raw:
            break
        total += await db.insert('funding_rates', funding_rows(symbol, raw))
        nxt = int(raw[-1]['fundingTime']) + 1
        if nxt <= cursor or len(raw) < 1000:
            break
        cursor = nxt
        await asyncio.sleep(0.2)
    return total


async def backfill_metric(api, db, kind, symbol, period):
    """Binance only serves about the last 30 days of these series, so look back 29 days at most."""
    table = METRIC_TABLE[kind]
    now_ms = int(time.time() * 1000)
    floor_ms = now_ms - 29 * DAY_MS
    last = await db.scalar('SELECT max(ts) FROM %s WHERE symbol=%%s AND period=%%s' % table, (symbol, period))
    cursor = max(floor_ms, _ms(last) + 1) if last else floor_ms
    total = 0
    while cursor < now_ms:
        raw = await api.metric(kind, symbol, period, start_ms=cursor, end_ms=now_ms, limit=500)
        if not raw:
            break
        total += await db.insert(table, metric_rows(kind, symbol, period, raw))
        nxt = int(raw[-1]['timestamp']) + 1
        if nxt <= cursor or len(raw) < 500:
            break
        cursor = nxt
        await asyncio.sleep(0.2)
    return total


async def _step(label, coro, beat):
    try:
        n = await coro
        log.info('%s: +%s rows', label, n)
    except BinanceError as e:
        log.error('%s failed: %s', label, e)
    except Exception:
        log.exception('%s failed', label)
    if beat:
        await beat()


async def run_backfill(api, db, beat=None, klines_only=False):
    start_ms = int((time.time() - config.BACKFILL_YEARS * 365 * 86400) * 1000)
    for symbol in list(config.SYMBOLS):
        for tf in config.TIMEFRAMES:
            await _step('klines %s %s' % (symbol, tf), backfill_klines(api, db, symbol, tf, start_ms), beat)
        if klines_only:
            continue
        await _step('funding %s' % symbol, backfill_funding(api, db, symbol, start_ms), beat)
        for kind in METRIC_TABLE:
            for period in config.TIMEFRAMES:
                await _step('%s %s %s' % (kind, symbol, period), backfill_metric(api, db, kind, symbol, period), beat)
