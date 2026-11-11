"""Marcos López de Prado's Triple-Barrier Labeling with Live Limit-Entry Fill Simulation & Funding Accrual."""

from datetime import datetime
from typing import Dict, Optional, Tuple
import numpy as np
import pandas as pd
from libs.common.risk_rules import check_cost_to_risk_gate, DEFAULT_BARRIER_CONFIG


def apply_triple_barrier_with_execution(
    df: pd.DataFrame,
    pt_multiplier: float = DEFAULT_BARRIER_CONFIG.pt_multiplier,
    sl_multiplier: float = DEFAULT_BARRIER_CONFIG.sl_multiplier,
    max_holding_bars: int = 24,
    limit_wait_bars: int = 2,
    atr_col: str = "atr_14",
    funding_col: str = "funding_rate",
    fee_pct: float = 0.0005,       # 0.05% taker fee
    slippage_pct: float = 0.0002,  # 0.02% slippage
    max_cost_to_risk: float = 0.25,
    timeframe: str = "1h",
) -> Tuple[pd.DataFrame, Dict[str, float]]:
    """
    Computes triple-barrier labels matching live limit-entry and execution logic:
    1. Signal is evaluated at candle t close.
    2. Limit entry starts strictly at t+1:
       - Long: fills if Low(t+1..t+limit_wait) <= Entry
       - Short: fills if High(t+1..t+limit_wait) >= Entry
       - If not filled within limit_wait_bars, marked as 'unfilled' (fill_rate calculation).
    3. Cost-to-risk gate check: (round-trip friction / stop_distance <= max_cost_to_risk).
    4. Barriers from entry fill:
       - Upper TP barrier: Entry + pt_multiplier * ATR
       - Lower SL barrier: Entry - sl_multiplier * ATR
       - Vertical barrier: max_holding_bars
       - Conservative SL-first rule: If high and low touch TP & SL in same candle, SL wins.
    5. Funding accrual: incorporates continuous 8h funding rate costs during holding period.
    """
    n = len(df)
    close = df["close"].values
    high = df["high"].values
    low = df["low"].values
    times = df.index

    if atr_col in df.columns:
        atrs = df[atr_col].values
    else:
        atrs = df["close"].pct_change().rolling(14).std().fillna(0.01).values * close

    funding_rates = df[funding_col].values if funding_col in df.columns else np.zeros(n)

    labels = np.zeros(n, dtype=int)
    gross_returns = np.zeros(n, dtype=float)
    net_returns = np.zeros(n, dtype=float)
    funding_costs = np.zeros(n, dtype=float)
    holding_bars = np.zeros(n, dtype=int)
    barriers = ["unfilled"] * n
    touch_times = [None] * n
    filled_flags = np.zeros(n, dtype=bool)
    cost_gate_passed = np.zeros(n, dtype=bool)

    round_trip_friction = 2.0 * (fee_pct + slippage_pct)
    total_signals = n - (limit_wait_bars + max_holding_bars)
    filled_count = 0

    for i in range(max(0, total_signals)):
        signal_close = close[i]
        atr_val = atrs[i] if not np.isnan(atrs[i]) and atrs[i] > 0 else (signal_close * 0.01)

        # Baseline assumption: evaluate Long signal at candle t close
        entry_price = signal_close
        tp_price = entry_price + pt_multiplier * atr_val
        sl_price = entry_price - sl_multiplier * atr_val

        # Cost-to-risk gate check
        passed_gate, c_ratio, _ = check_cost_to_risk_gate(
            entry_price=entry_price,
            stop_loss_price=sl_price,
            fee_pct=fee_pct,
            slippage_pct=slippage_pct,
            max_cost_to_risk_ratio=max_cost_to_risk,
        )
        cost_gate_passed[i] = passed_gate

        # Step 2: Live Limit Entry Rule starting at t+1
        fill_idx = None
        for k in range(i + 1, min(n, i + 1 + limit_wait_bars)):
            # Long limit fill condition: price trades down to or through entry
            if low[k] <= entry_price:
                fill_idx = k
                break

        if fill_idx is None:
            # Unfilled within window
            barriers[i] = "unfilled"
            continue

        filled_flags[i] = True
        filled_count += 1

        # Step 3: Triple barrier tracking from fill_idx
        max_idx = min(n - 1, fill_idx + max_holding_bars)
        touched = False

        for j in range(fill_idx, max_idx + 1):
            h_j = high[j]
            l_j = low[j]

            hit_upper = h_j >= tp_price
            hit_lower = l_j <= sl_price

            if hit_upper and hit_lower:
                # Conservative SL-first rule
                labels[i] = -1
                raw_ret = (sl_price - entry_price) / entry_price
                holding_bars[i] = j - fill_idx + 1
                barriers[i] = "sl"
                touch_times[i] = times[j]
                touched = True
                break
            elif hit_lower:
                labels[i] = -1
                raw_ret = (sl_price - entry_price) / entry_price
                holding_bars[i] = j - fill_idx + 1
                barriers[i] = "sl"
                touch_times[i] = times[j]
                touched = True
                break
            elif hit_upper:
                labels[i] = 1
                raw_ret = (tp_price - entry_price) / entry_price
                holding_bars[i] = j - fill_idx + 1
                barriers[i] = "tp"
                touch_times[i] = times[j]
                touched = True
                break

        if not touched:
            exit_price = close[max_idx]
            raw_ret = (exit_price - entry_price) / entry_price
            labels[i] = 0
            holding_bars[i] = max_idx - fill_idx + 1
            barriers[i] = "time"
            touch_times[i] = times[max_idx]

        # Step 4: Calculate funding accrual over holding bars
        # Scale 8h funding rate according to bar timeframe
        bars_held = holding_bars[i]
        if timeframe == "1h":
            bars_per_8h = 8.0
        elif timeframe == "4h":
            bars_per_8h = 2.0
        elif timeframe == "15m":
            bars_per_8h = 32.0
        else:
            bars_per_8h = 8.0

        # Funding rate at entry fill (with fallback to 1 bp per 8h if absent/zero)
        if fill_idx < len(funding_rates) and not np.isnan(funding_rates[fill_idx]) and funding_rates[fill_idx] != 0.0:
            f_rate = funding_rates[fill_idx]
        else:
            f_rate = 0.0001  # Baseline fallback (1 bp / 8h)

        funding_accrued = f_rate * (bars_held / bars_per_8h)  # Long pays funding when funding_rate > 0

        gross_returns[i] = raw_ret
        funding_costs[i] = funding_accrued
        net_returns[i] = raw_ret - round_trip_friction - funding_accrued

    fill_rate = float(filled_count / total_signals) if total_signals > 0 else 0.0
    gate_pass_rate = float(np.sum(cost_gate_passed) / total_signals) if total_signals > 0 else 0.0

    result = pd.DataFrame(
        {
            "label": labels,
            "is_filled": filled_flags,
            "cost_gate_passed": cost_gate_passed,
            "gross_return": gross_returns,
            "net_return": net_returns,
            "funding_cost": funding_costs,
            "holding_bars": holding_bars,
            "barrier": barriers,
            "touch_time": touch_times,
        },
        index=df.index,
    )

    stats = {
        "total_signals": total_signals,
        "filled_trades": filled_count,
        "fill_rate": round(fill_rate, 4),
        "gate_pass_rate": round(gate_pass_rate, 4),
    }

    return result, stats


