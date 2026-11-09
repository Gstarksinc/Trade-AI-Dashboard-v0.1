'use client';
import { useMemo, useState } from 'react';
import { Money, usePrefs } from '../prefs';
import { fmtPct } from '../../lib/format';
import { TradeLevelBar } from '../components';

/**
 * Dedicated Open Positions View
 * Displays active paper-trading positions with live unrealized P&L, margin, leverage, and position detail modal.
 */
export function PositionsView({ signals = [], onSelectChartSymbol, onSimulateClose, onNavigate }) {
  const [directionFilter, setDirectionFilter] = useState('All');
  const [search, setSearch] = useState('');
  const [selectedPosition, setSelectedPosition] = useState(null);

  // Active positions are confirmed signals whose entry price has been reached (ORDER_IN_PROGRESS)
  const allActivePositions = useMemo(() => {
    return signals.filter((s) => s.is_confirmed && s.metrics?.phase === 'ORDER_IN_PROGRESS');
  }, [signals]);

  // Filter positions
  const filteredPositions = useMemo(() => {
    return allActivePositions.filter((p) => {
      if (directionFilter !== 'All') {
        const isLong = String(p.direction || '').toLowerCase() === 'long';
        if (directionFilter === 'Long' && !isLong) return false;
        if (directionFilter === 'Short' && isLong) return false;
      }
      if (search.trim()) {
        const q = search.trim().toUpperCase();
        if (!String(p.symbol || '').toUpperCase().includes(q)) return false;
      }
      return true;
    });
  }, [allActivePositions, directionFilter, search]);

  return (
    <div className="positions-container">
      {/* Positions Header & Filters */}
      <div className="card positions-card">
        <div className="watchlist-head">
          <div>
            <div className="account-badge-row">
              <span className="account-env-badge">
                <span className="sim-dot" /> ACTIVE SIMULATED TRADES
              </span>
              <span className="sim-disclaimer-pill">ISOLATED MARGIN 3X • ZERO REAL CAPITAL RISK</span>
            </div>
            <h2 className="card-title">Open Paper Positions ({filteredPositions.length})</h2>
            <p className="sub">Real-time marked-to-market positions filled at limit entries with dynamic stop-loss &amp; take-profit monitors</p>
          </div>

          <div className="watchlist-controls">
            <div className="search-wrap">
              <input
                type="text"
                className="search-input"
                placeholder="Filter position symbol..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <div className="pill-group">
              {['All', 'Long', 'Short'].map((d) => (
                <button
                  key={d}
                  className="filter-pill"
                  aria-pressed={directionFilter === d}
                  onClick={() => setDirectionFilter(d)}
                >
                  {d}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Positions Table */}
        <div className="table-container">
          <table className="signals-table positions-table">
            <thead>
              <tr>
                <th>Asset &amp; TF</th>
                <th>Side &amp; Leverage</th>
                <th>Entry Price</th>
                <th>Live Price (CMP)</th>
                <th>Unrealized P&amp;L</th>
                <th>Simulated Margin</th>
                <th>Stop Loss</th>
                <th>Take Profit</th>
                <th style={{ minWidth: '130px' }}>Level Visualizer</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredPositions.map((p) => {
                const isLong = String(p.direction || '').toLowerCase() === 'long';
                const m = p.metrics || {};
                const pnlPct = m.floatingPnlPct || 0;
                const isPnlPos = pnlPct >= 0;
                const simulatedMargin = 500.0; // $500 margin allocation
                const dollarPnl = simulatedMargin * (pnlPct / 100) * 3; // 3x leverage

                return (
                  <tr key={p.id || p.symbol} className="position-row">
                    <td>
                      <div className="sym-cell">
                        <span className="coin-symbol">{String(p.symbol || '').replace('USDT', '')}</span>
                        <span className="sym-meta">
                          <span className="tf-badge">{p.timeframe || '1h'}</span>
                          <span className="sub font-num">PERP</span>
                        </span>
                      </div>
                    </td>

                    <td>
                      <div className="dir-cell">
                        <span className={`dir-badge ${isLong ? 'long' : 'short'}`}>
                          {isLong ? '▲ LONG' : '▼ SHORT'}
                        </span>
                        <span className="leverage-tag">3.0x Isolated</span>
                      </div>
                    </td>

                    <td>
                      <span className="font-num font-bold">
                        <Money value={p.entry} />
                      </span>
                    </td>

                    <td>
                      <div className="cmp-cell">
                        <span className="live-dot pulse" />
                        <span className="cmp-val font-num font-bold">
                          <Money value={p.livePrice} />
                        </span>
                      </div>
                    </td>

                    <td>
                      <div className="pos-pnl-cell">
                        <span className={`pnl-val font-num font-bold ${isPnlPos ? 'pos' : 'neg'}`}>
                          {isPnlPos ? '+' : ''}{pnlPct.toFixed(2)}%
                        </span>
                        <span className={`sub font-num ${isPnlPos ? 'text-tp' : 'text-sl'}`}>
                          ({isPnlPos ? '+' : ''}<Money value={dollarPnl} />)
                        </span>
                      </div>
                    </td>

                    <td>
                      <div className="margin-cell">
                        <span className="font-num font-bold"><Money value={simulatedMargin} /></span>
                        <span className="sub">Notional: <Money value={simulatedMargin * 3} /></span>
                      </div>
                    </td>

                    <td>
                      <div className="level-cell sl-cell">
                        <span className="level-val font-num text-sl"><Money value={p.stop_loss} /></span>
                        <span className="risk-tag">-{fmtPct(m.riskPct, false)}</span>
                      </div>
                    </td>

                    <td>
                      <div className="level-cell tp-cell">
                        <span className="level-val font-num text-tp"><Money value={p.take_profit} /></span>
                        <span className="reward-tag">+{fmtPct(m.rewardPct, false)}</span>
                      </div>
                    </td>

                    <td>
                      <TradeLevelBar metrics={m} />
                    </td>

                    <td>
                      <div className="position-actions-wrap">
                        <button
                          className="calc-btn"
                          onClick={() => onSelectChartSymbol && onSelectChartSymbol(p.symbol)}
                          title="View Chart"
                        >
                          📊 Chart
                        </button>
                        <button
                          className="calc-btn details-btn"
                          onClick={() => setSelectedPosition(p)}
                          title="View Position Details"
                        >
                          🔍 Details
                        </button>
                        <button
                          className="calc-btn close-pos-btn"
                          onClick={() => onSimulateClose && onSimulateClose(p)}
                          title="Simulate Market Exit"
                        >
                          ✕ Exit
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {filteredPositions.length === 0 && (
            <div className="empty-state positions-empty">
              <span className="empty-icon">💼</span>
              <h3 className="empty-title">No Active Positions in Progress</h3>
              <p className="sub pad">
                {signals.filter((s) => s.is_confirmed).length > 0
                  ? 'All confirmed signals are currently waiting for market prices to touch their expected entry limit levels. Once filled, active orders will appear here automatically.'
                  : 'Currently monitoring market conditions across 8 perpetuals for high-probability setups.'}
              </p>
              {onNavigate && (
                <button
                  className="primary-btn empty-action-btn"
                  onClick={() => onNavigate('signals')}
                >
                  📡 View Signals Waiting for Entry
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Position Detail Modal */}
      {selectedPosition && (
        <div className="modal-backdrop" onClick={() => setSelectedPosition(null)}>
          <div className="modal-content pos-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <span className="account-env-badge">
                  <span className="sim-dot" /> SIMULATED POSITION DETAILS
                </span>
                <h3 className="modal-title">
                  {selectedPosition.symbol.replace('USDT', '')} / USDT Perpetual
                </h3>
              </div>
              <button className="modal-close-btn" onClick={() => setSelectedPosition(null)}>
                ✕
              </button>
            </div>

            <div className="modal-body">
              <div className="pos-detail-grid">
                <div className="detail-item">
                  <span className="detail-label">Direction</span>
                  <span className={`dir-badge ${String(selectedPosition.direction).toLowerCase() === 'long' ? 'long' : 'short'}`}>
                    {String(selectedPosition.direction).toLowerCase() === 'long' ? '▲ LONG' : '▼ SHORT'}
                  </span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Timeframe</span>
                  <span className="font-num font-bold">{selectedPosition.timeframe || '1h'}</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Entry Price</span>
                  <span className="font-num font-bold"><Money value={selectedPosition.entry} /></span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Current CMP</span>
                  <span className="font-num font-bold"><Money value={selectedPosition.livePrice} /></span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Unrealized P&amp;L</span>
                  <span className={`font-num font-bold ${(selectedPosition.metrics?.floatingPnlPct || 0) >= 0 ? 'text-tp' : 'text-sl'}`}>
                    {(selectedPosition.metrics?.floatingPnlPct || 0) >= 0 ? '+' : ''}
                    {(selectedPosition.metrics?.floatingPnlPct || 0).toFixed(2)}%
                  </span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Leverage</span>
                  <span className="font-num text-cyan">3.0x Isolated</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Stop Loss Limit</span>
                  <span className="font-num text-sl"><Money value={selectedPosition.stop_loss} /></span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Take Profit Target</span>
                  <span className="font-num text-tp"><Money value={selectedPosition.take_profit} /></span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Risk : Reward Ratio</span>
                  <span className="rr-badge">1 : {(selectedPosition.metrics?.rrRatio || 1).toFixed(1)}</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Estimated Liq Price</span>
                  <span className="font-num text-sl">
                    <Money
                      value={
                        String(selectedPosition.direction).toLowerCase() === 'long'
                          ? selectedPosition.entry * 0.70
                          : selectedPosition.entry * 1.30
                      }
                    />
                  </span>
                </div>
              </div>

              <div className="modal-bar-box">
                <span className="detail-label">Position Progress to Target</span>
                <TradeLevelBar metrics={selectedPosition.metrics} />
              </div>
            </div>

            <div className="modal-footer">
              <button
                className="copy-btn"
                onClick={() => {
                  if (onSelectChartSymbol) onSelectChartSymbol(selectedPosition.symbol);
                  setSelectedPosition(null);
                }}
              >
                📊 Open Chart
              </button>
              <button
                className="calc-btn close-pos-btn"
                onClick={() => {
                  if (onSimulateClose) onSimulateClose(selectedPosition);
                  setSelectedPosition(null);
                }}
              >
                ✕ Simulate Exit Position
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

