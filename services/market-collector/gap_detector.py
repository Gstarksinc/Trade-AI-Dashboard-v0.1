"""Gap detection and historical backfill for candles."""

from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional
try:
    from .binance_rest import BinanceRestClient
    from .storage import MarketDataStorage
except (ImportError, ValueError):
    from binance_rest import BinanceRestClient
    from storage import MarketDataStorage

log = logging.getLogger("market-collector.gap-detector")

TF_MS: Dict[str, int] = {
    "15m": 15 * 60 * 1000,
    "1h": 60 * 60 * 1000,
    "4h": 4 * 60 * 60 * 1000,
}


def parse_kline_row(symbol: str, timeframe: str, raw: list) -> dict:
    """Parse Binance kline REST row into database schema dictionary."""
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "open_time": datetime.fromtimestamp(raw[0] / 1000.0, tz=timezone.utc),
        "close_time": datetime.fromtimestamp(raw[6] / 1000.0, tz=timezone.utc),
        "open": float(raw[1]),
        "high": float(raw[2]),
        "low": float(raw[3]),
        "close": float(raw[4]),
        "volume": float(raw[5]),
        "quote_volume": float(raw[7]),
        "trades_count": int(raw[8]),
        "taker_buy_base": float(raw[9]),
        "taker_buy_quote": float(raw[10]),
        "is_closed": True,
    }


class GapDetector:
    def __init__(self, rest_client: BinanceRestClient, storage: MarketDataStorage):
        self.rest = rest_client
        self.storage = storage

    async def backfill_symbol_timeframe(
        self,
        symbol: str,
        timeframe: str,
        default_bars: int = 500,
    ) -> int:
        tf_ms = TF_MS.get(timeframe, 15 * 60 * 1000)
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        latest_dt = await self.storage.get_latest_candle_time(symbol, timeframe)

        if latest_dt is None:
            # Cold start: fetch recent `default_bars`
            start_ms = now_ms - (default_bars * tf_ms)
            log.info("Cold start backfill for %s %s from %s (%d bars)", symbol, timeframe, datetime.fromtimestamp(start_ms/1000, tz=timezone.utc), default_bars)
        else:
            latest_ms = int(latest_dt.timestamp() * 1000)
            gap_ms = now_ms - latest_ms
            if gap_ms <= tf_ms:
                # No gap to fill
                return 0
            start_ms = latest_ms + tf_ms
            missing_bars = gap_ms // tf_ms
            log.info("Filling gap for %s %s: ~%d bars missing since %s", symbol, timeframe, missing_bars, latest_dt)

        total_inserted = 0
        curr_start = start_ms

        while curr_start < now_ms:
            raw_klines = await self.rest.klines(symbol, timeframe, start_ms=curr_start, limit=1000)
            if not raw_klines:
                break

            # Filter out the current still-forming unclosed bar
            closed_klines = [k for k in raw_klines if k[6] < now_ms]
            if not closed_klines:
                break

            parsed_rows = [parse_kline_row(symbol, timeframe, k) for k in closed_klines]
            await self.storage.insert_candles(parsed_rows)
            total_inserted += len(parsed_rows)

            last_open = closed_klines[-1][0]
            curr_start = last_open + tf_ms
            if len(raw_klines) < 1000:
                break

        if total_inserted > 0:
            log.info("Backfilled %d bars for %s %s", total_inserted, symbol, timeframe)
        return total_inserted

    async def run_full_backfill(self, symbols: List[str], timeframes: List[str]) -> int:
        """Run gap check across all configured symbols and timeframes."""
        total = 0
        for symbol in symbols:
            for tf in timeframes:
                try:
                    total += await self.backfill_symbol_timeframe(symbol, tf)
                except Exception as e:
                    log.warning("Failed backfill for %s %s: %s", symbol, tf, e)
        return total

