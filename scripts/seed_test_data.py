"""Seed verified test records across all domain schemas for backup/restore testing."""

import asyncio
from datetime import datetime, timezone
from sqlalchemy import text
from libs.database.connection import engine


async def seed():
    print("Seeding test rows into domain tables...")
    async with engine.begin() as conn:
        # 1. signals_ledger.signals
        await conn.execute(text("""
            INSERT INTO signals_ledger.signals (
                id, created_at, candle_open_time, symbol, timeframe, direction,
                probability, meta_probability, entry, stop_loss, take_profit, atr,
                model_version, feature_set_version, calibration_version, regime,
                status, version
            ) VALUES
            (1001, NOW(), NOW(), 'BTCUSDT', '1h', 'long', 0.65, 0.70, 50000.0, 49000.0, 52000.0, 1000.0, 'LGBM-TEST-1', 'v1.0.0', 'cal-1', 'trending', 'waiting_for_entry', 1),
            (1002, NOW(), NOW(), 'ETHUSDT', '1h', 'short', 0.62, 0.68, 3000.0, 3100.0, 2800.0, 50.0, 'LGBM-TEST-2', 'v1.0.0', 'cal-1', 'trending', 'waiting_for_confirmation', 1),
            (1003, NOW(), NOW(), 'SOLUSDT', '1h', 'long', 0.75, 0.80, 100.0, 95.0, 110.0, 3.0, 'LGBM-TEST-3', 'v1.0.0', 'cal-1', 'trending', 'closed', 2)
            ON CONFLICT (id) DO NOTHING;
        """))

        # 2. paper_execution.paper_trades
        await conn.execute(text("""
            INSERT INTO paper_execution.paper_trades (
                id, signal_id, symbol, timeframe, direction, entry, leverage,
                opened_at, closed_at, exit_price, exit_reason, fees, funding, pnl_usd, pnl_pct
            ) VALUES
            (2001, 1001, 'BTCUSDT', '1h', 'long', 50000.0, 2.0, NOW(), NULL, NULL, NULL, 5.0, 0.5, 0.0, 0.0),
            (2002, 1003, 'SOLUSDT', '1h', 'long', 100.0, 2.0, NOW(), NOW(), 110.0, 'target_hit', 1.0, 0.1, 20.0, 20.0)
            ON CONFLICT (id) DO NOTHING;
        """))

        # 3. model_registry.models
        await conn.execute(text("""
            INSERT INTO model_registry.models (
                version, stage, algorithm, feature_set_version, metrics, artifact_path, created_at
            ) VALUES
            ('LGBM-SEED-VERIFY-1', 'candidate', 'lightgbm', 'v1.0.0', '{"accuracy": 0.55}'::jsonb, '/app/models/test1.joblib', NOW())
            ON CONFLICT (version) DO NOTHING;
        """))

        # 4. outbox.events
        await conn.execute(text("""
            INSERT INTO outbox.events (
                event_id, stream, event_type, idempotency_key, payload, status
            ) VALUES
            ('evt-seed-1', 'signal.state_changed', 'signal.state_changed', 'idemp-seed-1', '{"signal_id": 1001}'::jsonb, 'published'),
            ('evt-seed-2', 'trade.opened', 'trade.opened', 'idemp-seed-2', '{"trade_id": 2001}'::jsonb, 'pending')
            ON CONFLICT (event_id) DO NOTHING;
        """))

    print("Seeding complete.")


if __name__ == "__main__":
    asyncio.run(seed())
