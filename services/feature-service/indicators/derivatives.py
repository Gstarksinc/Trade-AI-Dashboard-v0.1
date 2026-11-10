"""Futures market microstructure features: Funding, Open Interest, Long/Short Ratio, Taker Volume."""

import numpy as np
import pandas as pd


def compute_derivatives_features(
    candles_df: pd.DataFrame,
    funding_df: pd.DataFrame = None,
    oi_df: pd.DataFrame = None,
    lsr_df: pd.DataFrame = None,
    taker_df: pd.DataFrame = None,
) -> pd.DataFrame:
    """Aligns futures derivative metrics with candles on open_time (strictly causal forward-fill)."""
    df = pd.DataFrame(index=candles_df.index)

    # 1. Funding Rates
    if funding_df is not None and not funding_df.empty and "funding_rate" in funding_df.columns:
        f_aligned = funding_df["funding_rate"].reindex(candles_df.index, method="ffill")
        df["funding_rate"] = f_aligned
        df["funding_rate_ma"] = f_aligned.rolling(24, min_periods=1).mean()
        df["funding_annualized"] = f_aligned * 3 * 365 * 100
        f_mean = f_aligned.rolling(72, min_periods=12).mean()
        f_std = f_aligned.rolling(72, min_periods=12).std()
        df["funding_zscore"] = ((f_aligned - f_mean) / f_std.replace(0, np.nan)).fillna(0.0)
    else:
        df["funding_rate"] = 0.0
        df["funding_rate_ma"] = 0.0
        df["funding_annualized"] = 0.0
        df["funding_zscore"] = 0.0

    # 2. Open Interest
    if oi_df is not None and not oi_df.empty and "sum_open_interest" in oi_df.columns:
        oi_aligned = oi_df["sum_open_interest"].reindex(candles_df.index, method="ffill")
        df["oi_change_4"] = oi_aligned.pct_change(4)
        df["oi_change_24"] = oi_aligned.pct_change(24)
        oi_mean = oi_aligned.rolling(48, min_periods=12).mean()
        oi_std = oi_aligned.rolling(48, min_periods=12).std()
        df["oi_zscore"] = ((oi_aligned - oi_mean) / oi_std.replace(0, np.nan)).fillna(0.0)
    else:
        df["oi_change_4"] = 0.0
        df["oi_change_24"] = 0.0
        df["oi_zscore"] = 0.0

    # 3. Long / Short Account Ratio
    if lsr_df is not None and not lsr_df.empty and "ratio" in lsr_df.columns:
        lsr_aligned = lsr_df["ratio"].reindex(candles_df.index, method="ffill")
        df["lsr_ratio"] = lsr_aligned
        df["lsr_delta_4"] = lsr_aligned.diff(4)
        lsr_mean = lsr_aligned.rolling(48, min_periods=12).mean()
        lsr_std = lsr_aligned.rolling(48, min_periods=12).std()
        df["lsr_zscore"] = ((lsr_aligned - lsr_mean) / lsr_std.replace(0, np.nan)).fillna(0.0)
    else:
        df["lsr_ratio"] = 1.0
        df["lsr_delta_4"] = 0.0
        df["lsr_zscore"] = 0.0

    # 4. Taker Volume Imbalance
    if taker_df is not None and not taker_df.empty and "buy_sell_ratio" in taker_df.columns:
        taker_aligned = taker_df["buy_sell_ratio"].reindex(candles_df.index, method="ffill")
        df["taker_buy_sell_ratio"] = taker_aligned
        df["taker_imbalance_ma12"] = taker_aligned.rolling(12, min_periods=1).mean()
    elif "taker_buy_base" in candles_df.columns and "volume" in candles_df.columns:
        buy_vol = candles_df["taker_buy_base"]
        total_vol = candles_df["volume"]
        sell_vol = (total_vol - buy_vol).clip(lower=0.0001)
        approx_ratio = buy_vol / sell_vol
        df["taker_buy_sell_ratio"] = approx_ratio
        df["taker_imbalance_ma12"] = approx_ratio.rolling(12, min_periods=1).mean()
    else:
        df["taker_buy_sell_ratio"] = 1.0
        df["taker_imbalance_ma12"] = 1.0

    return df

