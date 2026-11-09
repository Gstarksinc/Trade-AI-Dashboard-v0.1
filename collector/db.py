from psycopg_pool import AsyncConnectionPool

from . import config

INSERT = {
    'candles': (
        'INSERT INTO candles (symbol, timeframe, open_time, open, high, low, close, volume, '
        'quote_volume, trades, taker_buy_base, taker_buy_quote) '
        'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING'),
    'funding_rates': (
        'INSERT INTO funding_rates (symbol, funding_time, funding_rate, mark_price) '
        'VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING'),
    'open_interest': (
        'INSERT INTO open_interest (symbol, ts, period, sum_open_interest, sum_open_interest_val) '
        'VALUES (%s,%s,%s,%s,%s) ON CONFLICT (symbol, period, ts) DO UPDATE SET '
        'sum_open_interest = EXCLUDED.sum_open_interest, sum_open_interest_val = EXCLUDED.sum_open_interest_val'),
    'long_short_ratio': (
        'INSERT INTO long_short_ratio (symbol, ts, period, long_account, short_account, ratio) '
        'VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (symbol, period, ts) DO UPDATE SET '
        'long_account = EXCLUDED.long_account, short_account = EXCLUDED.short_account, ratio = EXCLUDED.ratio'),
    'taker_volume': (
        'INSERT INTO taker_volume (symbol, ts, period, buy_sell_ratio, buy_vol, sell_vol) '
        'VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (symbol, period, ts) DO UPDATE SET '
        'buy_sell_ratio = EXCLUDED.buy_sell_ratio, buy_vol = EXCLUDED.buy_vol, sell_vol = EXCLUDED.sell_vol'),
}

UPSERT_SYMBOL = (
    'INSERT INTO symbols (symbol, base_asset, onboard_date, is_active, updated_at) '
    'VALUES (%s,%s,%s,true,now()) ON CONFLICT (symbol) DO UPDATE SET '
    'base_asset = EXCLUDED.base_asset, onboard_date = EXCLUDED.onboard_date, is_active = true, updated_at = now()')


class DB:
    def __init__(self):
        self.pool = AsyncConnectionPool(config.DATABASE_URL, min_size=1, max_size=4, open=False)

    async def open(self):
        await self.pool.open(wait=True)

    async def close(self):
        await self.pool.close()

    async def insert(self, table, rows):
        if not rows:
            return 0
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.executemany(INSERT[table], rows)
        return len(rows)

    async def scalar(self, sql, params=()):
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, params)
                row = await cur.fetchone()
                return row[0] if row else None

    async def upsert_symbol(self, symbol, base_asset, onboard_ms):
        from .parse import ts
        async with self.pool.connection() as conn:
            await conn.execute(UPSERT_SYMBOL, (symbol, base_asset, ts(onboard_ms) if onboard_ms else None))
