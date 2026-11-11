"""Shared risk and execution cost rules across training and live risk engine."""

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class BarrierMultiplesConfig:
    """
    Shared configuration for Triple-Barrier Stop-Loss and Take-Profit multiples.
    Resolves the 2.0 vs 2.2 conflict:
      Live production value is strictly 2.0x ATR for TP, 1.0x ATR for SL (1:2 Risk-to-Reward).
    """
    pt_multiplier: float = 2.0       # Take profit multiple of ATR (2.0x)
    sl_multiplier: float = 1.0       # Stop loss multiple of ATR (1.0x)
    default_friction: float = 0.0014 # 14 bps round-trip friction (2x 5 bps fee + 2x 2 bps slippage)
    max_cost_to_risk_ratio: float = 0.25 # 25% max friction-to-stop ratio


DEFAULT_BARRIER_CONFIG = BarrierMultiplesConfig()


def check_cost_to_risk_gate(
    entry_price: float,
    stop_loss_price: float,
    fee_pct: float = 0.0005,       # 0.05% taker fee per leg
    slippage_pct: float = 0.0002,  # 0.02% estimated slippage per leg
    max_cost_to_risk_ratio: float = 0.25,
) -> Tuple[bool, float, str]:
    """
    Cost-to-risk gate:
    Evaluates whether two-way transaction costs eat too much of the stop-loss risk distance.
    Ratio = (round-trip friction) / (stop distance).
    If Ratio > max_cost_to_risk_ratio (default 0.25 = 25%), the setup is rejected.
    """
    if entry_price <= 0:
        return False, 1.0, "Invalid entry price <= 0"

    stop_distance_pct = abs(entry_price - stop_loss_price) / entry_price
    if stop_distance_pct <= 1e-6:
        return False, 1.0, "Stop distance too tight or zero"

    # Round-trip friction (entry + exit fees + slippage)
    round_trip_friction_pct = 2.0 * (fee_pct + slippage_pct)

    cost_to_risk_ratio = round_trip_friction_pct / stop_distance_pct

    if cost_to_risk_ratio > max_cost_to_risk_ratio:
        return False, round(cost_to_risk_ratio, 4), (
            f"Cost-to-risk ratio {cost_to_risk_ratio:.1%} exceeds limit {max_cost_to_risk_ratio:.1%} "
            f"(friction={round_trip_friction_pct:.2%}, stop_dist={stop_distance_pct:.2%})"
        )

    return True, round(cost_to_risk_ratio, 4), "Passed cost-to-risk gate"

