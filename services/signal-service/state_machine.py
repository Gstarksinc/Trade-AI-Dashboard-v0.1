"""Authoritative Signal Lifecycle State Machine with Optimistic Locking."""

from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional, Tuple
from sqlalchemy import text
from libs.database.connection import engine

log = logging.getLogger("signal-service.state-machine")

VALID_TRANSITIONS = {
    "waiting_for_confirmation": ["waiting_for_entry", "rejected"],
    "waiting_for_entry": ["order_in_progress", "expired", "invalidated"],
    "order_in_progress": ["win_target_hit", "loss_stop_loss_hit"],
    "win_target_hit": [],
    "loss_stop_loss_hit": [],
    "expired": [],
    "invalidated": [],
}


class SignalStateMachine:
    @staticmethod
    async def create_signal_from_approved(payload: dict) -> Optional[int]:
        """Inserts an approved signal with initial status 'waiting_for_entry'."""
        query = text("""
            INSERT INTO signals_ledger.signals (
                candle_open_time, symbol, timeframe, direction,
                probability, meta_probability, entry, stop_loss, take_profit,
                status, version, created_at
            ) VALUES (
                :candle_open_time, :symbol, :timeframe, :direction,
                :probability, :meta_probability, :entry, :stop_loss, :take_profit,
                'waiting_for_entry', 1, now()
            )
            ON CONFLICT (symbol, timeframe, candle_open_time, direction)
            DO NOTHING
            RETURNING id;
        """)
        async with engine.begin() as conn:
            res = await conn.execute(query, {
                "candle_open_time": payload["candle_open_time"],
                "symbol": payload["symbol"],
                "timeframe": payload["timeframe"],
                "direction": payload["direction"],
                "probability": payload["probability"],
                "meta_probability": payload["meta_probability"],
                "entry": payload["entry"],
                "stop_loss": payload["stop_loss"],
                "take_profit": payload["take_profit"],
            })
            row = res.fetchone()
            return row[0] if row else None

    @staticmethod
    async def get_active_signals(symbol: Optional[str] = None) -> List[dict]:
        """Fetches signals in non-terminal states ('waiting_for_entry', 'order_in_progress')."""
        where_clause = "WHERE status IN ('waiting_for_entry', 'order_in_progress')"
        params = {}
        if symbol:
            where_clause += " AND symbol = :symbol"
            params["symbol"] = symbol

        query = text(f"""
            SELECT id, symbol, timeframe, direction, entry, stop_loss, take_profit,
                   status, version, candle_open_time, created_at
            FROM signals_ledger.signals
            {where_clause}
            ORDER BY created_at ASC;
        """)
        async with engine.connect() as conn:
            res = await conn.execute(query, params)
            rows = res.fetchall()
            return [
                {
                    "id": r[0],
                    "symbol": r[1],
                    "timeframe": r[2],
                    "direction": r[3],
                    "entry": float(r[4]),
                    "stop_loss": float(r[5]),
                    "take_profit": float(r[6]),
                    "status": r[7],
                    "version": int(r[8]),
                    "candle_open_time": r[9].isoformat(),
                    "created_at": r[10].isoformat(),
                }
                for r in rows
            ]

    @staticmethod
    async def transition_state(
        signal_id: int,
        current_status: str,
        new_status: str,
        current_version: int,
        trigger_event: str,
    ) -> bool:
        """
        Executes idempotent state transition using optimistic locking.
        Returns True if successful, False if version collision or invalid transition.
        """
        allowed = VALID_TRANSITIONS.get(current_status, [])
        if new_status not in allowed:
            log.warning("Invalid state transition rejected: %s -> %s for signal %d", current_status, new_status, signal_id)
            return False

        query = text("""
            UPDATE signals_ledger.signals
            SET status = :new_status,
                version = version + 1
            WHERE id = :signal_id AND version = :current_version
            RETURNING version;
        """)
        async with engine.begin() as conn:
            res = await conn.execute(query, {
                "new_status": new_status,
                "signal_id": signal_id,
                "current_version": current_version,
            })
            row = res.fetchone()
            if row:
                log.info("Transitioned signal %d: %s -> %s (v%d -> v%d) on '%s'",
                         signal_id, current_status, new_status, current_version, row[0], trigger_event)
                return True
            else:
                log.warning("Optimistic lock collision for signal %d (expected v%d)", signal_id, current_version)
                return False

