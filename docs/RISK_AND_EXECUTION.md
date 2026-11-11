# Risk Management & Paper Execution Engine

> **Scope**: Crypto futures paper trading & research only. Strictly zero real order execution and zero exchange private keys.
> **Source of Truth**: [`libs/common/risk_rules.py`](file:///libs/common/risk_rules.py), [`services/risk-service/`](file:///services/risk-service/), and [`services/paper-exec-service/`](file:///services/paper-exec-service/).

---

## 1. Capital Allocation & Position Sizing Formula

The platform utilizes **Fixed-Fractional ATR Risk Sizing**. Position sizing is determined exclusively by the volatility distance to the stop-loss barrier, guaranteeing that every setup risks an identical fraction of account equity regardless of market volatility.

### Sizing Equation:
$$\text{Risk USD} = \text{Virtual Equity} \times \text{Risk\%}$$
$$\text{Stop Distance \%} = \frac{|\text{Entry Price} - \text{Stop Loss Price}|}{\text{Entry Price}} = \frac{1.0 \times \text{ATR}_{14}}{\text{Entry Price}}$$
$$\text{Position Size USD} = \min\left(\frac{\text{Risk USD}}{\text{Stop Distance \%}}, \text{Virtual Equity} \times \text{Leverage Cap}\right)$$
$$\text{Base Asset Quantity} = \frac{\text{Position Size USD}}{\text{Entry Price}}$$

### Standard Parameters:
- **Default Equity Risk per Trade**: `0.5%` (`risk_pct = 0.005`)
- **Maximum Leverage Cap**: `3.0x` (`leverage_cap = 3.0`)
- **Default Virtual Equity**: `$10,000.00 USD`

---

## 2. Portfolio Caps & Correlated Cluster Exposure

To guard against systemic flash crashes across crypto markets, `risk-service` enforces aggregate portfolio constraints:

1. **Total Portfolio Margin Cap**:
   $$\sum_{i} \text{Used Margin}_i \le 100\% \text{ of Total Equity}$$
2. **Correlated Cluster Exposure Cap**:
   Assets are categorized into risk correlation clusters (e.g. Major DeFi, Layer 1, Meme). The aggregate margin assigned to any single cluster cannot exceed `30.0%`:
   $$\sum_{i \in \text{Cluster}} \text{Used Margin}_i \le 30.0\% \text{ of Total Equity}$$
3. **Single-Symbol Position Limit**:
   Only one active signal or paper position per symbol/timeframe is permitted at any given time.

---

## 3. Atomic Advisory Lock Reservation (`RISK_ADVISORY_LOCK_ID`)

In a distributed environment where multiple prediction events arrive simultaneously across different perpetual pairs, naive margin checks create race conditions.

To guarantee atomicity, `risk-service` serializes portfolio exposure checks and capital reservations using a PostgreSQL transaction-level advisory lock:

```python
async with engine.begin() as conn:
    # 1. Acquire transaction-level advisory lock
    await conn.execute(text("SELECT pg_advisory_xact_lock(:lock_id);"), {"lock_id": 888888})
    
    # 2. Query live account state & sum active reservations
    equity, used_margin, active_positions = await get_account_state(conn)
    
    # 3. Evaluate risk rules and cluster caps
    if used_margin + candidate_margin > max_portfolio_margin:
        return False, {}, "Portfolio margin limit exceeded"
        
    # 4. Insert reservation atomically within the same transaction
    await reserve_margin(conn, symbol, candidate_margin)
    
    # 5. Lock is automatically released on transaction commit
```

---

## 4. Circuit Breakers & Inactivity Halts

| Circuit Breaker | Threshold | Unit | Action Triggered | Recovery / Reset |
| :--- | :---: | :---: | :--- | :--- |
| **Daily Loss Limit** | `3.0%` | Rolling 24-Hour Equity | Halts all new signal approvals | Automatically resets after 24 hours without further breach |
| **Max Trailing Drawdown** | `10.0%` | High-Water Mark Equity | Emergency circuit breaker trip; rejects all signals | Requires manual administrator review & reset |
| **Max Cost-to-Risk Gate** | `20.0%` | Ratio: $\frac{\text{Round-Trip Friction}}{\text{Stop Distance}}$ | Rejects setups where costs erode edge | Evaluated per trade; drops low-volatility / 15m pairs |
| **Feed Latency Breaker** | `15.0` | Seconds since last price tick | Halts approvals; flags status as "degraded" | Automatically resumes when price tick latency $\le 5$s |

---

## 5. Order Fill & Slippage Model

`paper-exec-service` simulates realistic exchange limit and barrier execution:

### Limit Order Entry Mechanics:
- When a signal enters `waiting_for_entry`, a resting limit order is placed at candle close price $C_t$.
- Limit fills are only recognized if the live market price trades strictly through the entry level:
  - **Long Entry**: Fill confirmed when $\text{Low}_{t+k} \le C_t$.
  - **Short Entry**: Fill confirmed when $\text{High}_{t+k} \ge C_t$.
- If unfilled after `limit_wait_bars = 2` bars, the order expires.

### Barrier Exit & Slippage Buffer:
- Exits are evaluated against **Mark Price** to prevent wick stop-outs.
- To simulate finite book depth and adverse order queue priority, barrier triggers require a **5 bps (0.05%) price penetration buffer**:
  - **Take Profit (Long)**: $\text{Mark Price} \ge \text{TP Price} \times (1 + 0.0005)$
  - **Stop Loss (Long)**: $\text{Mark Price} \le \text{SL Price} \times (1 - 0.0005)$
  - **Take Profit (Short)**: $\text{Mark Price} \le \text{TP Price} \times (1 - 0.0005)$
  - **Stop Loss (Short)**: $\text{Mark Price} \ge \text{SL Price} \times (1 + 0.0005)$
- **SL-First Ambiguity Rule**: If both barriers are penetrated within the same tick or bar, Stop Loss is strictly assumed.

---

## 6. Friction, Fees & Continuous Funding Accrual

### Transaction Fees:
Simulates Binance VIP0 USDT-Margined Futures tier:
- **Maker Fee**: `2 bps` ($0.0002$)
- **Taker Fee**: `5 bps` ($0.0005$)
- **Standard Friction Model**: `14 bps` ($0.0014$) round-trip (combines entry maker, exit taker, and conservative adverse selection buffer).

### Funding Rate Accrual:
Funding payments are exchanged every 8 hours on Binance perpetual contracts. During position holding periods, funding accrues continuously:
$$\text{Accrued Funding USD} = \sum_{k} \left(\text{Position Size USD} \times \text{Funding Rate}_k \times \frac{\Delta t}{8\text{h}}\right)$$
- If real funding records are unavailable, a fallback of `1 bp / 8h` ($0.0001$) is accrued.

---

## 7. Realized PnL Calculation & Worked Numeric Example

### Formula:
$$\text{Gross Return \%} = \begin{cases} 
\frac{\text{Exit Price} - \text{Entry Price}}{\text{Entry Price}} & \text{for Long} \\
\frac{\text{Entry Price} - \text{Exit Price}}{\text{Entry Price}} & \text{for Short}
\end{cases}$$

$$\text{Gross PnL USD} = \text{Position Size USD} \times \text{Gross Return \%}$$
$$\text{Total Fees USD} = \text{Position Size USD} \times \text{Round-Trip Fee Rate (0.0014)}$$
$$\text{Net PnL USD} = \text{Gross PnL USD} - \text{Total Fees USD} - \text{Accrued Funding USD}$$
$$\text{Net Return on Capital \%} = \frac{\text{Net PnL USD}}{\text{Risk USD}} \times 100\%$$

---

### Step-by-Step Worked Numeric Verification (Hand-Calculated):

We trace a long BTC trade with virtual equity \$10,000.00:
1. **Inputs**:
   - $\text{Entry Price} = \$50,000.00$
   - $\text{ATR}_{14} = \$1,000.00$ ($2.0\%$)
   - $\text{Target Multiple} = 2.0\text{x ATR} = \$2,000.00 \implies \text{Take Profit} = \$52,000.00$ ($+4.0\%$)
   - $\text{Stop Multiple} = 1.0\text{x ATR} = \$1,000.00 \implies \text{Stop Loss} = \$49,000.00$ ($-2.0\%$)
   - $\text{Risk Target} = 0.5\% \text{ of } \$10,000.00 = \$50.00 \text{ USD}$
2. **Sizing**:
   - $\text{Stop Distance \%} = \frac{\$1,000}{\$50,000} = 0.020$ ($2.0\%$)
   - $\text{Position Size USD} = \frac{\$50.00}{0.020} = \$2,500.00 \text{ USD}$
   - $\text{Quantity} = \frac{\$2,500}{\$50,000} = 0.050 \text{ BTC}$
   - $\text{Effective Leverage} = \frac{\$2,500}{\$10,000} = 0.25\text{x} \le 3.0\text{x}$ (Pass)
3. **Execution at Target Hit**:
   - $\text{Exit Price} = \$52,000.00$
   - $\text{Gross Return \%} = \frac{52,000 - 50,000}{50,000} = +4.000\%$
   - $\text{Gross Profit USD} = \$2,500.00 \times 0.040 = +\$100.00 \text{ USD}$
   - $\text{Round-Trip Fees USD} = \$2,500.00 \times 0.0014 = \$3.50 \text{ USD}$
   - $\text{Accrued Funding USD} = \$0.20 \text{ USD}$
   - $\text{Net PnL USD} = \$100.00 - \$3.50 - \$0.20 = +\$96.30 \text{ USD}$
   - $\text{Net Return on Risk} = \frac{\$96.30}{\$50.00} = +192.6\%$ ($1 : 1.926 \text{ realized R:R}$ after all costs).

