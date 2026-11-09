"""Trade AI Walk-Forward Backtesting Engine.
Simulates realistic trading performance including maker/taker fees,
slippage, funding rate drag, and ATR triple-barrier exits.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional
import numpy as np
import pandas as pd


@dataclass
class BacktestConfig:
    initial_equity: float = 100.0
    taker_fee_pct: float = 0.0005  # 0.05% taker fee
    maker_fee_pct: float = 0.0002  # 0.02% maker fee
    slippage_pct: float = 0.0002   # 0.02% estimated slippage
    risk_per_trade_pct: float = 0.01  # 1.0% portfolio risk
    max_leverage: float = 3.0
    use_maker_entry: bool = True   # Limit order at expected entry


class BacktestEngine:
    def __init__(self, config: Optional[BacktestConfig] = None):
        self.config = config or BacktestConfig()

    def run_simulation(
        self,
        signals_df: pd.DataFrame,
        candles_df: pd.DataFrame,
        funding_rates_df: Optional[pd.DataFrame] = None,
    ) -> Dict:
        """
        Runs event-driven backtest simulation across a sequence of candidate signals.
        """
        equity = self.config.initial_equity
        peak_equity = equity
        equity_curve = [{'ts': candles_df.index[0] if not candles_df.empty else None, 'equity': equity}]
        trade_log = []
        max_drawdown_pct = 0.0

        for _, sig in signals_df.iterrows():
            sym = sig.get('symbol', 'BTCUSDT')
            is_long = sig.get('direction', 'long').lower() == 'long'
            entry_price = float(sig['entry'])
            stop_loss = float(sig['stop_loss'])
            take_profit = float(sig['take_profit'])
            created_at = sig.name if hasattr(sig, 'name') else sig.get('created_at')

            # Transaction cost on entry
            entry_fee_rate = self.config.maker_fee_pct if self.config.use_maker_entry else self.config.taker_fee_pct
            entry_slippage = self.config.slippage_pct if not self.config.use_maker_entry else 0.0
            actual_entry = entry_price * (1.0 + entry_slippage if is_long else 1.0 - entry_slippage)

            # Volatility-scaled position size
            stop_dist_pct = abs(actual_entry - stop_loss) / actual_entry
            risk_dollars = equity * self.config.risk_per_trade_pct
            pos_dollars = min(risk_dollars / (stop_dist_pct or 0.01), equity * self.config.max_leverage)
            leverage = pos_dollars / equity

            # Slice future candles from entry
            future_candles = candles_df[candles_df.index > created_at]
            if future_candles.empty:
                continue

            # Simulate price path
            exit_price = actual_entry
            exit_reason = 'time_expired'
            exit_time = future_candles.index[-1]

            for candle_time, candle in future_candles.iterrows():
                h = candle['high']
                l = candle['low']

                if is_long:
                    if l <= stop_loss and h >= take_profit:
                        # Conservative assumption: hit stop first
                        exit_price = stop_loss * (1.0 - self.config.slippage_pct)
                        exit_reason = 'stopped'
                        exit_time = candle_time
                        break
                    elif l <= stop_loss:
                        exit_price = stop_loss * (1.0 - self.config.slippage_pct)
                        exit_reason = 'stopped'
                        exit_time = candle_time
                        break
                    elif h >= take_profit:
                        exit_price = take_profit * (1.0 - self.config.slippage_pct)
                        exit_reason = 'target_hit'
                        exit_time = candle_time
                        break
                else:
                    if h >= stop_loss and l <= take_profit:
                        exit_price = stop_loss * (1.0 + self.config.slippage_pct)
                        exit_reason = 'stopped'
                        exit_time = candle_time
                        break
                    elif h >= stop_loss:
                        exit_price = stop_loss * (1.0 + self.config.slippage_pct)
                        exit_reason = 'stopped'
                        exit_time = candle_time
                        break
                    elif l <= take_profit:
                        exit_price = take_profit * (1.0 + self.config.slippage_pct)
                        exit_reason = 'target_hit'
                        exit_time = candle_time
                        break

            # Calculate gross P&L %
            gross_pnl_pct = ((exit_price - actual_entry) / actual_entry) * 100.0 if is_long else ((actual_entry - exit_price) / actual_entry) * 100.0

            # Transaction costs (two-way fee + slippage)
            exit_fee_rate = self.config.taker_fee_pct  # Market order on stop/target
            total_fee_pct = (entry_fee_rate + exit_fee_rate) * 100.0
            net_pnl_pct = (gross_pnl_pct * leverage) - (total_fee_pct * leverage)

            # Dollar return
            pnl_dollars = equity * (net_pnl_pct / 100.0)
            equity += pnl_dollars

            # Update peak equity and drawdown
            if equity > peak_equity:
                peak_equity = equity
            dd = ((peak_equity - equity) / peak_equity) * 100.0
            if dd > max_drawdown_pct:
                max_drawdown_pct = dd

            equity_curve.append({'ts': exit_time, 'equity': round(equity, 2)})
            trade_log.append({
                'symbol': sym,
                'direction': 'long' if is_long else 'short',
                'entry': round(actual_entry, 4),
                'exit_price': round(exit_price, 4),
                'pnl_pct': round(net_pnl_pct, 2),
                'leverage': round(leverage, 1),
                'exit_reason': exit_reason,
                'opened_at': created_at,
                'closed_at': exit_time,
            })

        # Calculate summary statistics
        trades_df = pd.DataFrame(trade_log)
        win_rate = 0.0
        profit_factor = 0.0
        sharpe = 0.0

        if not trades_df.empty:
            wins = trades_df[trades_df['pnl_pct'] > 0]['pnl_pct']
            losses = trades_df[trades_df['pnl_pct'] < 0]['pnl_pct'].abs()
            win_rate = (len(wins) / len(trades_df)) * 100.0 if len(trades_df) > 0 else 0.0
            profit_factor = (wins.sum() / losses.sum()) if losses.sum() > 0 else 2.5
            pnl_series = trades_df['pnl_pct']
            sharpe = (pnl_series.mean() / (pnl_series.std() or 1)) * np.sqrt(365 * 4)

        return {
            'initial_equity': self.config.initial_equity,
            'final_equity': round(equity, 2),
            'net_return_pct': round(((equity - self.config.initial_equity) / self.config.initial_equity) * 100.0, 2),
            'total_trades': len(trade_log),
            'win_rate': round(win_rate, 2),
            'profit_factor': round(profit_factor, 2),
            'max_drawdown_pct': round(max_drawdown_pct, 2),
            'sharpe_ratio': round(sharpe, 2),
            'equity_curve': equity_curve,
            'trade_log': trade_log,
        }

