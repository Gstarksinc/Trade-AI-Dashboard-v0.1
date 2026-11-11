# ADR 008: Nested Cross-Validation & Inner-Fold Threshold Optimization

## Status
Accepted

## Context
Tuning probability decision thresholds or meta-model confidence filters on the holdout evaluation set is a severe form of data snooping and lookahead leakage. It inflates reported metrics and guarantees real-world forward degradation.

## Decision
1. Mathematically derive the base break-even probability threshold $p^* = \frac{\text{SL} + \text{cost}}{\text{TP} + \text{SL}}$ from each bar's ATR%.
2. Perform grid optimization of probability and meta-model thresholds **strictly inside the inner training folds** of Combinatorial Purged Cross-Validation (`c_tr_idx`).
3. Freeze the selected inner threshold parameters and apply them untouched to out-of-fold and final holdout testing.

## Consequences
- **Positive**: Complete elimination of threshold snooping bias; guarantees zero holdout information leakage.
- **Negative**: Selected thresholds are more conservative, yielding fewer executed holdout trades.
