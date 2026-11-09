import argparse
import asyncio
import logging
import time
from datetime import datetime, timezone

import redis.asyncio as aioredis

from . import config
from .backfill import run_backfill
from .binance import Binance
from .db import DB
from .live import Live

log = logging.getLogger('collector')


async def validate_symbols(api, db):
    """Keep only symbols that are tradable USDT perpetuals and record them in the symbols table."""
    info = await api.exchange_info()
    table = {s['symbol']: s for s in info['symbols']}
    valid = []
    for sym in config.SYMBOLS:
        s = table.get(sym)
        if not s or s.get('status') != 'TRADING' or s.get('contractType') != 'PERPETUAL' or s.get('quoteAsset') != 'USDT':
            log.error('dropping %s: not a tradable USDT perpetual', sym)
            continue
        await db.upsert_symbol(sym, s.get('baseAsset'), s.get('onboardDate'))
        valid.append(sym)
    if not valid:
        raise SystemExit('no valid symbols in SYMBOLS')
    config.SYMBOLS[:] = valid
    log.info('collecting %s on %s', ','.join(valid), ','.join(config.TIMEFRAMES))


async def run(args):
    api, db = Binance(), DB()
    await db.open()
    redis = aioredis.from_url(config.REDIS_URL) if config.REDIS_URL else None

    async def beat(field=None, value=None):
        if not redis:
            return
        try:
            await redis.set('collector:heartbeat', datetime.now(timezone.utc).isoformat())
            if field:
                await redis.hset('collector:last_candle', field, value.isoformat())
        except Exception as e:
            log.warning('redis heartbeat failed: %s', e)

    try:
        await validate_symbols(api, db)
        if not args.no_backfill:
            await run_backfill(api, db, beat)
        if args.backfill_only:
            log.info('backfill finished')
            return
        live = Live(api, db, beat)
        jobs = [  # name, interval seconds, coroutine function, last run
            ['candles', 15, live.candles, 0.0],
            ['metrics', 300, live.metrics, 0.0],
            ['funding', 3600, live.funding, 0.0],
            ['gapfill', 3600, lambda: run_backfill(api, db, beat, klines_only=True), time.time()],
        ]
        log.info('live collection started')
        while True:
            now = time.time()
            for job in jobs:
                if now - job[3] >= job[1]:
                    job[3] = now
                    try:
                        await job[2]()
                    except Exception:
                        log.exception('%s job failed', job[0])
            await beat()
            await asyncio.sleep(5)
    finally:
        await api.close()
        await db.close()
        if redis:
            await redis.aclose()


def main():
    parser = argparse.ArgumentParser(description='Binance Futures data collector')
    parser.add_argument('--backfill-only', action='store_true', help='backfill history, then exit')
    parser.add_argument('--no-backfill', action='store_true', help='skip the startup backfill')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    asyncio.run(run(args))


if __name__ == '__main__':
    main()
