"""Meta-Labeling method (Marcos López de Prado).
Generates binary labels (1 = execute trade, 0 = pass) for secondary classification.
"""
import numpy as np
import pandas as pd


def compute_meta_labels(
    primary_predictions: pd.Series,
    realized_returns: pd.Series,
    fee_pct: float = 0.0005,  # 0.05% taker fee per leg
    slippage_pct: float = 0.0002,  # 0.02% estimated slippage
    min_profit_threshold: float = 0.0,
) -> pd.DataFrame:
    """
    Computes binary meta-labels based on whether taking the primary model's signal
    yielded a net positive return after two-way fees and slippage.

    Parameters:
    - primary_predictions: Series of primary directional predictions (+1 for Long, -1 for Short)
    - realized_returns: Series of raw path-dependent price returns from triple-barrier touch
    - fee_pct: Fee per leg (entry + exit = 2 * fee_pct)
    - slippage_pct: Slippage per leg (2 * slippage_pct)
    - min_profit_threshold: Minimum net return required to classify as positive (default: 0.0)

    Returns:
    DataFrame with:
    - primary_direction: +1 or -1
    - gross_return: Trade return before transaction costs
    - net_return: Trade return after two-way fees and slippage
    - meta_label: 1 (Take trade / high alpha), 0 (Pass trade / false positive)
    """
    total_friction = 2 * (fee_pct + slippage_pct)
    
    # Trade return is positive if direction matches price movement
    gross_return = primary_predictions * realized_returns
    net_return = gross_return - total_friction

    meta_labels = (net_return > min_profit_threshold).astype(int)

    return pd.DataFrame(
        {
            'primary_direction': primary_predictions,
            'gross_return': gross_return,
            'net_return': net_return,
            'meta_label': meta_labels,
        },
        index=primary_predictions.index,
    )

