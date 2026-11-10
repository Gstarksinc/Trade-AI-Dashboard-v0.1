"""Create shadow_predictions table in model_registry

Revision ID: 002_shadow_predictions
Revises: 001_domain_schemas_and_tables
Create Date: 2026-11-10 02:30:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = '002_shadow_predictions'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS model_registry.shadow_predictions (
            id                     bigserial PRIMARY KEY,
            created_at             timestamptz NOT NULL DEFAULT now(),
            symbol                 text NOT NULL,
            timeframe              text NOT NULL,
            candle_open_time       timestamptz NOT NULL,
            direction              text NOT NULL,
            raw_probability        double precision NOT NULL,
            calibrated_probability double precision NOT NULL,
            meta_confidence        double precision NOT NULL,
            model_version          text NOT NULL,
            feature_set_version    text NOT NULL,
            feature_hash           text NOT NULL,
            is_shadow              boolean NOT NULL DEFAULT true,
            realized_outcome       text,
            realized_pnl           double precision,
            UNIQUE (model_version, symbol, timeframe, candle_open_time, is_shadow)
        );

        CREATE INDEX IF NOT EXISTS idx_shadow_predictions_ver_sym
            ON model_registry.shadow_predictions (model_version, symbol, timeframe);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS model_registry.shadow_predictions CASCADE;")

