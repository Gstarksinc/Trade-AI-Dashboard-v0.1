# Quantitative Experiment & Trial Registry

This registry tracks every model architecture, hyperparameter combination, and threshold search variant evaluated across the Trade AI Dashboard project. Under Marcos López de Prado's Deflated Sharpe Ratio (DSR), the expected maximum Sharpe ratio under the null hypothesis of no skill increases with the number of independent trials. Therefore, **the DSR trial count ($N$) is dynamically derived directly from the `model_registry.experiments` database table**.

---

## Trial Count Summary

| Source Database Table | Total Registered Trials ($N_{\text{trials}}$) | Last Synced (UTC) |
| :--- | :---: | :---: |
| `model_registry.experiments` | **208** | 2026-11-11 12:28:41 |

---

## Registered Historical Batches

| Batch Range | Phase | Symbol | TF | Model Family / Strategy | Candidate Grid | Trials | Status / Gate Result |
| :--- | :---: | :---: | :---: | :--- | :--- | :---: | :---: |
| `EXP-001` - `EXP-050` | 3.1 | BTC, ETH | 1h, 4h | LightGBM GBDT | GBDT parameter sweep (depth, lr, estimators) | 50 | Rejected (Lookahead audit failed) |
| `EXP-051` - `EXP-100` | 3.1 | BTC, ETH | 1h, 4h | RF Meta | Static threshold grid search | 50 | Rejected (Uncalibrated probabilities) |
| `EXP-101` - `EXP-148` | 6.5 | 8 Perpetuals | 1h, 4h | Calibrated GBDT | 3 clean seeds (42, 123, 999) + 2x cost stress | 48 | Rejected (Insufficient holdout trades) |
| `EXP-149` - `EXP-178` | 6.6 | BTC, ETH | 1h, 4h | Calibrated + RF | Inner-fold selection around p* | 30 | Rejected (Lower EV CI bound < 0) |
| `EXP-179` - `EXP-208` | 6.7 | BTC, ETH | 1h, 4h | Calibrated + RF | Per-setup dynamic p*_i break-even grid | 30 | Rejected (Zero models promoted) |

---

## Dynamic DSR Derivation Rule

1. The function `evaluator.py::get_dsr_trial_count()` directly queries `SELECT COUNT(*) FROM model_registry.experiments`.
2. Current dynamic trial count in database: **208**.
3. Formula for Bailey & López de Prado DSR:
   $$\text{DSR} = \Phi\left(\frac{(\widehat{\text{SR}} - \text{SR}^*) \sqrt{T-1}}{\sqrt{1 - \widehat{\gamma}_3 \widehat{\text{SR}} + \frac{\widehat{\gamma}_4 - 1}{4}\widehat{\text{SR}}^2}}\right)$$
   where:
   $$\text{SR}^* = \sqrt{2 \ln(208)} \left(1 - \frac{\gamma}{\sqrt{2 \ln(208)}}\right) + \frac{\text{Euler-Mascheroni}}{\sqrt{2 \ln(208)}}$$
   with $N_{\text{trials}} = 208$.
