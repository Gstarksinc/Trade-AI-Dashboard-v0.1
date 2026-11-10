"""Binance USD-M Futures WebSocket client with jittered reconnect and stream publishing."""

import asyncio
from datetime import datetime, timezone
import json
import logging
import random
from typing import Callable, Dict, List, Optional
import websockets

from libs.common.streams import RedisStreamManager
from libs.contracts.events import CandleClosedEvent, CandleClosedPayload, PriceTickEvent, PriceTickPayload
try:
    from .gap_detector import GapDetector
    from .storage import MarketDataStorage
except (ImportError, ValueError):
    from gap_detector import GapDetector
    from storage import MarketDataStorage

log = logging.getLogger("market-collector.binance-ws")


class BinanceWsClient:
    def __init__(
        self,
        symbols: List[str],
        timeframes: List[str],
        stream_mgr: RedisStreamManager,
        gap_detector: GapDetector,
        storage: MarketDataStorage,
    ):
        self.symbols = [s.lower() for s in symbols]
        self.timeframes = timeframes
        self.stream_mgr = stream_mgr
        self.gap_detector = gap_detector
        self.storage = storage
        self.running = False
        self._last_tick_published: Dict[str, float] = {}

    def build_stream_url(self) -> str:
        streams = []
        for sym in self.symbols:
            # 1s mark price tick stream
            streams.append(f"{sym}@markPrice@1s")
            # Closed candle streams for each tf
            for tf in self.timeframes:
                streams.append(f"{sym}@kline_{tf}")
        combined = "/".join(streams)
        return f"wss://fstream.binance.com/stream?streams={combined}"

    async def handle_message(self, raw_msg: str):
        try:
            data = json.loads(raw_msg)
        except Exception:
            return

        stream_name = data.get("stream", "")
        payload = data.get("data", {})

        # 1. Mark price tick
        if "@markPrice" in stream_name:
            symbol = payload.get("s")  # e.g. "BTCUSDT"
            mark_price_str = payload.get("p")
            index_price_str = payload.get("i")
            if symbol and mark_price_str:
                mark_price = float(mark_price_str)
                index_price = float(index_price_str) if index_price_str else mark_price
                
                # Fast Redis cache (O(1) read for all services)
                await self.stream_mgr.set_latest_price(symbol, mark_price)

                # Throttle price.tick event to at most 1/sec/symbol to avoid stream congestion
                now_ts = asyncio.get_event_loop().time()
                last_ts = self._last_tick_published.get(symbol, 0.0)
                if now_ts - last_ts >= 1.0:
                    self._last_tick_published[symbol] = now_ts
                    event = PriceTickEvent(
                        idempotency_key=f"tick-{symbol}-{int(now_ts * 1000)}",
                        producer="market-collector",
                        payload=PriceTickPayload(
                            symbol=symbol,
                            price=mark_price,
                            mark_price=mark_price,
                            index_price=index_price,
                            bid_price=mark_price,
                            ask_price=mark_price,
                            volume_24h=0.0,
                            ts=int(now_ts * 1000),
                        ),
                    )
                    await self.stream_mgr.publish("price.tick", event)

        # 2. Kline updates
        elif "@kline" in stream_name:
            kline = payload.get("k", {})
            is_closed = kline.get("x", False)
            if not is_closed:
                # Strictly ignore unclosed candle ticks
                return

            symbol = payload.get("s")
            tf = kline.get("i")
            open_ms = kline.get("t")
            close_ms = kline.get("T")

            open_dt = datetime.fromtimestamp(open_ms / 1000.0, tz=timezone.utc)
            close_dt = datetime.fromtimestamp(close_ms / 1000.0, tz=timezone.utc)
            open_p = float(kline.get("o", 0.0))
            high_p = float(kline.get("h", 0.0))
            low_p = float(kline.get("l", 0.0))
            close_p = float(kline.get("c", 0.0))
            vol = float(kline.get("v", 0.0))
            q_vol = float(kline.get("q", 0.0))
            trades = int(kline.get("n", 0))
            tb_base = float(kline.get("V", 0.0))
            tb_quote = float(kline.get("Q", 0.0))

            # Store closed candle into TimescaleDB
            candle_record = {
                "symbol": symbol,
                "timeframe": tf,
                "open_time": open_dt,
                "close_time": close_dt,
                "open": open_p,
                "high": high_p,
                "low": low_p,
                "close": close_p,
                "volume": vol,
                "quote_volume": q_vol,
                "trades_count": trades,
                "taker_buy_base": tb_base,
                "taker_buy_quote": tb_quote,
                "is_closed": True,
            }
            await self.storage.insert_candles([candle_record])

            # Publish candle.closed event
            event = CandleClosedEvent(
                idempotency_key=f"candle-{symbol}-{tf}-{open_ms}",
                producer="market-collector",
                payload=CandleClosedPayload(
                    symbol=symbol,
                    timeframe=tf,
                    open_time=open_dt.isoformat(),
                    close_time=close_dt.isoformat(),
                    open=open_p,
                    high=high_p,
                    low=low_p,
                    close=close_p,
                    volume=vol,
                    quote_volume=q_vol,
                    trades=trades,
                    taker_buy_base=tb_base,
                    taker_buy_quote=tb_quote,
                ),
            )
            await self.stream_mgr.publish("candle.closed", event)
            log.info("Emitted candle.closed for %s %s (close=%.2f, time=%s)", symbol, tf, close_p, close_dt)

    async def run(self):
        self.running = True
        base_delay = 1.0
        consecutive_errors = 0

        while self.running:
            url = self.build_stream_url()
            try:
                log.info("Connecting to Binance WS streams...")
                async with websockets.connect(url, ping_interval=20, ping_timeout=15) as ws:
                    log.info("Connected to Binance WS.")
                    consecutive_errors = 0
                    
                    # On successful connect/reconnect, trigger gap detection in background
                    asyncio.create_task(
                        self.gap_detector.run_full_backfill(
                            [s.upper() for s in self.symbols],
                            self.timeframes,
                        )
                    )

                    async for message in ws:
                        if not self.running:
                            break
                        await self.handle_message(message)

            except (websockets.ConnectionClosed, asyncio.TimeoutError, OSError) as exc:
                if not self.running:
                    break
                consecutive_errors += 1
                jitter = random.uniform(0.7, 1.3)
                sleep_sec = min(base_delay * (2 ** consecutive_errors), 60.0) * jitter
                log.warning("Binance WS disconnected (%s). Reconnecting in %.1fs (attempt %d)...", type(exc).__name__, sleep_sec, consecutive_errors)
                await asyncio.sleep(sleep_sec)
            except Exception:
                if not self.running:
                    break
                log.exception("Unexpected error in WS loop")
                await asyncio.sleep(5.0)

    def stop(self):
        self.running = False

