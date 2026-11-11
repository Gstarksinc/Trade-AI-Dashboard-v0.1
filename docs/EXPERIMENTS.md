# Quantitative Experiment & Trial Registry

This registry tracks every model architecture, hyperparameter combination, and threshold search variant evaluated across the Trade AI Dashboard project. Under Marcos López de Prado's Deflated Sharpe Ratio (DSR), the expected maximum Sharpe ratio under the null hypothesis of no skill increases with the number of independent trials. Therefore, **the DSR trial count ($N$) is dynamically derived directly from this registry**.

---

## Trial Count Summary

| Phase / Batch | Description | Architecture / Candidates | Total Trials |
| :--- | :--- | :--- | :---: |
| **Phase 3.1 Grid** | Initial CPCV GBDT parameter sweeps (depth, lr, subsample) | LightGBM + PurgedKFold | 50 |
| **Phase 3.1 Gating** | Initial static threshold grid ($p \in [0.50, 0.70]$, $m \in [0.40, 0.60]$) | GBDT probability & meta gates | 50 |
| **Phase 6.5 Re-Audit** | Clean-seed reproducibility runs ($s \in \{42, 123, 999\}$ across 8 assets) | CalibratedClassifierCV + RF meta | 48 |
| **Phase 6.6 Reconciliation** | Unified evaluation threshold calibration around $p^*$ | Sigmoid calibrated GBDT + RF | 30 |
| **Phase 6.7 Dynamic Gates** | Per-setup break-even $p^*_i$ dynamic grid ($p^* \pm 0.04 \times m \in [0.25, 0.50]$) | CalibratedClassifierCV + RF meta | 30 |
| **Total Registered Trials ($N_{\text{trials}}$)** | **Cumulative independent trials tested across all phases** | — | **208** |

---

## Detailed Experiment Log

| Experiment ID | Phase | Date (UTC) | Symbol | TF | Model Family | Hyperparameters / Thresholds Tried | Trials | Status / Gate Result |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- | :---: | :---: |
| `EXP-001-050` | 3.1 | 2026-11-09 | BTC, ETH | 1h, 4h | LightGBM | $n \in \{50, 80, 100, 150\}$, depth $\in \{3, 4, 5\}$, lr $\in \{0.03, 0.05, 0.10\}$ | 50 | Rejected (Lookahead & leak audit failed) |
| `EXP-051-100` | 3.1 | 2026-11-09 | BTC, ETH | 1h, 4h | RF Meta | $p_{\text{thresh}} \in [0.50, 0.70]$ (10 steps), $m_{\text{thresh}} \in [0.40, 0.60]$ (5 steps) | 50 | Rejected (Uncalibrated raw probabilities) |
| `EXP-101-148` | 6.5 | 2026-11-10 | 8 Perpetuals | 1h, 4h | Calibrated GBDT | Seeds 42, 123, 999 on 3+ years full history; 2x cost stress (28 bps) | 48 | Rejected (Insufficient holdout trades $\ge 100$) |
| `EXP-149-178` | 6.6 | 2026-11-11 | BTC, ETH | 1h, 4h | Calibrated + RF | Inner-fold selection: $p \in [0.364, 0.404]$ (5 steps), $m \in [0.25, 0.50]$ (6 steps) | 30 | Rejected (Lower EV CI bound $< 0$) |
| `EXP-179-208` | 6.7 | 2026-11-11 | BTC, ETH | 1h, 4h | Calibrated + RF | Per-setup $p^*_i$ dynamic grid: $p^* \pm [0.00, 0.04]$ (5 steps) $\times m \in \{0.25, 0.28, 0.30, 0.35, 0.40, 0.50\}$ (6 steps) | 30 | Rejected (Zero models promoted; honest baseline) |

---

## Dynamic DSR Derivation Rule

1. The function `evaluator.py::get_dsr_trial_count()` parses `docs/EXPERIMENTS.md` for the registered total trials count.
2. If `docs/EXPERIMENTS.md` is present, it dynamically extracts the exact total trial count (currently **208**).
3. If overridden via environment variable `DSR_TRIALS`, that explicit value is used and logged.
4. Formula for Bailey & López de Prado DSR:
   $$\text{DSR} = \Phi\left(\frac{(\widehat{\text{SR}} - \text{SR}^*) \sqrt{T-1}}{\sqrt{1 - \widehat{\gamma}_3 \widehat{\text{SR}} + \frac{\widehat{\gamma}_4 - 1}{4}\widehat{\text{SR}}^2}}\right)$$
   where:
   $$\text{SR}^* = \sqrt{2 \ln(N_{\text{trials}})} \left(1 - \frac{\gamma}{\sqrt{2 \ln(N_{\text{trials}})}}\right) + \frac{\text{Euler-Mascheroni}}{\sqrt{2 \ln(N_{\text{trials}})}}$$
   with $N_{\text{trials}} = 208$.
