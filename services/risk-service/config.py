"""Risk Service Configuration."""

from typing import Dict, List
from pydantic import Field
from libs.common.config import BaseServiceSettings


class RiskSettings(BaseServiceSettings):
    service_name: str = "risk-service"
    consumer_group: str = "risk-service-group"
    consumer_name: str = "risk-worker-1"

    # Sizing & Leverage (Updated per Phase 4 Fixes: 0.5% default risk)
    max_leverage: float = 3.0
    risk_per_trade_pct: float = 0.005  # 0.5% equity risk per trade (strictly conservative)
    max_position_size_usd: float = 50000.0
    initial_virtual_equity: float = 10000.0

    # Loss limits & Cooldowns
    daily_loss_limit_pct: float = 0.03   # 3% daily loss limit
    weekly_loss_limit_pct: float = 0.06  # 6% weekly loss limit
    cooldown_hours: float = 12.0

    # Halts & Shock thresholds
    stale_data_timeout_sec: float = 60.0
    volatility_shock_multiplier: float = 3.0
    max_cost_to_risk_ratio: float = 0.25

    # Cluster limits
    max_open_trades_per_cluster: int = 2
    max_total_open_trades: int = 5

    # Advisory lock for atomic serialized evaluation & reservation
    advisory_lock_id: int = Field(default=888888, env="RISK_ADVISORY_LOCK_ID")


settings = RiskSettings()
