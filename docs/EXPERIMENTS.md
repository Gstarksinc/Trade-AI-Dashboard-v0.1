# Quantitative Experiment & Trial Registry

This registry tracks every model architecture, hyperparameter combination, and threshold search variant evaluated across the Trade AI Dashboard project. Under Marcos López de Prado's Deflated Sharpe Ratio (DSR), the expected maximum Sharpe ratio under the null hypothesis of no skill increases with the number of independent trials. Therefore, **the DSR trial count ($N$) is dynamically derived directly from the `model_registry.experiments` database table**.

---

## Trial Count Summary

| Source Database Table | Total Registered Trials ($N_{\text{trials}}$) | Last Synced (UTC) |
| :--- | :---: | :---: |
| `model_registry.experiments` | **223** | 2026-11-11 14:39:43 |

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

## Dynamically Logged Experiments

| ID | Symbol | TF | Model | Prob Thresh | Meta Thresh | Holdout Trades | Net EV % | Sharpe | PBO | DSR | Status |
| :--- | :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `EXP-209` | BTCUSDT | 1h | LGBM-V31-BTCUSDT-1h-20261111130909 | 0.3644 | 0.3500 | 5 | 1.37% | 2.53 | 0.00 | 0.7097 | Evaluated |
| `EXP-210` | BTCUSDT | 4h | LGBM-V31-BTCUSDT-4h-20261111130941 | 0.3944 | 0.4000 | 0 | 0.00% | 0.00 | 0.00 | 0.0000 | Evaluated |
| `EXP-211` | ETHUSDT | 1h | LGBM-V31-ETHUSDT-1h-20261111131128 | 0.4044 | 0.3500 | 0 | 0.00% | 0.00 | 0.00 | 0.0000 | Evaluated |
| `EXP-212` | ETHUSDT | 4h | LGBM-V31-ETHUSDT-4h-20261111131203 | 0.3644 | 0.4000 | 0 | 0.00% | 0.00 | 0.00 | 0.0000 | Evaluated |
| `EXP-213` | SOLUSDT | 1h | LGBM-V31-SOLUSDT-1h-20261111131323 | 0.3644 | 0.4000 | 0 | 0.00% | 0.00 | 0.00 | 0.0000 | Evaluated |
| `EXP-214` | SOLUSDT | 4h | LGBM-V31-SOLUSDT-4h-20261111131332 | 0.4044 | 0.4000 | 0 | 0.00% | 0.00 | 0.00 | 0.0000 | Evaluated |
| `EXP-215` | BNBUSDT | 1h | LGBM-V31-BNBUSDT-1h-20261111131400 | 0.3844 | 0.4000 | 0 | 0.00% | 0.00 | 0.10 | 0.0000 | Evaluated |
| `EXP-216` | BNBUSDT | 4h | LGBM-V31-BNBUSDT-4h-20261111131409 | 0.3944 | 0.4000 | 0 | 0.00% | 0.00 | 0.10 | 0.0000 | Evaluated |
| `EXP-217` | XRPUSDT | 1h | LGBM-V31-XRPUSDT-1h-20261111131440 | 0.3644 | 0.3500 | 0 | 0.00% | 0.00 | 0.00 | 0.0000 | Evaluated |
| `EXP-218` | XRPUSDT | 4h | LGBM-V31-XRPUSDT-4h-20261111131448 | 0.3644 | 0.5000 | 0 | 0.00% | 0.00 | 0.30 | 0.0000 | Evaluated |
| `EXP-219` | DOGEUSDT | 1h | LGBM-V31-DOGEUSDT-1h-20261111131518 | 0.3944 | 0.3500 | 0 | 0.00% | 0.00 | 0.00 | 0.0000 | Evaluated |
| `EXP-220` | DOGEUSDT | 4h | LGBM-V31-DOGEUSDT-4h-20261111131527 | 0.3644 | 0.4000 | 0 | 0.00% | 0.00 | 0.60 | 0.0000 | Evaluated |
| `EXP-221` | LINKUSDT | 1h | LGBM-V31-LINKUSDT-1h-20261111143614 | 0.3644 | 0.4000 | 0 | 0.00% | 0.00 | 0.10 | 0.0000 | Evaluated |
| `EXP-222` | LINKUSDT | 4h | LGBM-V31-LINKUSDT-4h-20261111143714 | 0.4044 | 0.3500 | 0 | 0.00% | 0.00 | 0.20 | 0.0000 | Evaluated |
| `EXP-223` | TRXUSDT | 1h | LGBM-V31-TRXUSDT-1h-20261111143938 | 0.3644 | 0.4000 | 0 | 0.00% | 0.00 | 0.00 | 0.0000 | Evaluated |

---

## Dynamic DSR Derivation Rule

1. The function `evaluator.py::get_dsr_trial_count()` directly queries `SELECT COUNT(*) FROM model_registry.experiments`.
2. Current dynamic trial count in database: **223**.
3. Formula for Bailey & López de Prado DSR:
   $$\text{DSR} = \Phi\left(\frac{(\widehat{\text{SR}} - \text{SR}^*) \sqrt{T-1}}{\sqrt{1 - \widehat{\gamma}_3 \widehat{\text{SR}} + \frac{\widehat{\gamma}_4 - 1}{4}\widehat{\text{SR}}^2}}\right)$$
   where:
   $$\text{SR}^* = \sqrt{2 \ln(223)} \left(1 - \frac{\gamma}{\sqrt{2 \ln(223)}}\right) + \frac{\text{Euler-Mascheroni}}{\sqrt{2 \ln(223)}}$$
   with $N_{\text{trials}} = 223$.
