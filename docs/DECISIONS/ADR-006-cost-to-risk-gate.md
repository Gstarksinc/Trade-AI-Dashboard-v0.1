# ADR 006: 20% Cost-to-Risk Gate and 15m Timeframe Suppression

## Status
Accepted

## Context
High-frequency cryptocurrency trading incurs fixed exchange trading fees (Binance VIP0: 2 bps maker, 5 bps taker) and bid-ask slippage (round-trip friction $\approx 14\text{ bps}$). On lower timeframes such as 15m, average true range (ATR) stops are frequently tight (e.g., $0.30\% - 0.60\%$). When fixed friction consumes a large percentage of the stop distance, trading becomes mathematically negative expectation regardless of model accuracy.

## Decision
1. Implement a **Max Cost-to-Risk Ratio Gate** in `risk-service` and evaluation pipelines:
   $$\frac{\text{Round-Trip Friction}}{\text{Stop Distance}} \le 20.0\%$$
   Any trade setup where friction exceeds 20% of the stop-loss distance is rejected immediately.
2. Formally disable all `15m` trading pairs across the platform.

## Consequences
- **Positive**: Protects capital from churn and fee drag; eliminates low-expectation setups.
- **Negative**: Suppresses high-frequency trade signals on lower timeframes.
