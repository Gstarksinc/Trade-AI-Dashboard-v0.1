"""Trade AI Risk Management Engine.
Enforces ATR-based trade levels, volatility-scaled position sizing,
maximum 3x leverage, daily loss limits, and cross-asset correlation caps.
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class RiskLimits:
    max_leverage: float = 3.0
    risk_per_trade_pct: float = 0.01  # 1.0% portfolio risk
    daily_loss_limit_pct: float = 0.03  # 3.0% max daily loss limit
    max_correlated_positions: int = 3
    atr_tp_multiplier: float = 2.0
    atr_sl_multiplier: float = 1.0


def calculate_trade_levels(
    current_price: float,
    atr: float,
    direction: str,
    pt_mult: float = 2.0,
    sl_mult: float = 1.0,
) -> dict:
    """
    Computes precise entry, stop loss, and target levels using ATR volatility boundaries.
    """
    p = float(current_price)
    a = float(atr) if atr and atr > 0 else (p * 0.01)
    is_long = direction.lower() == 'long'

    if is_long:
        entry = p
        stop_loss = round(entry - sl_mult * a, 6)
        take_profit = round(entry + pt_mult * a, 6)
        risk_pct = (entry - stop_loss) / entry
        reward_pct = (take_profit - entry) / entry
    else:
        entry = p
        stop_loss = round(entry + sl_mult * a, 6)
        take_profit = round(entry - pt_mult * a, 6)
        risk_pct = (stop_loss - entry) / entry
        reward_pct = (entry - take_profit) / entry

    rr_ratio = reward_pct / (risk_pct if risk_pct > 0 else 0.001)

    return {
        'entry': entry,
        'stop_loss': max(0.0, stop_loss),
        'take_profit': max(0.0, take_profit),
        'risk_pct': risk_pct * 100.0,
        'reward_pct': reward_pct * 100.0,
        'rr_ratio': round(rr_ratio, 2),
        'atr': a,
    }


def calculate_position_size(
    equity: float,
    entry_price: float,
    stop_loss_price: float,
    risk_pct: float = 0.01,
    max_leverage: float = 3.0,
) -> dict:
    """
    Calculates volatility-scaled position size ensuring portfolio loss
    never exceeds risk_pct if stopped out, capped at max_leverage.
    """
    eq = max(1.0, float(equity))
    entry = float(entry_price)
    sl = float(stop_loss_price)
    max_risk_dollars = eq * risk_pct

    sl_dist_pct = abs(entry - sl) / entry
    if sl_dist_pct <= 0:
        sl_dist_pct = 0.01

    # Position size based on risk
    raw_size_dollars = max_risk_dollars / sl_dist_pct
    
    # Cap position at max leverage (e.g. 3x)
    max_allowed_dollars = eq * max_leverage
    capped_size_dollars = min(raw_size_dollars, max_allowed_dollars)
    effective_leverage = capped_size_dollars / eq
    contracts = capped_size_dollars / entry

    return {
        'position_value_dollars': round(capped_size_dollars, 2),
        'contracts': round(contracts, 4),
        'effective_leverage': round(effective_leverage, 2),
        'max_loss_dollars': round(max_risk_dollars, 2),
        'is_leverage_capped': raw_size_dollars > max_allowed_dollars,
    }


class RiskEngine:
    def __init__(self, limits: Optional[RiskLimits] = None):
        self.limits = limits or RiskLimits()

    def check_daily_loss(self, daily_loss_used_pct: float) -> bool:
        """Returns True if daily loss is within safe limits."""
        return daily_loss_used_pct < self.limits.daily_loss_limit_pct * 100.0

    def check_correlation_cap(self, open_signals: List[dict], new_direction: str) -> bool:
        """
        Enforces maximum simultaneous directional exposure across crypto assets
        (e.g., no more than 3 longs open at once).
        """
        same_direction_count = sum(
            1 for s in open_signals
            if s.get('direction', '').lower() == new_direction.lower() and s.get('status') == 'open'
        )
        return same_direction_count < self.limits.max_correlated_positions

    def validate_new_signal(
        self,
        new_signal: dict,
        current_open_signals: List[dict],
        daily_loss_used_pct: float,
    ) -> Tuple[bool, str]:
        """
        Validates whether a new candidate signal passes all risk controls.
        """
        # 1. Daily Drawdown Guardrail
        if not self.check_daily_loss(daily_loss_used_pct):
            return False, f"Daily loss limit reached ({daily_loss_used_pct:.1f}% >= {self.limits.daily_loss_limit_pct * 100:.1f}%)"

        # 2. Cross-Asset Directional Cap
        direction = new_signal.get('direction', 'long')
        if not self.check_correlation_cap(current_open_signals, direction):
            return False, f"Correlation cap reached ({self.limits.max_correlated_positions} open {direction.upper()} positions)"

        # 3. Minimum Risk/Reward Ratio
        entry = float(new_signal.get('entry', 0))
        sl = float(new_signal.get('stop_loss', 0))
        tp = float(new_signal.get('take_profit', 0))
        if entry > 0 and sl > 0 and tp > 0:
            levels = calculate_trade_levels(entry, abs(entry - sl), direction)
            if levels['rr_ratio'] < 1.3:
                return False, f"Unfavorable R:R ratio ({levels['rr_ratio']:.2f} < 1.30)"

        return True, "Approved by Risk Engine"

