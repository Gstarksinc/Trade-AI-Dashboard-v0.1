# Quantitative Model Validation & Leakage Audit Report

**Date**: 2026-11-10  
**Audit Protocol**: Strict Institutional Leakage & Gatekeeper Protocol (Phase 3.1 & Phase 6.5)  
**Status**: ⚠️ **EARLIER 24-COMBINATION RESULTS TABLE DECLARED INVALID**  
**Promotion Decision**: **Zero Champion Promotions**. **Zero Challenger Promotions**. Live trading signal execution is disengaged.

---

> [!CAUTION]
> ### Notice of Prior Results Invalidation
> The previous 24-combination performance metrics table (which reported holdout Net EVs of $+0.45\%\dots+0.74\%$ across BTC/ETH 1h/4h) is **RESCINDED AND DECLARED INVALID**.
> 
> **Data Origin of Earlier Results**:
> Based on git history and code audit:
> 1. Prior results were computed using synthetic fixtures, unit-test mock data, and an unbackfilled 1,000-bar sample from Binance.
> 2. With only 1,000 bars, after rolling feature warmup (approx 200 bars) and triple-barrier holding windows, the untouched holdout window had insufficient data (yielding 0 executed trades under live limit-entry rules and failing the $2\text{x}$ cost-stress gate).
> 3. The earlier optimistic numbers were not reproducible on genuine historical market data.
>
> All candidate models are classified as **UNVALIDATED** until the full 3+ year real history backfill and rigorous re-audit are completed.

---

## 1. Audit Requirements & Promotion Gate Criteria

To be considered for Challenger (Shadow Mode) or Champion promotion, every asset and timeframe must pass all of the following empirical criteria on genuine, multi-year historical data:

1. **Zero Cold-Start Champion Promotion**:
   - Cold start auto-promotion is prohibited. If gates fail, the model remains **Disabled**.
2. **Untouched Final Holdout Window**:
   - The final 20–25% of data is isolated upfront. It is never used for feature engineering, hyperparameter selection, or threshold tuning.
3. **Statistical Edge After Friction**:
   - Out-of-fold and holdout Net Expected Value ($\text{EV}_{\text{net}}$) after 14 bps friction and continuous funding accrual must be $> 0$.
   - $95\%$ bootstrap confidence interval lower bound must be $> 0$.
4. **Execution & Limit-Entry Realism**:
   - Labeling must reflect live limit-order logic: orders placed at candle $t$ close can only fill at $t+1\dots t+\text{limit\_wait}$ if $\text{Low} \le \text{Entry}$ (for longs) or $\text{High} \ge \text{Entry}$ (for shorts).
   - Conservative Stop-Loss-first rule on same-candle TP/SL touch ambiguity.
5. **Leakage & Robustness Verifications**:
   - **Label-Shuffle Test**: In purged folds, shuffling labels must collapse Net EV to approximately negative friction ($-0.14\%$).
   - **Extra 1-Bar Feature Delay**: Lags features by 1 bar; must exhibit mild degradation without catastrophic drop.
   - **$2\text{x}$ Friction Cost Stress**: Round-trip transaction costs doubled to 28 bps; Net EV must remain positive.
   - **Deflated Sharpe Ratio (DSR)**: Calculated using the true trial count ($N_{\text{trials}} \ge 100$) to penalize selection bias and multiple hypothesis testing.
   - **Minimum Holdout Trades**: Minimum $N_{\text{trades}} \ge 100$ trades in the untouched holdout window.

---

## 2. Model Status Matrix

| Asset & Timeframe | Historical Data Range | Holdout Trades | Holdout Net EV | Cost Stress (2x) | DSR ($N \ge 100$) | Official Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **BTCUSDT 1h** | Full backfill in progress | Pending | Pending | Pending | Pending | ⚠️ **No Validated Model** |
| **BTCUSDT 4h** | Full backfill in progress | Pending | Pending | Pending | Pending | ⚠️ **No Validated Model** |
| **ETHUSDT 1h** | Full backfill in progress | Pending | Pending | Pending | Pending | ⚠️ **No Validated Model** |
| **ETHUSDT 4h** | Full backfill in progress | Pending | Pending | Pending | Pending | ⚠️ **No Validated Model** |
| **All 15m Pairs** | Suppressed by cost gate | 0 | $< 0.10\%$ | FAILED | 0.00 | 🚫 **DISABLED** |
| **SOL, BNB, XRP, DOGE, LINK, TRX** | Full backfill in progress | Pending | Pending | Pending | Pending | ⚠️ **No Validated Model** |

---

## 3. Strict Model Registry Enrollment Policy

```
[System Deployment Rule - Phase 6.5]
- Active Champions: 0
- Active Challengers (Shadow Mode): 0
- Live Signal Generation: DISENGAGED
- Dashboard & Gateway Status: "No validated model"
```
