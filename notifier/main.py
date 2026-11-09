"""Trade AI Telegram Notifier Service.
Sends instant trade setup alerts, exit notifications, and collector heartbeats.
Entry point: python -m notifier.main
"""
import asyncio
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx
import psycopg
from psycopg.rows import dict_row
import redis.asyncio as aioredis

log = logging.getLogger('notifier')

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')
DATABASE_URL = os.environ.get('DATABASE_URL', '')
REDIS_URL = os.environ.get('REDIS_URL', '')


class TelegramNotifier:
    def __init__(self, bot_token: str = TELEGRAM_BOT_TOKEN, chat_id: str = TELEGRAM_CHAT_ID):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.client = httpx.AsyncClient(timeout=15.0)

    async def close(self):
        await self.client.aclose()

    async def send_message(self, text: str, parse_mode: str = 'Markdown') -> bool:
        """Sends a message to the configured Telegram chat."""
        if not self.bot_token or not self.chat_id:
            log.info("[Telegram Not Configured] Message:\n%s", text)
            return False

        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                'chat_id': self.chat_id,
                'text': text,
                'parse_mode': parse_mode,
                'disable_web_page_preview': True,
            }
            resp = await self.client.post(url, json=payload)
            if resp.status_code == 200:
                log.info("Telegram notification sent successfully.")
                return True
            else:
                log.warning("Telegram API error (HTTP %d): %s", resp.status_code, resp.text)
        except Exception as e:
            log.error("Failed to send Telegram message: %s", e)
        return False

    async def notify_new_signal(self, sig: dict):
        """Formats and sends a high-priority new signal notification."""
        is_long = sig.get('direction', '').lower() == 'long'
        dir_emoji = "🟢 *LONG*" if is_long else "🔴 *SHORT*"
        prob_pct = round(float(sig.get('probability', 0.5)) * 100)
        meta_pct = round(float(sig.get('meta_probability', 0.65)) * 100) if sig.get('meta_probability') else None
        
        entry = float(sig.get('entry', 0))
        sl = float(sig.get('stop_loss', 0))
        tp = float(sig.get('take_profit', 0))

        risk_pct = abs(entry - sl) / entry * 100 if entry > 0 else 0
        reward_pct = abs(tp - entry) / entry * 100 if entry > 0 else 0
        rr_ratio = reward_pct / (risk_pct or 1)

        msg = (
            f"⚡ *TRADE AI NEW SIGNAL* ⚡\n\n"
            f"📊 *Asset:* #{sig.get('symbol')} ({sig.get('timeframe')})\n"
            f"Direction: {dir_emoji}\n"
            f"AI Confidence: *{prob_pct}%*" + (f" (Meta: *{meta_pct}%*)" if meta_pct else "") + "\n\n"
            f"🎯 *Expected Entry:* `${entry:,.4f}`\n"
            f"🛑 *Stop Loss:* `${sl:,.4f}` (-{risk_pct:.2f}% Risk)\n"
            f"🏆 *Take Profit:* `${tp:,.4f}` (+{reward_pct:.2f}% Reward)\n"
            f"⚖️ *Risk/Reward:* `1 : {rr_ratio:.2f}`\n\n"
            f"🛡️ *Risk Engine:* Max 3.0x Simulated Leverage\n"
            f"🕒 *Timestamp:* `{sig.get('created_at', datetime.now(timezone.utc).isoformat())[:19]} UTC`"
        )
        await self.send_message(msg)

    async def notify_exit(self, symbol: str, direction: str, exit_reason: str, pnl_pct: float):
        """Notifies when a trade reaches its target or stops out."""
        is_profit = pnl_pct >= 0
        status_emoji = "✅ *TARGET HIT*" if is_profit else "🛑 *STOPPED OUT*"
        sign = "+" if is_profit else ""

        msg = (
            f"{status_emoji}\n\n"
            f"📊 *Asset:* #{symbol}\n"
            f"Position: *{direction.upper()}*\n"
            f"Result: *{sign}{pnl_pct:.2f}% Net Return*\n"
            f"Reason: `{exit_reason}`\n"
            f"🕒 *Time:* `{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC`"
        )
        await self.send_message(msg)

    async def notify_heartbeat_warning(self, minutes_quiet: int):
        """Sends an alert if data collection has stalled."""
        msg = (
            f"⚠️ *DATA COLLECTOR ALERT* ⚠️\n\n"
            f"The Binance data collector has been quiet for *{minutes_quiet} minutes*!\n"
            f"Expected incoming 15m candles may be delayed.\n"
            f"Please check your server logs: `docker compose logs -f collector`"
        )
        await self.send_message(msg)


async def poll_signals_and_heartbeats(notifier: TelegramNotifier):
    """Monitors database/Redis for new signals and collector health."""
    last_notified_signal_id = 0
    last_warning_sent_at = None
    r_client = aioredis.from_url(REDIS_URL) if REDIS_URL else None

    # Get latest existing signal ID so we only notify about fresh ones
    if DATABASE_URL:
        try:
            with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT max(id) FROM signals")
                    row = cur.fetchone()
                    last_notified_signal_id = row['max'] or 0
        except Exception as e:
            log.warning("Could not fetch max signal ID: %s", e)

    log.info("Notifier service started. Listening for alerts (latest signal ID: %d)...", last_notified_signal_id)

    while True:
        try:
            # 1. Check for newly created signals in TimescaleDB
            if DATABASE_URL:
                with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT id, symbol, timeframe, direction, probability, meta_probability,
                                   entry, stop_loss, take_profit, atr, created_at, status
                            FROM signals
                            WHERE id > %s AND status = 'open'
                            ORDER BY id ASC
                            LIMIT 5
                        """, (last_notified_signal_id,))
                        new_signals = cur.fetchall()

                        for s in new_signals:
                            await notifier.notify_new_signal(s)
                            last_notified_signal_id = max(last_notified_signal_id, s['id'])

            # 2. Check Collector Heartbeat in Redis / Database
            collector_stale = False
            minutes_quiet = 0

            if r_client:
                try:
                    beat_val = await r_client.get('collector:heartbeat')
                    if beat_val:
                        beat_time = datetime.fromisoformat(beat_val.decode('utf-8'))
                        diff_sec = (datetime.now(timezone.utc) - beat_time).total_seconds()
                        minutes_quiet = int(diff_sec / 60)
                        if minutes_quiet >= 25:
                            collector_stale = True
                except Exception:
                    pass

            if collector_stale:
                now = datetime.now(timezone.utc)
                if not last_warning_sent_at or (now - last_warning_sent_at) > timedelta(hours=2):
                    await notifier.notify_heartbeat_warning(minutes_quiet)
                    last_warning_sent_at = now

        except Exception as e:
            log.warning("Notifier poll loop iteration error: %s", e)

        await asyncio.sleep(15)  # Poll every 15 seconds


async def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    notifier = TelegramNotifier()
    try:
        await poll_signals_and_heartbeats(notifier)
    finally:
        await notifier.close()


if __name__ == '__main__':
    asyncio.run(main())

