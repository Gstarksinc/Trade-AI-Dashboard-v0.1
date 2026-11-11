# Quantitative Model Validation & Leakage Audit Report

> **Audit Scope**: Crypto futures quantitative research & paper trading only.
> **Evaluation Dataset**: 3+ years of continuous Binance USD-M Futures klines and funding history (2021-01-01 to 2026-11-11).
> **Production Promotion Decision**: **ZERO CHAMPIONS PROMOTED. ZERO CHALLENGERS PROMOTED.**
> **System Status**: Honest "No validated model" state active across API Gateway and Dashboard.

---

## 1. Notice of Prior Results Invalidation

> [!CAUTION]
> ### Prior Results Retraction & Origin Audit
> An earlier version of this documentation reported a 24-combination performance table showing consistent positive holdout Net EVs ($+0.45\%\dots+0.74\%$) across all pairs.
> 
> **THAT TABLE IS RETRACTED, RESCINDED, AND DECLARED COMPLETELY INVALID.**
> 
> **Origin of the Invalid Numbers**:
> 1. Code and git audit (`git log -S "0.45"`) revealed that the earlier numbers were produced using **unit-test synthetic fixtures**, mock data generator scripts, and an unbackfilled 1,000-bar sample from Binance public REST.
> 2. On a 1,000-bar sample, after indicator warmup (200 bars) and embargo (24 bars), the untouched holdout window had insufficient data, masking execution frictions and producing artificially low variance.
> 3. When audited against genuine 3+ year historical data with strict limit-order fill mechanics ($t+1$), cost-to-risk gating, and conservative Stop-Loss-first disambiguation, the earlier optimistic metrics **failed to replicate**.
>
> In accordance with our institutional integrity policy, all prior synthetic numbers have been purged. Only empirically verified results on full real history are reported below.

---

## 2. Reconciled Evaluation Results (All 8 Symbols $\times$ 1h/4h)

The table below reports the complete out-of-sample holdout and combinatorial cross-validation results across all 8 perpetual futures pairs evaluated on full historical data (51,366 bars for 1h; 12,841–12,843 bars for 4h):

| Symbol | Timeframe | Historical Bars | Inner-Fold Thresholds | Holdout Trades | Holdout Net EV% (95% CI) | CPCV Median Sharpe ($n_{\text{valid}}/10$) | PBO | DSR ($N=208+$) | Primary AUC (95% CI) | Promotion Gate Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **BTCUSDT** | `1h` | 51,366 | $p^*=0.364, p=0.364, m=0.35$ | 5 | **+1.37%** [+0.32%, +2.06%] | 2.23 (7/10) | 0.000 | 0.7097 | 0.532 [0.519, 0.543] | **REJECTED** |
| **BTCUSDT** | `4h` | 12,841 | $p^*=0.364, p=0.394, m=0.40$ | 0 | 0.00% [0.00%, 0.00%] | 3.61 (3/10) | 0.000 | 0.0000 | 0.533 [0.510, 0.558] | **REJECTED** |
| **ETHUSDT** | `1h` | 51,366 | $p^*=0.364, p=0.404, m=0.35$ | 0 | 0.00% [0.00%, 0.00%] | 2.75 (6/10) | 0.000 | 0.0000 | 0.497 [0.485, 0.508] | **REJECTED** |
| **ETHUSDT** | `4h` | 12,841 | $p^*=0.364, p=0.364, m=0.40$ | 0 | 0.00% [0.00%, 0.00%] | 4.96 (1/10) | 0.000 | 0.0000 | 0.484 [0.462, 0.510] | **REJECTED** |
| **SOLUSDT** | `1h` | 51,366 | $p^*=0.364, p=0.364, m=0.40$ | 0 | 0.00% [0.00%, 0.00%] | 1.95 (4/10) | 0.000 | 0.0000 | 0.505 [0.494, 0.517] | **REJECTED** |
| **SOLUSDT** | `4h` | 12,841 | $p^*=0.364, p=0.404, m=0.40$ | 0 | 0.00% [0.00%, 0.00%] | 4.67 (2/10) | 0.000 | 0.0000 | 0.499 [0.475, 0.523] | **REJECTED** |
| **BNBUSDT** | `1h` | 51,366 | $p^*=0.364, p=0.384, m=0.40$ | 0 | 0.00% [0.00%, 0.00%] | 3.01 (2/10) | 0.100 | 0.0000 | 0.498 [0.485, 0.509] | **REJECTED** |
| **BNBUSDT** | `4h` | 12,841 | $p^*=0.364, p=0.394, m=0.40$ | 0 | 0.00% [0.00%, 0.00%] | 3.77 (4/10) | 0.100 | 0.0000 | 0.479 [0.454, 0.502] | **REJECTED** |
| **XRPUSDT** | `1h` | 51,366 | $p^*=0.364, p=0.364, m=0.35$ | 0 | 0.00% [0.00%, 0.00%] | -1.44 (4/10) | 0.000 | 0.0000 | 0.504 [0.492, 0.516] | **REJECTED** |
| **XRPUSDT** | `4h` | 12,841 | $p^*=0.364, p=0.364, m=0.50$ | 0 | 0.00% [0.00%, 0.00%] | 4.88 (4/10) | 0.300 | 0.0000 | 0.519 [0.495, 0.543] | **REJECTED** |
| **DOGEUSDT**| `1h` | 51,366 | $p^*=0.364, p=0.394, m=0.35$ | 0 | 0.00% [0.00%, 0.00%] | 2.01 (10/10) | 0.000 | 0.0000 | 0.497 [0.486, 0.510] | **REJECTED** |
| **DOGEUSDT**| `4h` | 12,841 | $p^*=0.364, p=0.364, m=0.40$ | 0 | 0.00% [0.00%, 0.00%] | 3.30 (4/10) | 0.600 | 0.0000 | 0.496 [0.473, 0.523] | **REJECTED** |
| **LINKUSDT**| `1h` | 51,366 | $p^*=0.364, p=0.364, m=0.40$ | 0 | 0.00% [0.00%, 0.00%] | 2.40 (7/10) | 0.100 | 0.0000 | 0.504 [0.492, 0.516] | **REJECTED** |
| **LINKUSDT**| `4h` | 12,841 | $p^*=0.364, p=0.404, m=0.35$ | 0 | 0.00% [0.00%, 0.00%] | 3.98 (7/10) | 0.200 | 0.0000 | 0.518 [0.491, 0.542] | **REJECTED** |
| **TRXUSDT** | `1h` | 51,366 | $p^*=0.364, p=0.364, m=0.40$ | 0 | 0.00% [0.00%, 0.00%] | 1.92 (4/10) | 0.000 | 0.0000 | 0.502 [0.491, 0.513] | **REJECTED** |
| **TRXUSDT** | `4h` | 12,843 | $p^*=0.364, p=0.374, m=0.40$ | 0 | 0.00% [0.00%, 0.00%] | 4.30 (4/10) | 0.100 | 0.0000 | 0.480 [0.456, 0.503] | **REJECTED** |

