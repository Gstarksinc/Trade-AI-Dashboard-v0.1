"""Cross-asset and regime features: BTC Correlation, Volatility Regimes, Cyclical Time Features."""

import numpy as np
import pandas as pd


def compute_btc_correlation(symbol_returns: pd.Series, btc_returns: pd.Series, window: int = 48) -> pd.Series:
    """Computes rolling correlation of an asset's returns with BTC returns."""
    if btc_returns is None or btc_returns.empty:
        return pd.Series(0.0, index=symbol_returns.index)
    aligned_btc = btc_returns.reindex(symbol_returns.index, method="ffill")
    corr = symbol_returns.rolling(window, min_periods=window // 2).corr(aligned_btc)
    return corr.fillna(0.0)


def compute_volatility_regime(atr_series: pd.Series, window: int = 96) -> pd.Series:
    """Volatility regime ratio: Current ATR relative to its rolling median."""
    rolling_median = atr_series.rolling(window, min_periods=window // 4).median()
    ratio = atr_series / rolling_median.replace(0, np.nan)
    return ratio.fillna(1.0)


def compute_time_features(timestamps: pd.DatetimeIndex) -> pd.DataFrame:
    """Cyclical sine and cosine encodings for hour of day (24h) and day of week (7d)."""
    df = pd.DataFrame(index=timestamps)
    hour = timestamps.hour
    day = timestamps.dayofweek

    df["hour_sin"] = np.sin(2 * np.pi * hour / 24.0)
    df["hour_cos"] = np.cos(2 * np.pi * hour / 24.0)
    df["day_sin"] = np.sin(2 * np.pi * day / 7.0)
    df["day_cos"] = np.cos(2 * np.pi * day / 7.0)
    return df


def compute_cross_asset_features(
    candles_df: pd.DataFrame,
    btc_candles_df: pd.DataFrame = None,
    atr_series: pd.Series = None,
    adx_series: pd.Series = None,
) -> pd.DataFrame:
    """Aggregates cross-asset, regime, and temporal features."""
    df = pd.DataFrame(index=candles_df.index)

    # 1. Cyclical Time Features
    time_feats = compute_time_features(candles_df.index)
    for col in time_feats.columns:
        df[col] = time_feats[col]

    # 2. Volatility Regime & Trend Regime
    if atr_series is not None and not atr_series.empty:
        df["volatility_regime"] = compute_volatility_regime(atr_series)
    else:
        df["volatility_regime"] = 1.0

    # Trend vs Mean-reverting regime: ADX > 25 indicates trending, <= 25 mean-reverting
    if adx_series is not None and not adx_series.empty:
        df["regime_trend_score"] = (adx_series / 50.0).clip(upper=2.0)
    else:
        df["regime_trend_score"] = 0.5

    # 3. BTC Correlation
    if btc_candles_df is not None and not btc_candles_df.empty:
        sym_ret = candles_df["close"].pct_change()
        btc_ret = btc_candles_df["close"].pct_change()
        df["btc_corr_48"] = compute_btc_correlation(sym_ret, btc_ret, 48)
        df["btc_corr_96"] = compute_btc_correlation(sym_ret, btc_ret, 96)
    else:
        df["btc_corr_48"] = 0.0
        df["btc_corr_96"] = 0.0

    return df

