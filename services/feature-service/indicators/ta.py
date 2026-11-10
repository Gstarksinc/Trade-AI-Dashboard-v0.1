"""Technical Analysis Indicators with TA-Lib and vectorized NumPy/Pandas fallbacks."""

import numpy as np
import pandas as pd

try:
    import talib
    HAS_TALIB = True
except ImportError:
    HAS_TALIB = False


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index."""
    if HAS_TALIB:
        res = talib.RSI(close.values.astype(float), timeperiod=period)
        return pd.Series(res, index=close.index)
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    res = 100.0 - (100.0 / (1.0 + rs))
    return res.fillna(50.0)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """Moving Average Convergence Divergence."""
    if HAS_TALIB:
        m, s, h = talib.MACD(close.values.astype(float), fastperiod=fast, slowperiod=slow, signalperiod=signal)
        return pd.Series(m, index=close.index), pd.Series(s, index=close.index), pd.Series(h, index=close.index)
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Average True Range."""
    if HAS_TALIB:
        res = talib.ATR(high.values.astype(float), low.values.astype(float), close.values.astype(float), timeperiod=period)
        return pd.Series(res, index=close.index)
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()


def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Average Directional Movement Index."""
    if HAS_TALIB:
        res = talib.ADX(high.values.astype(float), low.values.astype(float), close.values.astype(float), timeperiod=period)
        return pd.Series(res, index=close.index)
    
    # Vectorized fallback
    up = high.diff()
    down = -low.diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    
    tr_smooth = pd.Series(tr, index=close.index).ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    plus_dm_smooth = pd.Series(plus_dm, index=close.index).ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    minus_dm_smooth = pd.Series(minus_dm, index=close.index).ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    
    plus_di = (plus_dm_smooth / tr_smooth.replace(0, np.nan)) * 100.0
    minus_di = (minus_dm_smooth / tr_smooth.replace(0, np.nan)) * 100.0
    
    dx = (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan) * 100.0
    adx_series = dx.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    return adx_series.fillna(25.0)


def bollinger_bands(close: pd.Series, period: int = 20, nbdev: float = 2.0):
    """Bollinger Bands: Upper, Middle, Lower, Width and %B."""
    if HAS_TALIB:
        upper, middle, lower = talib.BBANDS(close.values.astype(float), timeperiod=period, nbdevup=nbdev, nbdevdn=nbdev)
        u, m, l = pd.Series(upper, index=close.index), pd.Series(middle, index=close.index), pd.Series(lower, index=close.index)
    else:
        m = close.rolling(period).mean()
        std = close.rolling(period).std(ddof=0)
        u = m + nbdev * std
        l = m - nbdev * std

    width = (u - l) / m.replace(0, np.nan)
    pct_b = (close - l) / (u - l).replace(0, np.nan)
    return u, m, l, width, pct_b


def ema(close: pd.Series, span: int) -> pd.Series:
    """Exponential Moving Average."""
    if HAS_TALIB:
        res = talib.EMA(close.values.astype(float), timeperiod=span)
        return pd.Series(res, index=close.index)
    return close.ewm(span=span, adjust=False).mean()


def compute_all_ta(df: pd.DataFrame) -> pd.DataFrame:
    """Computes technical indicators on a DataFrame containing open, high, low, close, volume."""
    c = df["close"]
    h = df["high"]
    l = df["low"]
    v = df["volume"]

    features = pd.DataFrame(index=df.index)

    # Momentum
    features["rsi_14"] = rsi(c, 14)
    features["rsi_7"] = rsi(c, 7)
    
    macd_val, macd_sig, macd_hist = macd(c, 12, 26, 9)
    features["macd"] = macd_val / c
    features["macd_sig"] = macd_sig / c
    features["macd_hist"] = macd_hist / c

    # Volatility & Trend
    atr_14 = atr(h, l, c, 14)
    features["atr_14"] = atr_14
    features["natr_14"] = (atr_14 / c) * 100.0
    features["adx_14"] = adx(h, l, c, 14)

    _, _, _, bb_width, bb_pct_b = bollinger_bands(c, 20, 2.0)
    features["bb_width"] = bb_width
    features["bb_pct_b"] = bb_pct_b

    # Moving Average Distance Ratios
    for span in [9, 21, 50, 200]:
        ema_val = ema(c, span)
        features[f"ema_ratio_{span}"] = (c / ema_val) - 1.0

    # Returns & Momentum
    features["ret_1"] = c.pct_change(1)
    features["ret_4"] = c.pct_change(4)
    features["ret_12"] = c.pct_change(12)
    features["ret_24"] = c.pct_change(24)

    # Volume Ratios
    vol_sma_20 = v.rolling(20).mean()
    features["volume_ratio_20"] = v / vol_sma_20.replace(0, np.nan)

    # Candlestick Anatomy
    body = (c - df["open"]).abs()
    candle_range = (h - l).replace(0, np.nan)
    features["body_to_range"] = body / candle_range
    features["upper_wick_ratio"] = (h - df[["open", "close"]].max(axis=1)) / candle_range
    features["lower_wick_ratio"] = (df[["open", "close"]].min(axis=1) - l) / candle_range

    return features

