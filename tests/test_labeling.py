"""Unit tests for triple-barrier labeling and meta-labeling."""
import unittest
import numpy as np
import pandas as pd

from labeling.triple_barrier import apply_triple_barrier
from labeling.meta_labeling import compute_meta_labels


class LabelingTests(unittest.TestCase):
    def setUp(self):
        # Create an artificial trending price series: rises, then falls
        n = 50
        dates = pd.date_range('2024-01-01', periods=n, freq='1h', tz='UTC')
        prices = [100.0]
        for i in range(1, 20):
            prices.append(prices[-1] + 2.0)  # Strong uptrend
        for i in range(20, n):
            prices.append(prices[-1] - 1.5)  # Downtrend

        self.df = pd.DataFrame({
            'open_time': dates,
            'open': prices,
            'high': [p + 1.0 for p in prices],
            'low': [p - 1.0 for p in prices],
            'close': prices,
            'atr_14': [1.5] * n,
        }).set_index('open_time')

    def test_triple_barrier_detects_take_profit(self):
        labels = apply_triple_barrier(self.df, pt_multiplier=1.5, sl_multiplier=1.5, max_holding_bars=10)
        self.assertEqual(len(labels), len(self.df))
        self.assertIn('label', labels.columns)
        self.assertIn('return_pct', labels.columns)
        self.assertIn('barrier', labels.columns)
        
        # In early uptrend candles, take profit (+1) should be hit first
        first_five = labels['label'].iloc[:5]
        self.assertTrue((first_five == 1).any())

    def test_meta_labeling_logic(self):
        predictions = pd.Series([1, 1, -1, -1], index=pd.date_range('2024-01-01', periods=4, freq='1h'))
        realized_returns = pd.Series([0.03, -0.02, -0.03, 0.02], index=predictions.index)

        meta = compute_meta_labels(predictions, realized_returns, fee_pct=0.0005, slippage_pct=0.0002)
        
        # Trade 1: Long and return is +3% -> Profitable -> Meta label 1
        self.assertEqual(meta['meta_label'].iloc[0], 1)
        # Trade 2: Long and return is -2% -> Loss -> Meta label 0
        self.assertEqual(meta['meta_label'].iloc[1], 0)
        # Trade 3: Short and price dropped -3% -> Profitable short -> Meta label 1
        self.assertEqual(meta['meta_label'].iloc[2], 1)
        # Trade 4: Short and price rose +2% -> Loss on short -> Meta label 0
        self.assertEqual(meta['meta_label'].iloc[3], 0)


if __name__ == '__main__':
    unittest.main()