def compute_sample_uniqueness_weights(
    event_start_times: pd.Series,
    event_end_times: pd.Series,
) -> pd.Series:
    """Marcos López de Prado's sample-uniqueness weights."""
    n = len(event_start_times)
    if n == 0:
        return pd.Series(dtype=float)

    valid_mask = ~event_start_times.isna() & ~event_end_times.isna()
    if not valid_mask.any():
        return pd.Series(1.0, index=event_start_times.index)

    all_times = sorted(set(event_start_times[valid_mask]).union(set(event_end_times[valid_mask])))
    if not all_times:
        return pd.Series(1.0, index=event_start_times.index)

    time_idx = pd.DatetimeIndex(all_times)
    concurrency = pd.Series(0, index=time_idx)

    for t_start, t_end in zip(event_start_times[valid_mask], event_end_times[valid_mask]):
        concurrency.loc[t_start:t_end] += 1

    concurrency = concurrency.replace(0, 1)

    uniqueness = []
    for t_start, t_end in zip(event_start_times, event_end_times):
        if pd.isna(t_start) or pd.isna(t_end):
            uniqueness.append(1.0)
            continue
        c_sub = concurrency.loc[t_start:t_end]
        u_i = (1.0 / c_sub).mean() if len(c_sub) > 0 else 1.0
        uniqueness.append(u_i)

    weights = pd.Series(uniqueness, index=event_start_times.index)
    mean_w = weights.mean()
    norm_weights = weights / mean_w if mean_w > 0 else weights
    return norm_weights.fillna(1.0)
