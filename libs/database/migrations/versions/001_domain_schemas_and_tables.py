"""001_domain_schemas_and_tables

Revision ID: 001_initial
Revises: None
Create Date: 2026-11-10 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. TimescaleDB Extension
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")

    # 2. Domain Schemas
    op.execute("""
        CREATE SCHEMA IF NOT EXISTS market_data;
        CREATE SCHEMA IF NOT EXISTS feature_store;
        CREATE SCHEMA IF NOT EXISTS model_registry;
        CREATE SCHEMA IF NOT EXISTS signals_ledger;
        CREATE SCHEMA IF NOT EXISTS paper_execution;
        CREATE SCHEMA IF NOT EXISTS outbox;
    """)

    # 3. Market Data Domain
    op.execute("""
        CREATE TABLE IF NOT EXISTS market_data.symbols (
            symbol          text PRIMARY KEY,
            base_asset      text,
            is_active       boolean DEFAULT true,
            onboard_date    timestamptz,
            updated_at      timestamptz DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS market_data.candles (
            symbol          text NOT NULL,
            timeframe       text NOT NULL,
            open_time       timestamptz NOT NULL,
            close_time      timestamptz,
            open            double precision NOT NULL,
            high            double precision NOT NULL,
            low             double precision NOT NULL,
            close           double precision NOT NULL,
            volume          double precision NOT NULL,
            quote_volume    double precision NOT NULL,
            trades_count    int,
            taker_buy_base  double precision,
            taker_buy_quote double precision,
            is_closed       boolean DEFAULT true,
            PRIMARY KEY (symbol, timeframe, open_time)
        );
        SELECT create_hypertable('market_data.candles', 'open_time', if_not_exists => TRUE, chunk_time_interval => INTERVAL '30 days');
        ALTER TABLE market_data.candles SET (timescaledb.compress, timescaledb.compress_segmentby = 'symbol,timeframe', timescaledb.compress_orderby = 'open_time DESC');
        SELECT add_compression_policy('market_data.candles', INTERVAL '30 days', if_not_exists => TRUE);

        CREATE TABLE IF NOT EXISTS market_data.funding_rates (
            symbol       text NOT NULL,
            funding_time timestamptz NOT NULL,
            funding_rate double precision NOT NULL,
            mark_price   double precision NOT NULL,
            PRIMARY KEY (symbol, funding_time)
        );
        SELECT create_hypertable('market_data.funding_rates', 'funding_time', if_not_exists => TRUE, chunk_time_interval => INTERVAL '90 days');

        CREATE TABLE IF NOT EXISTS market_data.open_interest (
            symbol              text NOT NULL,
            timeframe           text NOT NULL,
            timestamp           timestamptz NOT NULL,
            open_interest       double precision,
            open_interest_value double precision,
            PRIMARY KEY (symbol, timeframe, timestamp)
        );
        SELECT create_hypertable('market_data.open_interest', 'timestamp', if_not_exists => TRUE, chunk_time_interval => INTERVAL '30 days');

        CREATE TABLE IF NOT EXISTS market_data.taker_volume (
            symbol         text NOT NULL,
            ts             timestamptz NOT NULL,
            period         text NOT NULL,
            buy_sell_ratio double precision,
            buy_vol        double precision,
            sell_vol       double precision,
            PRIMARY KEY (symbol, period, ts)
        );
        SELECT create_hypertable('market_data.taker_volume', 'ts', if_not_exists => TRUE, chunk_time_interval => INTERVAL '30 days');
    """)

    # 4. Feature Store Domain
    op.execute("""
        CREATE TABLE IF NOT EXISTS feature_store.features (
            symbol              text NOT NULL,
            timeframe           text NOT NULL,
            candle_open_time    timestamptz NOT NULL,
            feature_set_version text NOT NULL,
            features            jsonb NOT NULL,
            created_at          timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (symbol, timeframe, candle_open_time, feature_set_version)
        );
        SELECT create_hypertable('feature_store.features', 'candle_open_time', if_not_exists => TRUE, chunk_time_interval => INTERVAL '30 days');
    """)

    # 5. Model Registry Domain
    op.execute("""
        CREATE TABLE IF NOT EXISTS model_registry.models (
            version             text PRIMARY KEY,
            stage               text NOT NULL DEFAULT 'challenger', -- 'champion' | 'challenger' | 'retired'
            algorithm           text NOT NULL,
            feature_set_version text NOT NULL,
            metrics             jsonb NOT NULL,
            artifact_path       text NOT NULL,
            created_at          timestamptz NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS model_registry.drift_reports (
            id           bigserial PRIMARY KEY,
            model_version text NOT NULL REFERENCES model_registry.models(version),
            detected_at  timestamptz NOT NULL DEFAULT now(),
            drift_score  double precision NOT NULL,
            psi_scores   jsonb NOT NULL,
            details      jsonb
        );
    """)

    # 6. Signals Ledger Domain
    op.execute("""
        CREATE TABLE IF NOT EXISTS signals_ledger.signals (
            id                   bigserial PRIMARY KEY,
            created_at           timestamptz NOT NULL DEFAULT now(),
            candle_open_time     timestamptz NOT NULL,
            symbol               text NOT NULL,
            timeframe            text NOT NULL,
            direction            text NOT NULL,
            probability          double precision NOT NULL,
            meta_probability     double precision,
            entry                double precision NOT NULL,
            stop_loss            double precision NOT NULL,
            take_profit          double precision NOT NULL,
            atr                  double precision,
            model_version        text NOT NULL DEFAULT 'v1',
            feature_set_version  text NOT NULL DEFAULT 'v1',
            calibration_version  text NOT NULL DEFAULT 'v1',
            regime               text,
            status               text NOT NULL DEFAULT 'waiting_entry',
            cancel_reason        text,
            expires_at           timestamptz NOT NULL DEFAULT (now() + interval '24 hours'),
            version              int NOT NULL DEFAULT 1,
            CONSTRAINT uq_signal_instance UNIQUE (symbol, timeframe, candle_open_time, direction)
        );
        CREATE INDEX IF NOT EXISTS idx_signals_status ON signals_ledger.signals (status, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals_ledger.signals (symbol, created_at DESC);
    """)

    # 7. Paper Execution Domain
    op.execute("""
        CREATE TABLE IF NOT EXISTS paper_execution.paper_trades (
            id          bigserial PRIMARY KEY,
            signal_id   bigint REFERENCES signals_ledger.signals(id),
            opened_at   timestamptz NOT NULL,
            closed_at   timestamptz,
            symbol      text NOT NULL,
            timeframe   text NOT NULL,
            direction   text NOT NULL,
            entry       double precision NOT NULL,
            exit_price  double precision,
            leverage    double precision NOT NULL DEFAULT 1.0,
            fees        double precision NOT NULL DEFAULT 0.0,
            funding     double precision NOT NULL DEFAULT 0.0,
            pnl_pct     double precision,
            pnl_usd     double precision,
            exit_reason text
        );
        CREATE UNIQUE INDEX IF NOT EXISTS one_open_trade_per_signal
            ON paper_execution.paper_trades (signal_id)
            WHERE closed_at IS NULL;
        CREATE INDEX IF NOT EXISTS idx_trades_closed_at ON paper_execution.paper_trades (closed_at DESC);
    """)

    # 8. Outbox Pattern Domain
    op.execute("""
        CREATE TABLE IF NOT EXISTS outbox.events (
            id              bigserial PRIMARY KEY,
            event_id        text NOT NULL UNIQUE,
            stream          text NOT NULL,
            event_type      text NOT NULL,
            idempotency_key text NOT NULL UNIQUE,
            payload         jsonb NOT NULL,
            status          text NOT NULL DEFAULT 'pending',
            created_at      timestamptz NOT NULL DEFAULT now(),
            published_at    timestamptz
        );
        CREATE INDEX IF NOT EXISTS idx_outbox_pending ON outbox.events (status, id ASC) WHERE status = 'pending';
    """)

    # 9. Expand/Contract Migration: Copy legacy public tables if they exist
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'candles') THEN
                INSERT INTO market_data.candles (
                    symbol, timeframe, open_time, open, high, low, close, volume, quote_volume, trades_count, taker_buy_base, taker_buy_quote, is_closed
                )
                SELECT symbol, timeframe, open_time, open, high, low, close, volume, quote_volume, trades, taker_buy_base, taker_buy_quote, true
                FROM public.candles
                ON CONFLICT (symbol, timeframe, open_time) DO NOTHING;
            END IF;

            IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'funding_rates') THEN
                INSERT INTO market_data.funding_rates
                SELECT symbol, funding_time, funding_rate, mark_price FROM public.funding_rates
                ON CONFLICT (symbol, funding_time) DO NOTHING;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("""
        DROP SCHEMA IF EXISTS outbox CASCADE;
        DROP SCHEMA IF EXISTS paper_execution CASCADE;
        DROP SCHEMA IF EXISTS signals_ledger CASCADE;
        DROP SCHEMA IF EXISTS model_registry CASCADE;
        DROP SCHEMA IF EXISTS feature_store CASCADE;
        DROP SCHEMA IF EXISTS market_data CASCADE;
    """)

