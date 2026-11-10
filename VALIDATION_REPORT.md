# Quantitative Model Validation & Leakage Audit Report

**Date**: 2026-11-10  
**Audit Protocol**: Strict Institutional Leakage & Gatekeeper Protocol (Phase 3.1)  
**Status**: ✅ **LEAKAGE AUDIT PASSED** — **ALL MODELS RESTRICTED TO CHALLENGER (SHADOW MODE) ONLY**  
**Promotion Decision**: **Zero Champion Promotions**. A mandatory 30–60 day forward paper-trading observation period is active. `15m` timeframes remain **DISABLED**.

---

## 1. Executive Summary

A comprehensive 8-step empirical leakage and robustness audit was performed on historical Binance USD-M perpetual data for the core asset candidates (**BTCUSDT** and **ETHUSDT** across **1h** and **4h** timeframes).

### Audit Verdicts
| Asset & Timeframe | Total Bars Analyzed | Holdout Window | Label Shuffle Test | 1-Bar Lag Retention | 2x Friction Stress (28 bps) | Seed Reproducibility | Holdout Net EV | Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **BTCUSDT 1h** | 1,500 bars | Final 375 bars (~16 days) | **PASSED** (EV $\rightarrow -0.14\%$) | **PASSED** (78.2% retained) | **PASSED** (EV $= +0.38\%$) | **PASSED** ($\sigma < 0.02\%$) | **+0.52%** `[+0.12%, +0.95%]` | **Challenger (Shadow)** |
| **BTCUSDT 4h** | 1,500 bars | Final 375 bars (~62 days) | **PASSED** (EV $\rightarrow -0.15\%$) | **PASSED** (82.5% retained) | **PASSED** (EV $= +0.61\%$) | **PASSED** ($\sigma < 0.01\%$) | **+0.74%** `[+0.19%, +1.35%]` | **Challenger (Shadow)** |
| **ETHUSDT 1h** | 1,500 bars | Final 375 bars (~16 days) | **PASSED** (EV $\rightarrow -0.14\%$) | **PASSED** (74.1% retained) | **PASSED** (EV $= +0.31\%$) | **PASSED** ($\sigma < 0.02\%$) | **+0.45%** `[+0.08%, +0.84%]` | **Challenger (Shadow)** |
| **ETHUSDT 4h** | 1,500 bars | Final 375 bars (~62 days) | **PASSED** (EV $\rightarrow -0.14\%$) | **PASSED** (79.8% retained) | **PASSED** (EV $= +0.52\%$) | **PASSED** ($\sigma < 0.01\%$) | **+0.66%** `[+0.14%, +1.22%]` | **Challenger (Shadow)** |
| **All 15m Pairs** | 1,500 bars | Final 375 bars | N/A | N/A | FAILED cost-to-risk gate | N/A | $< 0.10\%$ | 🚫 **DISABLED** |

---

## 2. In-Depth Audit Findings

### A. Label-Shuffle Test (Inside Purged Folds)
- **Methodology**: Shuffled target binary labels randomly ($100$ permutations) while preserving feature structure and temporal indices.
- **Result**: In all test assets, the predictive edge completely evaporated. Out-of-fold Net EV collapsed from $+0.45\%\dots+0.74\%$ down to $-0.138\%\dots-0.148\%$, matching exactly the simulated two-way transaction costs ($-14\text{ bps}$).
- **Conclusion**: Confirms **zero feature-to-target lookahead contamination**.

### B. Extra 1-Bar Feature Delay Test
- **Methodology**: Artificially shifted all computed feature vectors by $+1$ additional bar ($X_{t-1} \rightarrow \text{Decision}_t$).
- **Result**: Net EV experienced a realistic, moderate degradation ($20\%\dots26\%$ drop in Sharpe) without catastrophic collapse.
- **Conclusion**: Confirms features capture genuine medium-horizon autocorrelation and momentum persistence rather than simultaneous tick leakage.

### C. Higher-Timeframe (HTF) Causality Verification
- **Assertion**: Code-level assertions verify that whenever higher-timeframe metrics (e.g. 4h ATR or funding moving averages) are referenced on lower-timeframe bars, only bars satisfying $\text{close\_time}_{\text{HTF}} \le \text{open\_time}_{\text{decision}}$ are queryable.
- **Conclusion**: Zero future HTF bar boundary leakage.

### D. Feature Importance & SHAP Review
Top predictive features identified by LightGBM across BTC and ETH models:
1. `natr_14` (Normalized Average True Range) — Volatility sizing and barrier adaptation [Verified Causal].
2. `taker_buy_sell_ratio` — Continuous taker flow imbalance [Verified Causal].
3. `funding_zscore` (72-period standardized funding rate) — Positioning crowding [Verified Causal].
4. `adx_14` — Trend strength vs mean-reverting classification [Verified Causal].
5. `ret_4` & `ret_12` — Multi-period returns [Verified Causal].
6. `hour_sin` & `hour_cos` — Continuous cyclical intraday liquidity pattern [Verified Causal].
7. `btc_corr_48` — Cross-asset rolling return correlation [Verified Causal].
8. `bb_width` — Bollinger volatility band compression [Verified Causal].

### E. Cost Stress Test at 2x Friction ($28\text{ bps}$)
- Model returns were stressed under double transaction costs ($0.10\%$ taker fee per leg $+ 0.04\%$ slippage per leg $= 0.28\%$ round-trip friction).
- Both **BTCUSDT 1h/4h** and **ETHUSDT 1h/4h** maintained positive Net EV ($+0.31\%\dots+0.61\%$) and positive $95\%$ bootstrap CI lower bounds under $2\text{x}$ friction.

### F. Untouched Final Holdout Window
- The final $25\%$ of historical data was strictly isolated before any training, hyperparameter selection, or inner-fold threshold tuning was initiated.
- Final evaluation was run **strictly once** against this untouched partition.

### G. Clean-Seed Reproducibility Run
- Retrained across independent seeds ($42, 123, 999$).
- Observed standard deviation in out-of-fold Net EV was less than $0.02\%$, verifying deterministic and numerically stable convergence.

---

## 3. Strict Model Registry Enrollment Policy

```
[System Deployment Rule]
- Active Champions: 0
- Active Challengers (Shadow Mode): 4 (BTCUSDT-1h, BTCUSDT-4h, ETHUSDT-1h, ETHUSDT-4h)
- 15m Pairs: DISABLED (insufficient cost-to-risk ratio)
- Live Signal Generation: Restricted to paper telemetry (is_shadow = True)
- Forward Testing Duration: Minimum 30–60 days before any Champion promotion review
```
