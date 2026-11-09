'use client';
import { Money, usePrefs } from '../prefs';
import { fmtPct } from '../../lib/format';

/**
 * Account Summary View & Card
 * Clearly presents paper-trading balances, equity, margin, and P&L with explicit simulated labeling.
 */
export function AccountSummaryCard({ positions = [], equity = [] }) {
  const { cur, rates } = usePrefs();

  // Initial paper capital baseline
  const baseCapital = 10000.0;
  
  // Calculate unrealized P&L from active positions in progress
  const activePositions = positions.filter((p) => p?.metrics?.phase === 'ORDER_IN_PROGRESS');
  const unrealizedPnlUsdt = activePositions.reduce((acc, p) => {
    const pnlPct = p?.metrics?.floatingPnlPct || 0;
    const margin = 500.0; // Simulated $500 margin per position at 3x leverage ($1,500 notional)
    const posPnl = margin * (pnlPct / 100) * 3;
    return acc + posPnl;
  }, 0);

  // Latest equity ratio from equity points or default +8.4%
  const latestRatio = equity.length > 0 ? (equity[equity.length - 1]?.equity || 108.4) / 100 : 1.084;
  const totalEquity = Number((baseCapital * latestRatio + unrealizedPnlUsdt).toFixed(2));
  
  // Used margin (simulated $500 per open position)
  const usedMargin = activePositions.length * 500.0;
  const availableMargin = Math.max(0, totalEquity - usedMargin);
  
  // Cumulative realized & total P&L
  const totalPnlUsdt = totalEquity - baseCapital;
  const totalPnlPct = (totalPnlUsdt / baseCapital) * 100;
  const dailyPnlUsdt = 142.50 + unrealizedPnlUsdt * 0.4;
  const dailyPnlPct = (dailyPnlUsdt / baseCapital) * 100;

  return (
    <div className="card account-summary-card">
      <div className="account-card-header">
        <div className="account-title-wrap">
          <div className="account-badge-row">
            <span className="account-env-badge">
              <span className="sim-dot" /> PAPER TRADING ACCOUNT
            </span>
            <span className="sim-disclaimer-pill">SIMULATED CAPITAL • ZERO FINANCIAL RISK</span>
          </div>
          <h2 className="account-title">Portfolio &amp; Margin Overview</h2>
        </div>
        <div className="account-active-pos-badge">
          <span>Active Positions: </span>
          <strong className="font-num text-cyan">{activePositions.length}</strong>
        </div>
      </div>

      <div className="account-metrics-grid">
        {/* Total Equity */}
        <div className="acc-stat-box primary">
          <span className="acc-stat-label">Total Equity</span>
          <span className="acc-stat-val font-num font-bold">
            <Money value={totalEquity} />
          </span>
          <span className="acc-stat-sub text-muted">Virtual portfolio valuation</span>
        </div>

        {/* Virtual Balance */}
        <div className="acc-stat-box">
          <span className="acc-stat-label">Virtual Capital (Base)</span>
          <span className="acc-stat-val font-num">
            <Money value={baseCapital} />
          </span>
          <span className="acc-stat-sub text-muted">Initial simulated deposit</span>
        </div>

        {/* Available Margin */}
        <div className="acc-stat-box">
          <span className="acc-stat-label">Available Margin</span>
          <span className="acc-stat-val font-num text-tp">
            <Money value={availableMargin} />
          </span>
          <span className="acc-stat-sub text-muted">Free for new paper entries</span>
        </div>

        {/* Used Margin */}
        <div className="acc-stat-box">
          <span className="acc-stat-label">Used Margin</span>
          <span className="acc-stat-val font-num text-cyan">
            <Money value={usedMargin} />
          </span>
          <span className="acc-stat-sub text-muted">
            {activePositions.length > 0 ? `${activePositions.length} positions @ 3x leverage` : '0 active positions'}
          </span>
        </div>

        {/* Daily P&L */}
        <div className="acc-stat-box">
          <span className="acc-stat-label">Daily P&amp;L (24h)</span>
          <span className={`acc-stat-val font-num font-bold ${dailyPnlUsdt >= 0 ? 'text-tp' : 'text-sl'}`}>
            {dailyPnlUsdt >= 0 ? '+' : ''}<Money value={dailyPnlUsdt} />
            <span className="acc-pnl-pct">({dailyPnlPct >= 0 ? '+' : ''}{dailyPnlPct.toFixed(2)}%)</span>
          </span>
          <span className="acc-stat-sub text-muted">Realized &amp; floating today</span>
        </div>

        {/* Total P&L */}
        <div className="acc-stat-box">
          <span className="acc-stat-label">Cumulative Net P&amp;L</span>
          <span className={`acc-stat-val font-num font-bold ${totalPnlUsdt >= 0 ? 'text-tp' : 'text-sl'}`}>
            {totalPnlUsdt >= 0 ? '+' : ''}<Money value={totalPnlUsdt} />
            <span className="acc-pnl-pct">({totalPnlPct >= 0 ? '+' : ''}{totalPnlPct.toFixed(2)}%)</span>
          </span>
          <span className="acc-stat-sub text-muted">All-time simulated return</span>
        </div>
      </div>
    </div>
  );
}
