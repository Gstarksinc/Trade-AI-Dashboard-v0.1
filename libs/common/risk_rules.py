"""Shared risk and execution cost rules across training and live risk engine."""

from typing import Tuple


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

