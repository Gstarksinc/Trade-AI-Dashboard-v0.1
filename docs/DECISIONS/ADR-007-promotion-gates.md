# ADR 007: Strict Multi-Criteria Model Promotion Gates

## Status
Accepted

## Context
Deploying unvalidated machine learning models to production based on naive in-sample backtests leads to immediate capital decay due to backtest overfitting and multiple testing bias.

## Decision
Establish six mandatory, non-negotiable **Promotion Gates** evaluated exclusively on an untouched final holdout window:
1. Minimum Holdout Executed Trades: $N \ge 20$.
2. Positive Net Expected Value: $\text{Net EV} > 0.00\%$ after 14 bps fee and funding accrual.
3. Statistically Significant Edge: 95% bootstrap confidence interval lower bound $> 0.00\%$.
4. Out-of-Sample CPCV Robustness: Combinatorial Purged Cross-Validation median Sharpe $> 0.00$.
5. Overfitting Ceiling: Marcos López de Prado's Probability of Backtest Overfitting $\text{PBO} < 0.50$.
6. Probability Calibration Quality: Expected Calibration Error $\text{ECE} \le 0.12$.

Zero models are promoted to Champion or Challenger if any single gate fails. In such events, the system honestly operates in "No validated model" state with signal execution disengaged.

## Consequences
- **Positive**: Institutional capital preservation; zero tolerance for false discoveries or statistical illusions.
- **Negative**: Currently all 16 tested models fail promotion, leaving live execution disengaged until superior quantitative alpha is discovered.