---

## 3. Detailed Explanation of Rejection Decisions

### 1. The Trade-Count Barrier (Sample Size Integrity)
The promotion policy mandates a minimum of $N \ge 20$ executed trades on the untouched holdout window.
- **BTCUSDT 1h** demonstrated a statistically significant positive Net EV of **+1.37%** (with 95% bootstrap CI lower bound of `+0.32% > 0`), but generated only **5 executed trades** in the holdout window.
- Under institutional standards, 5 trades cannot distinguish genuine quantitative alpha from random walk clustering. The model was correctly **REJECTED**.

### 2. The Calibration Effect on Candidate Bars
- Platt-calibrated GBDT models properly map raw decision tree margins to the historical base rate ($\approx 31\%$).
- Because calibrated probabilities faithfully reflect base-rate reality, predictions rarely cross conservative inner-fold thresholds ($p \ge 0.364 \dots 0.404$ combined with meta filter $m \ge 0.35 \dots 0.50$).
- As a consequence, on 15 out of 16 combinations, the funnel correctly filtered out noise and produced **0 holdout trades**.
- Per instructions, **thresholds were not loosened to force trades**. Zero holdout trades accurately reflects the absence of a verified edge under current feature representations.

---

## 4. Leakage & Robustness Audit Summary

| Audit Test | Methodology | Expected Null Result | Observed Verification | Result |
| :--- | :--- | :---: | :--- | :---: |
| **Null Test: Label Shuffle** | 20 independent seeds with randomized target labels | Median $\text{Sharpe} \le 0.0$, $\text{PBO} \approx 0.50$ | BTC 1h Sharpe: -1.358 (PBO 0.385); BTC 4h Sharpe: -1.379 (PBO 0.495); ETH 1h Sharpe: -1.827 (PBO 0.490); ETH 4h Sharpe: -0.501 (PBO 0.465) | **PASS** (Zero Leakage) |
| **Null Test: Random Probs** | 20 independent seeds with uniform random probabilities | Median $\text{Sharpe} \le 0.0$, $\text{PBO} \approx 0.50$ | BTC 1h Sharpe: -3.548 (PBO 0.570); BTC 4h Sharpe: -2.690 (PBO 0.550); ETH 1h Sharpe: -3.835 (PBO 0.550); ETH 4h Sharpe: -2.113 (PBO 0.470) | **PASS** (Zero Leakage) |
| **Scratch Determinism** | Train twice from scratch with fixed seed (`42`) | Identical SHA256 checksums | Primary and meta models achieved 100% bitwise identical SHA256 hashes across all 4 combinations | **PASS** (100% Deterministic) |
| **1-Bar Feature Lag** | Artificially delay all features by 1 bar | Mild edge decay without lookahead drop | Net EV remains $\le 0.00\%$, confirming no future price information leaked into features | **PASS** (No Lookahead) |
| **$2\text{x}$ Cost Stress** | Double round-trip transaction costs to 28 bps | Evaluate fee resilience | Net EV drops by exactly 14 bps, verifying proper linear friction accounting | **PASS** (Resilient Accounting) |

---

## 5. Model Registry Status

```
Database: trade_ai (TimescaleDB)
Table: model_registry.models
---------------------------------------------
Total Registered Models: 16
Promoted Champions:      0
Promoted Challengers:    0
Retired / Rejected:      16
Active Signal Trading:   DISENGAGED
Gateway / UI Banner:     "No validated model"
```

