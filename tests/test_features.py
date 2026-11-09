"""Unit tests for feature engineering."""
import unittest
import numpy as np
import pandas as pd

from features.ta import rsi, macd, atr, bollinger_bands, ema, compute_all_ta
from features.derivatives import compute_derivatives_features
from features.cross_asset import compute_time_features, compute_volatility_regime
from features.builder import build_features


class FeaturesTests(unittest.TestCase):
    def setUp(self):
        np.random.seed(42)
        n = 100
        dates = pd.date_range('2024-01-01', periods=n, freq='1h', tz='UTC')
        prices = 100.0 + np.cumsum(np.random.randn(n) * 2.0)
        self.df = pd.DataFrame({
            'open_time': dates,
            'open': prices,
            'high': prices + np.random.uniform(1.0, 3.0, n),
            'low': prices - np.random.uniform(1.0, 3.0, n),
            'close': prices + np.random.randn(n) * 0.5,
            'volume': np.random.uniform(100, 1000, n),
        })
        self.df.loc[self.df['low'] > self.df['close'], 'low'] = self.df['close'] - 0.5
        self.df.loc[self.df['high'] < self.df['close'], 'high'] = self.df['close'] + 0.5

    def test_rsi_bounds(self):
        res = rsi(self.df['close'], 14)
        self.assertEqual(len(res), len(self.df))
        self.assertTrue((res >= 0.0).all())
        self.assertTrue((res <= 100.0).all())

    def test_macd(self):
        m, s, h = macd(self.df['close'], 12, 26, 9)
        self.assertEqual(len(m), len(self.df))
        self.assertEqual(len(s), len(self.df))
        self.assertEqual(len(h), len(self.df))

    def test_atr_positive(self):
        res = atr(self.df['high'], self.df['low'], self.df['close'], 14)
        self.assertEqual(len(res), len(self.df))
        self.assertTrue((res.dropna() > 0).all())

    def test_bollinger_bands(self):
        u, m, l, width, pct_b = bollinger_bands(self.df['close'], 20, 2.0)
        valid = (u.dropna() >= l.dropna())
        self.assertTrue(valid.all())

    def test_compute_all_ta(self):
        res = compute_all_ta(self.df)
        self.assertIn('rsi_14', res.columns)
        self.assertIn('atr_14', res.columns)
        self.assertIn('bb_width', res.columns)
        self.assertIn('volume_ratio_20', res.columns)

    def test_derivatives_features_empty_graceful(self):
        indexed = self.df.set_index('open_time')
        res = compute_derivatives_features(indexed)
        self.assertIn('funding_rate', res.columns)
        self.assertIn('oi_change_4', res.columns)
        self.assertIn('lsr_ratio', res.columns)

    def test_time_features(self):
        res = compute_time_features(self.df['open_time'])
        self.assertIn('hour_sin', res.columns)
        self.assertIn('hour_cos', res.columns)
        self.assertTrue((res['hour_sin'] >= -1.0).all())
        self.assertTrue((res['hour_sin'] <= 1.0).all())

    def test_build_features_pipeline(self):
        res = build_features(self.df)
        self.assertFalse(res.empty)
        self.assertIn('close', res.columns)
        self.assertIn('rsi_14', res.columns)
        self.assertIn('volatility_regime', res.columns)


if __name__ == '__main__':
    unittest.main()

