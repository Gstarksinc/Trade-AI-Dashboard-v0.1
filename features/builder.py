"""Unified Feature Builder pipeline for Trade AI."""
import pandas as pd

from .cross_asset import compute_cross_asset_features
from .derivatives import compute_derivatives_features
from .ta import compute_all_ta


def build_features(
    candles: pd.DataFrame,
    funding: pd.DataFrame = None,
    oi: pd.DataFrame = None,
    lsr: pd.DataFrame = None,
    taker: pd.DataFrame = None,
    btc_candles: pd.DataFrame = None,
) -> pd.DataFrame:
    """
    Builds the full feature matrix for a single symbol.
    Ensures input dataframe is indexed by open_time (UTC).
    All feature calculations are strictly causal (no future data leakage).
    """
    if candles.empty:
        return pd.DataFrame()

    df = candles.copy()
    if 'open_time' in df.columns:
        df['open_time'] = pd.to_datetime(df['open_time'], utc=True)
        df = df.set_index('open_time')
    df = df.sort_index()

    # 1. Technical Indicators
    ta_df = compute_all_ta(df)

    # 2. Derivatives & Microstructure
    deriv_df = compute_derivatives_features(df, funding, oi, lsr, taker)

    # 3. Cross-Asset, Regime, and Time
    cross_df = compute_cross_asset_features(df, btc_candles, ta_df.get('atr_14'))

    # Combine all feature sets
    full_df = pd.concat([df[['open', 'high', 'low', 'close', 'volume']], ta_df, deriv_df, cross_df], axis=1)

    # Fill any residual initial NaNs cleanly
    clean_features = full_df.bfill().ffill()

    return clean_features

