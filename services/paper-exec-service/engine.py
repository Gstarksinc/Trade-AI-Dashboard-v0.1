"""Paper Trading Execution Engine: Realistic Trade-Through Buffer, Conservative SL-First Rule, and Fees."""

from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional, Tuple
from sqlalchemy import text
from libs.database.connection import engine
try:
    from .config import settings
except (ImportError, ValueError):
    from config import settings

log = logging.getLogger("paper-exec-service.engine")


class PaperExecutionEngine:
    @staticmethod
    async def open_trade(
        signal_id: int,
        symbol: str,
        timeframe: str,
        direction: str,
        entry_price: float,
        leverage: float = 1.0,
    ) -> Optional[int]:
        """Opens a paper trade with database constraint enforcement (one open trade per signal)."""
        query = text("""
            INSERT INTO paper_execution.paper_trades (
                signal_id, opened_at, symbol, timeframe, direction,
                entry, leverage, fees, funding
            ) VALUES (
                :signal_id, now(), :symbol, :timeframe, :direction,
                :entry, :leverage, :fees, 0.0
            )
            ON CONFLICT (signal_id) WHERE closed_at IS NULL DO NOTHING
            RETURNING id;
        """)
        # Entry fee + slippage
        entry_friction = (settings.taker_fee_pct + settings.slippage_pct) * entry_price * leverage
        async with engine.begin() as conn:
            res = await conn.execute(query, {
                "signal_id": signal_id,
                "symbol": symbol,
                "timeframe": timeframe,
                "direction": direction,
                "entry": entry_price,
                "leverage": leverage,
                "fees": entry_friction,
            })
            row = res.fetchone()
            if row:
                log.info("OPENED Paper Trade #%d for signal #%d (%s %s @ %.2f, lev=%.1fx)",
                         row[0], signal_id, symbol, direction, entry_price, leverage)
                return row[0]
            else:
                log.warning("Paper trade for signal #%d already open (deduped).", signal_id)
                return None

    @staticmethod
    async def get_open_trades() -> List[dict]:
        """Fetches all open paper trades and their corresponding SL/TP levels from signals ledger."""
        query = text("""
            SELECT t.id, t.signal_id, t.symbol, t.timeframe, t.direction,
                   t.entry, t.leverage, t.opened_at, t.fees, t.funding,
                   s.stop_loss, s.take_profit, s.version
            FROM paper_execution.paper_trades t
            JOIN signals_ledger.signals s ON t.signal_id = s.id
            WHERE t.closed_at IS NULL;
        """)
        async with engine.connect() as conn:
            res = await conn.execute(query)
            rows = res.fetchall()
            return [
                {
                    "id": r[0],
                    "signal_id": r[1],
                    "symbol": r[2],
                    "timeframe": r[3],
                    "direction": r[4],
                    "entry": float(r[5]),
                    "leverage": float(r[6]),
                    "opened_at": r[7],
                    "fees": float(r[8]),
                    "funding": float(r[9]),
                    "stop_loss": float(r[10]),
                    "take_profit": float(r[11]),
                    "signal_version": int(r[12]),
                }
                for r in rows
            ]

    @classmethod
    async def evaluate_tick_exits(
        cls,
        symbol: str,
        mark_price: float,
        high_price: Optional[float] = None,
        low_price: Optional[float] = None,
    ) -> List[dict]:
        """
        Evaluates open trades against incoming price ticks with:
        1. Trade-through buffer for limit exits.
        2. Conservative SL-first rule on same-candle ambiguity.
        """
        open_trades = await cls.get_open_trades()
        trades_for_symbol = [t for t in open_trades if t["symbol"] == symbol]
        if not trades_for_symbol:
            return []

        h = high_price if high_price is not None else mark_price
        l = low_price if low_price is not None else mark_price
        buf = settings.trade_through_buffer_pct

        closed_results = []

        for t in trades_for_symbol:
            direction = t["direction"].lower()
            entry = t["entry"]
            sl = t["stop_loss"]
            tp = t["take_profit"]
            lev = t["leverage"]

            exit_reason = None
            exit_price = None

            if direction == "long":
                # Trade-through buffer: TP must be penetrated by at least buffer
                tp_trigger = tp * (1.0 + buf)
                sl_trigger = sl

                hit_tp = h >= tp_trigger
                hit_sl = l <= sl_trigger

                if hit_tp and hit_sl:
                    # Same-candle ambiguity: conservative SL-first rule
                    exit_reason = "stop_loss_hit"
                    exit_price = sl
                elif hit_sl:
                    exit_reason = "stop_loss_hit"
                    exit_price = sl
                elif hit_tp:
                    exit_reason = "target_hit"
                    exit_price = tp

            elif direction == "short":
                tp_trigger = tp * (1.0 - buf)
                sl_trigger = sl

                hit_tp = l <= tp_trigger
                hit_sl = h >= sl_trigger

                if hit_tp and hit_sl:
                    exit_reason = "stop_loss_hit"
                    exit_price = sl
                elif hit_sl:
                    exit_reason = "stop_loss_hit"
                    exit_price = sl
                elif hit_tp:
                    exit_reason = "target_hit"
                    exit_price = tp

            if exit_reason and exit_price:
                # Calculate performance metrics
                gross_ret = (exit_price - entry) / entry if direction == "long" else (entry - exit_price) / entry
                # Round-trip exit friction
                exit_friction = (settings.taker_fee_pct + settings.slippage_pct) * exit_price * lev
                total_fees = t["fees"] + exit_friction
                funding_accrued = t["funding"]

                net_ret_pct = (gross_ret * lev) - ((total_fees + funding_accrued) / entry)
                pnl_usd = net_ret_pct * 1000.0  # Normalized $1,000 standard position

                now_utc = datetime.now(timezone.utc)
                duration_sec = int((now_utc - t["opened_at"]).total_seconds())

                # Update database record
                query = text("""
                    UPDATE paper_execution.paper_trades
                    SET closed_at = now(),
                        exit_price = :exit_price,
                        exit_reason = :exit_reason,
                        fees = :fees,
                        pnl_pct = :pnl_pct,
                        pnl_usd = :pnl_usd
                    WHERE id = :id AND closed_at IS NULL;
                """)
                async with engine.begin() as conn:
                    await conn.execute(query, {
                        "exit_price": exit_price,
                        "exit_reason": exit_reason,
                        "fees": total_fees,
                        "pnl_pct": round(net_ret_pct * 100.0, 4),
                        "pnl_usd": round(pnl_usd, 2),
                        "id": t["id"],
                    })

                # Also update corresponding signal state in signals_ledger
                sig_new_status = "win_target_hit" if exit_reason == "target_hit" else "loss_stop_loss_hit"
                sig_query = text("""
                    UPDATE signals_ledger.signals
                    SET status = :sig_status, version = version + 1
                    WHERE id = :signal_id;
                """)
                async with engine.begin() as conn:
                    await conn.execute(sig_query, {
                        "sig_status": sig_new_status,
                        "signal_id": t["signal_id"],
                    })

                closed_info = {
                    "trade_id": t["id"],
                    "signal_id": t["signal_id"],
                    "symbol": symbol,
                    "direction": direction,
                    "entry_price": entry,
                    "exit_price": exit_price,
                    "exit_reason": exit_reason,
                    "net_pnl_pct": round(net_ret_pct * 100.0, 3),
                    "net_pnl_usd": round(pnl_usd, 2),
                    "duration_seconds": duration_sec,
                }
                closed_results.append(closed_info)
                log.info("CLOSED Trade #%d (%s %s): %s at %.2f (Net PnL: %.2f%%, $%s, %ds)",
                         t["id"], symbol, direction, exit_reason, exit_price, net_ret_pct * 100.0, pnl_usd, duration_sec)

        return closed_results

