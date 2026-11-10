"""Database storage for market data with ON CONFLICT deduplication."""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy import text
from libs.database.connection import engine

log = logging.getLogger("market-collector.storage")


class MarketDataStorage:
    @staticmethod
    async def get_latest_candle_time(symbol: str, timeframe: str) -> Optional[datetime]:
        """Fetch the most recent candle open_time for the given symbol and timeframe."""
        query = text("""
            SELECT open_time FROM market_data.candles
            WHERE symbol = :symbol AND timeframe = :timeframe
            ORDER BY open_time DESC LIMIT 1;
        """)
        async with engine.connect() as conn:
            result = await conn.execute(query, {"symbol": symbol, "timeframe": timeframe})
            row = result.fetchone()
            return row[0] if row else None

    @staticmethod
    async def insert_candles(candles: List[Dict[str, Any]]) -> int:
        """Bulk insert candles with ON CONFLICT (symbol, timeframe, open_time) DO NOTHING."""
        if not candles:
            return 0
        query = text("""
            INSERT INTO market_data.candles (
                symbol, timeframe, open_time, close_time,
                open, high, low, close, volume,
                quote_volume, trades_count, taker_buy_base, taker_buy_quote, is_closed
            ) VALUES (
                :symbol, :timeframe, :open_time, :close_time,
                :open, :high, :low, :close, :volume,
                :quote_volume, :trades_count, :taker_buy_base, :taker_buy_quote, :is_closed
            )
            ON CONFLICT (symbol, timeframe, open_time) DO UPDATE SET
                close_time = EXCLUDED.close_time,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume,
                quote_volume = EXCLUDED.quote_volume,
                trades_count = EXCLUDED.trades_count,
                taker_buy_base = EXCLUDED.taker_buy_base,
                taker_buy_quote = EXCLUDED.taker_buy_quote,
                is_closed = EXCLUDED.is_closed;
        """)
        async with engine.begin() as conn:
            await conn.execute(query, candles)
        return len(candles)

    @staticmethod
    async def insert_funding_rates(rates: List[Dict[str, Any]]) -> int:
        """Bulk insert funding rates with ON CONFLICT (symbol, funding_time) DO NOTHING."""
        if not rates:
            return 0
        query = text("""
            INSERT INTO market_data.funding_rates (symbol, funding_time, funding_rate, mark_price)
            VALUES (:symbol, :funding_time, :funding_rate, :mark_price)
            ON CONFLICT (symbol, funding_time) DO NOTHING;
        """)
        async with engine.begin() as conn:
            await conn.execute(query, rates)
        return len(rates)

    @staticmethod
    async def insert_open_interest(records: List[Dict[str, Any]]) -> int:
        """Bulk insert open interest records with ON CONFLICT (symbol, timeframe, timestamp) DO NOTHING."""
        if not records:
            return 0
        query = text("""
            INSERT INTO market_data.open_interest (symbol, timeframe, timestamp, open_interest, open_interest_value)
            VALUES (:symbol, :timeframe, :timestamp, :open_interest, :open_interest_value)
            ON CONFLICT (symbol, timeframe, timestamp) DO NOTHING;
        """)
        async with engine.begin() as conn:
            await conn.execute(query, records)
        return len(records)

