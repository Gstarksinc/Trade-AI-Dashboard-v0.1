"""Marcos López de Prado's Triple-Barrier Labeling Method."""
import numpy as np
import pandas as pd


def apply_triple_barrier(
    df: pd.DataFrame,
    pt_multiplier: float = 2.0,
    sl_multiplier: float = 1.0,
    max_holding_bars: int = 24,
    atr_col: str = 'atr_14',
) -> pd.DataFrame:
    """
    Computes triple-barrier labels for each candle:
    - Upper barrier (Take Profit): Close + pt_multiplier * ATR
    - Lower barrier (Stop Loss): Close - sl_multiplier * ATR
    - Vertical barrier: max_holding_bars into the future

    Returns a DataFrame containing:
    - label: +1 (TP hit first), -1 (SL hit first), 0 (Time barrier expired)
    - touch_time: Timestamp when barrier was touched
    - holding_bars: Number of bars until barrier touch
    - return_pct: Percentage return from entry to touch point
    - barrier: 'tp', 'sl', or 'time'
    """
    n = len(df)
    close = df['close'].values
    high = df['high'].values
    low = df['low'].values
    times = df.index

    if atr_col in df.columns:
        atrs = df[atr_col].values
    else:
        # Fallback to rolling std if ATR not present
        atrs = df['close'].pct_change().rolling(14).std().fillna(0.01).values * close

    labels = np.zeros(n, dtype=int)
    returns = np.zeros(n, dtype=float)
    holding_bars = np.zeros(n, dtype=int)
    barriers = ['time'] * n
    touch_times = [None] * n

    for i in range(n):
        entry_price = close[i]
        atr_val = atrs[i] if not np.isnan(atrs[i]) and atrs[i] > 0 else (entry_price * 0.01)
        
        upper_barrier = entry_price + pt_multiplier * atr_val
        lower_barrier = entry_price - sl_multiplier * atr_val
        max_idx = min(n - 1, i + max_holding_bars)

        touched = False
        for j in range(i + 1, max_idx + 1):
            h_j = high[j]
            l_j = low[j]

            hit_upper = h_j >= upper_barrier
            hit_lower = l_j <= lower_barrier

            if hit_upper and hit_lower:
                # Both breached in same candle: conservative assumption is Stop Loss hit first
                labels[i] = -1
                returns[i] = (lower_barrier - entry_price) / entry_price
                holding_bars[i] = j - i
                barriers[i] = 'sl'
                touch_times[i] = times[j]
                touched = True
                break
            elif hit_upper:
                labels[i] = 1
                returns[i] = (upper_barrier - entry_price) / entry_price
                holding_bars[i] = j - i
                barriers[i] = 'tp'
                touch_times[i] = times[j]
                touched = True
                break
            elif hit_lower:
                labels[i] = -1
                returns[i] = (lower_barrier - entry_price) / entry_price
                holding_bars[i] = j - i
                barriers[i] = 'sl'
                touch_times[i] = times[j]
                touched = True
                break

        if not touched:
            # Time barrier reached
            exit_price = close[max_idx]
            ret = (exit_price - entry_price) / entry_price
            labels[i] = 0
            returns[i] = ret
            holding_bars[i] = max_idx - i
            barriers[i] = 'time'
            touch_times[i] = times[max_idx]

    result = pd.DataFrame(
        {
            'label': labels,
            'return_pct': returns,
            'holding_bars': holding_bars,
            'barrier': barriers,
            'touch_time': touch_times,
        },
        index=df.index,
    )

    return result

