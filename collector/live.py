import logging
import time

from . import config
from .parse import METRIC_TABLE, candle_rows, floor_boundary, funding_rows, metric_rows

log = logging.getLogger('collector.live')


class Live:
    """Polls Binance REST for newly closed candles and the latest futures metrics."""

    def __init__(self, api, db, beat):
        self.api, self.db, self.beat = api, db, beat
        self.done = {}  # (symbol, timeframe) -> boundary already stored

    async def candles(self):
        now_ms = int(time.time() * 1000)
        for tf in config.TIMEFRAMES:
            boundary = floor_boundary(now_ms, tf)
            if now_ms - boundary < 5000:  # give the exchange a moment to finalise the candle
                continue
            for symbol in config.SYMBOLS:
                if self.done.get((symbol, tf)) == boundary:
                    continue
                try:
                    raw = await self.api.klines(symbol, tf, limit=3)
                    rows = candle_rows(symbol, tf, raw, now_ms)
                    await self.db.insert('candles', rows)
                    self.done[(symbol, tf)] = boundary
                    if rows:
                        await self.beat('%s:%s' % (symbol, tf), rows[-1][2])
                except Exception as e:
                    log.warning('candle poll failed for %s %s: %s', symbol, tf, e)

    async def metrics(self):
        for symbol in config.SYMBOLS:
            for period in config.TIMEFRAMES:
                for kind, table in METRIC_TABLE.items():
                    try:
                        raw = await self.api.metric(kind, symbol, period, limit=3)
                        await self.db.insert(table, metric_rows(kind, symbol, period, raw))
                    except Exception as e:
                        log.warning('%s poll failed for %s %s: %s', kind, symbol, period, e)

    async def funding(self):
        for symbol in config.SYMBOLS:
            try:
                raw = await self.api.funding(symbol, limit=10)
                await self.db.insert('funding_rates', funding_rows(symbol, raw))
            except Exception as e:
                log.warning('funding poll failed for %s: %s', symbol, e)
