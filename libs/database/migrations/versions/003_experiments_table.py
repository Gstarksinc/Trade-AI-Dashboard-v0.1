"""Create experiments table in model_registry

Revision ID: 003_experiments_table
Revises: 002_shadow_predictions
Create Date: 2026-11-11 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = '003_experiments_table'
down_revision = '002_shadow_predictions'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS model_registry.experiments (
            id SERIAL PRIMARY KEY,
            experiment_id TEXT UNIQUE NOT NULL,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            model_name TEXT NOT NULL,
            prob_threshold NUMERIC(6, 4) NOT NULL,
            meta_threshold NUMERIC(6, 4) NOT NULL,
            holdout_trades INTEGER NOT NULL DEFAULT 0,
            holdout_net_ev_pct NUMERIC(8, 4) NOT NULL DEFAULT 0.0,
            holdout_sharpe NUMERIC(8, 4) NOT NULL DEFAULT 0.0,
            pbo NUMERIC(6, 4) NOT NULL DEFAULT 0.0,
            dsr NUMERIC(6, 4) NOT NULL DEFAULT 0.0,
            status TEXT NOT NULL DEFAULT 'Evaluated',
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_experiments_symbol_tf
            ON model_registry.experiments (symbol, timeframe);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS model_registry.experiments CASCADE;")
