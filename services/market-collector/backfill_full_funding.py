"""Full Historical Funding Backfill & Candle Integrity Audit.
Backfills Binance USD-M funding rates from 2021-01-01 to present for all 8 symbols.
Audits symbol onboardDates against earliest candle, and reports zero-volume / flat bars.
"""

import asyncio
from datetime import datetime, timezone
import json
import logging
from typing import Dict, List, Tuple
import urllib.request
import numpy as np
import pandas as pd
from sqlalchemy import text

from libs.database.connection import engine
from services.market_collector.binance_rest import BinanceRestClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("funding_and_candle_audit")

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT", "LINKUSDT", "TRXUSDT"]
TIMEFRAMES = ["1h", "4h"]
START_MS_2021 = int(datetime(2021, 1, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)


async def backfill_funding_full_history(client: BinanceRestClient, symbol: str) -> int:
    """Paginates funding rates from 2021-01-01 until present using startTime."""
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    curr_start = START_MS_2021
    total_saved = 0

    log.info("Backfilling full funding history for %s...", symbol)
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
                    "mark_price": float(r.get("markPrice", 0.0) if r.get("markPrice") != "" else 0.0),
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

            total_saved += len(rates)
            last_time = int(raw[-1]["fundingTime"])
            if last_time <= curr_start:
                break
            curr_start = last_time + 1

            if len(raw) < 1000:
                break

        except Exception as e:
            log.warning("Funding fetch error for %s at %s: %s", symbol, curr_start, e)
            await asyncio.sleep(1.0)
            curr_start += 8 * 3600 * 1000 * 500

    log.info("Finished funding backfill for %s: %d records saved/upserted.", symbol, total_saved)
    return total_saved


def fetch_binance_exchange_info() -> Dict[str, any]:
    """Fetches onboardDate and trading specifications from Binance USD-M exchangeInfo."""
    url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
    req = urllib.request.urlopen(url, timeout=15)
    data = json.loads(req.read().decode())
    out = {}
    for s in data.get("symbols", []):
        sym = s["symbol"]
        if sym in SYMBOLS:
            onboard_ms = s.get("onboardDate", 0)
            out[sym] = {
                "onboard_ms": onboard_ms,
                "onboard_utc": datetime.fromtimestamp(onboard_ms / 1000.0, tz=timezone.utc).isoformat() if onboard_ms else "Unknown",
                "status": s.get("status"),
                "baseAsset": s.get("baseAsset"),
                "quoteAsset": s.get("quoteAsset"),
            }
    return out


async def audit_candles_and_onboard_dates(onboard_info: Dict[str, any]) -> List[Dict[str, any]]:
    """Compares earliest candle against onboardDate, and checks zero-volume and flat bars."""
    reports = []
    async with engine.connect() as conn:
        for sym in SYMBOLS:
            onboard = onboard_info.get(sym, {})
            onboard_utc = onboard.get("onboard_utc", "Unknown")

            for tf in TIMEFRAMES:
                query = text("""
                    SELECT
                        count(*) AS total_bars,
                        min(open_time) AS first_candle,
                        max(open_time) AS last_candle,
                        count(*) FILTER (WHERE volume = 0) AS zero_volume_bars,
                        count(*) FILTER (WHERE high = low) AS flat_bars
                    FROM market_data.candles
                    WHERE symbol = :symbol AND timeframe = :timeframe;
                """)
                res = await conn.execute(query, {"symbol": sym, "timeframe": tf})
                row = res.fetchone()

                reports.append({
                    "symbol": sym,
                    "timeframe": tf,
                    "onboard_date_utc": onboard_utc,
                    "first_candle_utc": row[1].isoformat() if row[1] else "None",
                    "last_candle_utc": row[2].isoformat() if row[2] else "None",
                    "total_bars": row[0],
                    "zero_volume_bars": row[3],
                    "flat_bars": row[4],
                    "candle_after_onboard": row[1] >= datetime.fromtimestamp(onboard.get("onboard_ms", 0)/1000.0, tz=timezone.utc) if row[1] and onboard.get("onboard_ms") else False,
                })
    return reports


async def main():
    client = BinanceRestClient()
    try:
        # 1. Backfill full funding rates for all 8 symbols
        print("\n" + "=" * 80)
        print("BACKFILLING FULL FUNDING RATE HISTORY (2021-01-01 TO PRESENT)")
        print("=" * 80)
        for sym in SYMBOLS:
            await backfill_funding_full_history(client, sym)

        # 2. Query funding summary from DB
        query_fund = text("""
            SELECT symbol, count(*) AS total_funding,
                   min(funding_time) AS min_time, max(funding_time) AS max_time
            FROM market_data.funding_rates
            GROUP BY symbol ORDER BY symbol;
        """)
        async with engine.connect() as conn:
            res_fund = await conn.execute(query_fund)
            rows_fund = res_fund.fetchall()

        print("\n" + "=" * 80)
        print("DATABASE FUNDING RATE TABLE SUMMARY AFTER FULL BACKFILL")
        print("=" * 80)
        print(f"{'Symbol':<10} | {'Count':<8} | {'Earliest (UTC)':<26} | {'Latest (UTC)':<26}")
        print("-" * 80)
        for rf in rows_fund:
            print(f"{rf[0]:<10} | {rf[1]:<8} | {str(rf[2]):<26} | {str(rf[3]):<26}")

        # 3. ExchangeInfo Onboard Dates and Candle Audit
        print("\n" + "=" * 80)
        print("EXCHANGEINFO ONBOARD DATE VS FIRST CANDLE & FLAT BARS AUDIT")
        print("=" * 80)
        onboard_info = fetch_binance_exchange_info()
        candle_audit = await audit_candles_and_onboard_dates(onboard_info)

        print(f"{'Symbol':<8} | {'TF':<3} | {'Onboard Date (UTC)':<22} | {'First Candle (UTC)':<22} | {'Total':<6} | {'Zero-Vol':<8} | {'Flat':<6}")
        print("-" * 95)
        for ca in candle_audit:
            print(f"{ca['symbol']:<8} | {ca['timeframe']:<3} | {ca['onboard_date_utc'][:19]:<22} | {ca['first_candle_utc'][:19]:<22} | {ca['total_bars']:<6} | {ca['zero_volume_bars']:<8} | {ca['flat_bars']:<6}")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
