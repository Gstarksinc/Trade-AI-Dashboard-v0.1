import asyncio
import os
import time
import unittest

os.environ.setdefault('DATABASE_URL', 'postgresql://unused')

from collector.backfill import backfill_klines  # noqa: E402
from collector.parse import TF_MS, candle_rows, floor_boundary, funding_rows, metric_rows  # noqa: E402


def kline(open_ms, tf):
    close_ms = open_ms + TF_MS[tf] - 1
    return [open_ms, '1.0', '2.0', '0.5', '1.5', '10', close_ms, '15', 7, '4', '6', '0']


class ParseTests(unittest.TestCase):
    def test_forming_candle_is_skipped(self):
        now = 10 * TF_MS['1h'] + 1000
        raw = [kline(8 * TF_MS['1h'], '1h'), kline(9 * TF_MS['1h'], '1h'), kline(10 * TF_MS['1h'], '1h')]
        rows = candle_rows('BTCUSDT', '1h', raw, now)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][:2], ('BTCUSDT', '1h'))
        self.assertEqual(rows[0][9], 7)

    def test_floor_boundary_4h_is_utc_aligned(self):
        self.assertEqual(floor_boundary(5 * 3_600_000 + 123, '4h'), 4 * 3_600_000)

    def test_funding_handles_empty_mark_price(self):
        rows = funding_rows('BTCUSDT', [{'fundingTime': 1700000000000, 'fundingRate': '0.0001', 'markPrice': ''}])
        self.assertEqual(rows[0][2], 0.0001)
        self.assertIsNone(rows[0][3])

    def test_metric_rows(self):
        raw = [{'timestamp': 1700000000000, 'sumOpenInterest': '5', 'sumOpenInterestValue': '9'}]
        self.assertEqual(metric_rows('oi', 'BTCUSDT', '1h', raw)[0][2:], ('1h', 5.0, 9.0))


class FakeDB:
    def __init__(self):
        self.rows = []

    async def scalar(self, sql, params=()):
        return None

    async def insert(self, table, rows):
        self.rows.extend(rows)
        return len(rows)


class FakeAPI:
    def __init__(self, tf, first_ms, count):
        step = TF_MS[tf]
        self.data = [kline(first_ms + i * step, tf) for i in range(count)]
        self.calls = 0

    async def klines(self, symbol, tf, start_ms=None, limit=1500):
        self.calls += 1
        return [k for k in self.data if start_ms is None or k[0] >= start_ms][:limit]


class BackfillTests(unittest.TestCase):
    def test_paginates_and_skips_forming_candle(self):
        tf, step = '1h', TF_MS['1h']
        now_ms = int(time.time() * 1000)
        current = floor_boundary(now_ms, tf)
        closed = 3200
        first = current - closed * step
        api = FakeAPI(tf, first, closed + 1)  # includes the forming candle
        db = FakeDB()
        total = asyncio.run(backfill_klines(api, db, 'BTCUSDT', tf, first))
        self.assertEqual(total, closed)
        self.assertEqual(len({r[2] for r in db.rows}), closed)
        self.assertGreaterEqual(api.calls, 3)


if __name__ == '__main__':
    unittest.main()
