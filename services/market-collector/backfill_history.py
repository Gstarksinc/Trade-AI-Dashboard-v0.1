"""Comprehensive 3+ Year Historical Backfill for 8 Binance USD-M Perpetuals.

Fetches 1h and 4h klines (1500 rows/request, rate-limit aware, deduplicated)
and full funding rate history into TimescaleDB. Generates a gap report
and prints exact row counts and date ranges per symbol/timeframe.
"""

import asyncio
from datetime import datetime, timezone, timedelta
import logging
from typing import Dict, List, Optional, Tuple
import httpx
from sqlalchemy import text

from libs.database.connection import engine
try:
    from .binance_rest import BinanceRestClient
    from .rate_limiter import RateLimitBudgeter
    from .gap_detector import parse_kline_row
    from .storage import MarketDataStorage
except (ImportError, ValueError):
    from binance_rest import BinanceRestClient
    from rate_limiter import RateLimitBudgeter
    from gap_detector import parse_kline_row
    from storage import MarketDataStorage

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("market-collector.backfill")

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT", "LINKUSDT", "TRXUSDT"]
TIMEFRAMES = ["1h", "4h"]
TF_MS = {
    "1h": 60 * 60 * 1000,
    "4h": 4 * 60 * 60 * 1000,
}

# 3+ years ago from current date (2021-01-01 UTC)
START_MS_3Y = int(datetime(2021, 1, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)


async def backfill_klines_for_symbol(
    client: BinanceRestClient,
    symbol: str,
    timeframe: str,
    start_ms: int,
) -> int:
    """Paginates Binance USD-M REST klines with limit=1500 until now."""
    tf_ms = TF_MS[timeframe]
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    
    # Check earliest and latest existing candle in DB to optimize resume
    query = text("""
        SELECT MIN(open_time), MAX(open_time) FROM market_data.candles
        WHERE symbol = :symbol AND timeframe = :timeframe;
    """)
    async with engine.connect() as conn:
        res = await conn.execute(query, {"symbol": symbol, "timeframe": timeframe})
        row = res.fetchone()
        min_dt, max_dt = row[0], row[1]

    curr_start = start_ms
    total_saved = 0
    consecutive_empty = 0

    log.info("Backfilling %s %s from %s to present...", symbol, timeframe, datetime.fromtimestamp(curr_start/1000, tz=timezone.utc))

    while curr_start < now_ms:
        try:
            params = {
                "symbol": symbol,
                "interval": timeframe,
                "startTime": curr_start,
                "limit": 1500,
            }
            raw = await client._request("GET", "/fapi/v1/klines", params=params, weight=5)
            if not raw or not isinstance(raw, list):
                consecutive_empty += 1
                if consecutive_empty > 2:
                    break
                curr_start += tf_ms * 1500
                continue

            consecutive_empty = 0
            # Exclude current unclosed candle
            closed = [k for k in raw if k[6] < now_ms]
            if not closed:
                break

            parsed = [parse_kline_row(symbol, timeframe, k) for k in closed]
            await MarketDataStorage.insert_candles(parsed)
            total_saved += len(parsed)

            last_open = closed[-1][0]
            curr_start = last_open + tf_ms

            if len(raw) < 1500:
                # Reached present
                break

        except Exception as e:
            log.warning("Kline error for %s %s at %s: %s", symbol, timeframe, curr_start, e)
            await asyncio.sleep(2.0)
            curr_start += tf_ms * 1500

    log.info("Finished klines for %s %s: +%d bars", symbol, timeframe, total_saved)
    return total_saved


async def backfill_funding_rates_for_symbol(
    client: BinanceRestClient,
    symbol: str,
    start_ms: int,
) -> int:
    """Paginates Binance USD-M funding rates from 3+ years ago with limit=1000."""
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    curr_start = start_ms
    total_funding = 0

    log.info("Backfilling funding rates for %s...", symbol)
    while curr_start < now_ms:
        try:
            params = {
                "symbol": symbol,
                "startTime": curr_start,
                "limit": 1000,
            }
            raw = await client._request("GET", "/fapi/v1/fundingRate", params=params, weight=1)
            if not raw or not isinstance(raw, list):
                break

            rates = []
            for r in raw:
                rates.append({
                    "symbol": symbol,
                    "funding_time": datetime.fromtimestamp(int(r["fundingTime"]) / 1000.0, tz=timezone.utc),
                    "funding_rate": float(r["fundingRate"]),
                    "mark_price": float(r.get("markPrice", 0.0)),
                })

            if not rates:
                break

            query = text("""
                INSERT INTO market_data.funding_rates (symbol, funding_time, funding_rate, mark_price)
                VALUES (:symbol, :funding_time, :funding_rate, :mark_price)
                ON CONFLICT (symbol, funding_time) DO UPDATE SET
                    funding_rate = EXCLUDED.funding_rate,
                    mark_price = EXCLUDED.mark_price;
            """)
            async with engine.begin() as conn:
                await conn.execute(query, rates)

            total_funding += len(rates)
            last_time = int(raw[-1]["fundingTime"])
            curr_start = last_time + 1

            if len(raw) < 1000:
                break

        except Exception as e:
            log.warning("Funding error for %s at %s: %s", symbol, curr_start, e)
            await asyncio.sleep(2.0)
            curr_start += 8 * 3600 * 1000 * 500

    log.info("Finished funding rates for %s: +%d records", symbol, total_funding)
    return total_funding


async def generate_gap_report(symbol: str, timeframe: str) -> Dict[str, any]:
    """Scans for missing candles between min and max open_time."""
    tf_ms = TF_MS[timeframe]
    query = text("""
        SELECT open_time FROM market_data.candles
        WHERE symbol = :symbol AND timeframe = :timeframe
        ORDER BY open_time ASC;
    """)
    async with engine.connect() as conn:
        res = await conn.execute(query, {"symbol": symbol, "timeframe": timeframe})
        rows = res.fetchall()

    if not rows:
        return {"symbol": symbol, "timeframe": timeframe, "total_bars": 0, "gaps_count": 0}

    timestamps = [r[0] for r in rows]
    total_bars = len(timestamps)
    gaps = []

    for i in range(len(timestamps) - 1):
        diff = (timestamps[i+1] - timestamps[i]).total_seconds() * 1000.0
        if diff > (tf_ms * 1.5):
            missing_bars = int(diff // tf_ms) - 1
            gaps.append({
                "from": timestamps[i].isoformat(),
                "to": timestamps[i+1].isoformat(),
                "missing_bars": missing_bars,
            })

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "total_bars": total_bars,
        "start": timestamps[0].isoformat(),
        "end": timestamps[-1].isoformat(),
        "gaps_count": len(gaps),
        "gaps": gaps[:5],  # sample first 5 gaps if any
    }


async def run_full_backfill():
    client = BinanceRestClient()
    try:
        print("\n" + "=" * 80)
        print("STARTING 3+ YEAR PRODUCTION BACKFILL (BINANCE USD-M 8 PERPETUALS)")
        print(f"Target Symbols: {', '.join(SYMBOLS)}")
        print(f"Target Timeframes: {', '.join(TIMEFRAMES)}")
        print(f"Earliest Window: {datetime.fromtimestamp(START_MS_3Y/1000, tz=timezone.utc).isoformat()}")
        print("=" * 80 + "\n")

        # 1. Backfill klines
        for sym in SYMBOLS:
            for tf in TIMEFRAMES:
                await backfill_klines_for_symbol(client, sym, tf, START_MS_3Y)

        # 2. Backfill funding rates
        for sym in SYMBOLS:
            await backfill_funding_rates_for_symbol(client, sym, START_MS_3Y)

        # 3. Print Row Counts and Date Ranges per Symbol & Timeframe
        print("\n" + "=" * 80)
        print("DATABASE ROW COUNTS & DATE RANGES PER SYMBOL / TIMEFRAME")
        print("=" * 80)

        query = text("""
            SELECT symbol, timeframe, count(*) AS total_rows,
                   min(open_time) AS start_time, max(open_time) AS end_time
            FROM market_data.candles
            GROUP BY symbol, timeframe
            ORDER BY symbol, timeframe;
        """)
        async with engine.connect() as conn:
            res = await conn.execute(query)
            rows = res.fetchall()

        print(f"{'Symbol':<12} | {'Timeframe':<10} | {'Row Count':<10} | {'Start Time (UTC)':<24} | {'End Time (UTC)':<24}")
        print("-" * 90)
        for r in rows:
            print(f"{r[0]:<12} | {r[1]:<10} | {r[2]:<10} | {str(r[3]):<24} | {str(r[4]):<24}")

        # 4. Print Funding Rate Summary
        query_fund = text("""
            SELECT symbol, count(*) AS total_funding,
                   min(funding_time) AS start_time, max(funding_time) AS end_time
            FROM market_data.funding_rates
            GROUP BY symbol
            ORDER BY symbol;
        """)
        async with engine.connect() as conn:
            res_fund = await conn.execute(query_fund)
            rows_fund = res_fund.fetchall()

        print("\n" + "=" * 80)
        print("DATABASE FUNDING RATE RECORDS PER SYMBOL")
        print("=" * 80)
        print(f"{'Symbol':<12} | {'Records':<10} | {'Start Time (UTC)':<24} | {'End Time (UTC)':<24}")
        print("-" * 75)
        for rf in rows_fund:
            print(f"{rf[0]:<12} | {rf[1]:<10} | {str(rf[2]):<24} | {str(rf[3]):<24}")

        # 5. Gap Report
        print("\n" + "=" * 80)
        print("INTEGRITY & GAP REPORT (1h & 4h)")
        print("=" * 80)
        for sym in SYMBOLS:
            for tf in TIMEFRAMES:
                report = await generate_gap_report(sym, tf)
                print(f"[{sym} {tf}] Total Bars: {report['total_bars']} | Gaps Detected: {report['gaps_count']}")
                if report['gaps_count'] > 0:
                    for g in report['gaps']:
                        print(f"    Missing ~{g['missing_bars']} bars between {g['from']} and {g['to']}")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(run_full_backfill())

