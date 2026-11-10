"""Notifier Service: Telegram Bot Alerts & System Health Monitoring."""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
from typing import Dict, Optional
from fastapi import FastAPI
import httpx
from pydantic import Field

from libs.common.config import BaseServiceSettings
from libs.common.logging import setup_structured_logging
from libs.common.streams import RedisStreamManager
from libs.common.metrics import setup_metrics_endpoint
from libs.contracts.events import SignalApprovedEvent, TradeClosedEvent, SystemDLQEvent

log = setup_structured_logging("notifier-service")


class NotifierSettings(BaseServiceSettings):
    service_name: str = "notifier-service"
    telegram_bot_token: Optional[str] = Field(default=None, env="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: Optional[str] = Field(default=None, env="TELEGRAM_CHAT_ID")
    min_alert_interval_sec: float = 5.0


settings = NotifierSettings()
stream_mgr = RedisStreamManager(redis_url=settings.redis_url, service_name=settings.service_name)
http_client = httpx.AsyncClient(timeout=10.0)
last_alert_time: Dict[str, float] = {}


async def send_telegram_message(text: str):
    """Sends formatted alert message to Telegram bot if credentials configured."""
    if not (settings.telegram_bot_token and settings.telegram_chat_id):
        log.debug("Telegram alert skipped (bot token/chat ID not configured): %s", text[:60])
        return

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    try:
        resp = await http_client.post(url, json=payload)
        if resp.status_code != 200:
            log.warning("Telegram API error HTTP %d: %s", resp.status_code, resp.text)
    except Exception as e:
        log.warning("Telegram notification failed: %s", e)


async def handle_signal_approved(event_data: dict):
    event = SignalApprovedEvent(**event_data)
    p = event.payload
    msg = (
        f"🚨 *NEW SIGNAL APPROVED* 🚨\n\n"
        f"• *Asset*: `{p.symbol}` ({p.timeframe})\n"
        f"• *Direction*: *{p.direction.upper()}*\n"
        f"• *Entry*: `${p.entry:,.2f}`\n"
        f"• *Stop Loss*: `${p.stop_loss:,.2f}`\n"
        f"• *Target*: `${p.take_profit:,.2f}`\n"
        f"• *Confidence*: `{p.probability:.1%}` (Meta: `{p.meta_probability:.1%}`)\n"
        f"• *Leverage*: `{p.leverage:.1f}x` | *Size*: `${p.position_size_usd:,.2f}`\n"
        f"• *Risk Reason*: _{p.risk_reason}_\n\n"
        f"_Paper Trading Mode — No Real Execution_"
    )
    await send_telegram_message(msg)


async def handle_trade_closed(event_data: dict):
    event = TradeClosedEvent(**event_data)
    p = event.payload
    emoji = "🎯" if "target" in p.exit_reason.lower() else "🛑"
    pnl_sign = "+" if p.net_pnl_usd >= 0 else ""
    msg = (
        f"{emoji} *TRADE CLOSED* {emoji}\n\n"
        f"• *Asset*: `{p.symbol}` ({p.direction.upper()})\n"
        f"• *Reason*: *{p.exit_reason.replace('_', ' ').title()}*\n"
        f"• *Entry*: `${p.entry_price:,.2f}` $\\rightarrow$ *Exit*: `${p.exit_price:,.2f}`\n"
        f"• *Net PnL*: *{pnl_sign}${p.net_pnl_usd:,.2f}*\n"
        f"• *Duration*: `{p.duration_seconds // 60}m {p.duration_seconds % 60}s`\n"
    )
    await send_telegram_message(msg)


async def monitor_collector_heartbeat():
    """Alerts if market collector heartbeat is missing for > 60 seconds."""
    while True:
        try:
            if stream_mgr.client:
                hb_raw = await stream_mgr.client.get("collector:heartbeat")
                if hb_raw:
                    hb_time = datetime.fromisoformat(hb_raw.decode() if isinstance(hb_raw, bytes) else hb_raw)
                    age = (datetime.now(timezone.utc) - hb_time).total_seconds()
                    if age > 60.0:
                        log.error("COLLECTOR STALL: No heartbeat for %.1f seconds", age)
                        await send_telegram_message(f"⚠️ *ALERT: Market Collector Stalled* (no heartbeat for {int(age)}s)")
        except Exception:
            pass
        await asyncio.sleep(30)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting notifier-service...")
    await stream_mgr.connect()
    t1 = asyncio.create_task(
        stream_mgr.consume_loop("signal.approved", "notifier-group", "notifier-worker-signals", handle_signal_approved)
    )
    t2 = asyncio.create_task(
        stream_mgr.consume_loop("trade.closed", "notifier-group", "notifier-worker-trades", handle_trade_closed)
    )
    t3 = asyncio.create_task(monitor_collector_heartbeat())
    yield
    t1.cancel()
    t2.cancel()
    t3.cancel()
    await http_client.aclose()
    await stream_mgr.close()
    log.info("Stopped notifier-service.")


app = FastAPI(title="notifier-service", lifespan=lifespan)
setup_metrics_endpoint(app)


@app.get("/health")
async def health():
    return {
        "service": "notifier-service",
        "status": "healthy",
        "telegram_configured": bool(settings.telegram_bot_token and settings.telegram_chat_id),
    }
