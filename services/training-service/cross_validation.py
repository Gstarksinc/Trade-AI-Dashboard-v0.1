"""Purged and Embargoed Cross-Validation with Scikit-Learn CV compatibility."""

import itertools
from typing import Generator, List, Optional, Tuple
import numpy as np
import pandas as pd


class PurgedKFoldCV:
    """
    Purged and Embargoed K-Fold Cross-Validation implementing sklearn CV interface.
    Guarantees embargo_bars >= max_holding_bars to eliminate post-event serial correlation.
    """
    def __init__(
        self,
        n_splits: int = 5,
        max_holding_bars: int = 24,
        embargo_pct: float = 0.02,
        event_times: Optional[Tuple[pd.Series, pd.Series]] = None,
    ):
        self.n_splits = n_splits
        self.max_holding_bars = max_holding_bars
        self.embargo_pct = embargo_pct
        self.event_times = event_times  # (event_start_times, event_end_times)

    def set_event_times(self, starts: pd.Series, ends: pd.Series):
        self.event_times = (starts, ends)

    def get_n_splits(self, X=None, y=None, groups=None) -> int:
        return self.n_splits

    def split(self, X, y=None, groups=None) -> Generator[Tuple[np.ndarray, np.ndarray], None, None]:
        n = len(X)
        indices = np.arange(n)
        embargo_bars = max(self.max_holding_bars, int(n * self.embargo_pct))
        fold_size = n // self.n_splits

        starts, ends = None, None
        if self.event_times is not None:
            starts, ends = self.event_times
        elif isinstance(X, pd.DataFrame):
            starts = pd.Series(X.index, index=X.index)
            ends = starts

        for i in range(self.n_splits):
            test_start = i * fold_size
            test_end = n if i == self.n_splits - 1 else (i + 1) * fold_size
            test_idx = indices[test_start:test_end]

            train_mask = np.ones(n, dtype=bool)
            train_mask[test_start:test_end] = False

            # Purge overlap before test window if timestamps available
            if starts is not None and ends is not None:
                test_earliest = starts.iloc[test_start]
                overlap_before = (ends >= test_earliest) & (starts < test_earliest)
                train_mask[overlap_before] = False

            # Purge overlap after test window + strictly enforced embargo
            embargo_end = min(n, test_end + embargo_bars)
            train_mask[test_end:embargo_end] = False

            train_idx = indices[train_mask]
            if len(train_idx) > 0 and len(test_idx) > 0:
                yield train_idx, test_idx


class CombinatorialPurgedCV:
    """
    Combinatorial Purged Cross-Validation (CPCV).
    Generates all combinations of test groups with enforced embargo >= max_holding_bars.
    """
    def __init__(
        self,
        n_groups: int = 6,
        k_test_groups: int = 2,
        max_holding_bars: int = 24,
        embargo_pct: float = 0.01,
    ):
        self.n_groups = n_groups
        self.k_test_groups = k_test_groups
        self.max_holding_bars = max_holding_bars
        self.embargo_pct = embargo_pct

    def split(
        self,
        event_start_times: pd.Series,
        event_end_times: pd.Series,
    ) -> Generator[Tuple[np.ndarray, np.ndarray], None, None]:
        n = len(event_start_times)
        indices = np.arange(n)
        group_size = n // self.n_groups
        embargo_bars = max(self.max_holding_bars, int(n * self.embargo_pct))

        groups = []
        for g in range(self.n_groups):
            start = g * group_size
            end = n if g == self.n_groups - 1 else (g + 1) * group_size
            groups.append(indices[start:end])

        for test_combo in itertools.combinations(range(self.n_groups), self.k_test_groups):
            test_idx = np.concatenate([groups[g] for g in test_combo])
            train_mask = np.ones(n, dtype=bool)
            train_mask[test_idx] = False

            for g in test_combo:
                g_start = g * group_size
                g_end = n if g == self.n_groups - 1 else (g + 1) * group_size
                t_earliest = event_start_times.iloc[g_start]

                overlap = (event_end_times >= t_earliest) & (event_start_times < t_earliest)
                train_mask[overlap] = False

                embargo_end = min(n, g_end + embargo_bars)
                train_mask[g_end:embargo_end] = False

            train_idx = indices[train_mask]
            if len(train_idx) > 0 and len(test_idx) > 0:
                yield train_idx, test_idx
