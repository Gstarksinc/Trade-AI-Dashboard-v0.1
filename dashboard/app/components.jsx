'use client';
import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { calcTradeMetrics, fmtPct, fmtTime } from '../lib/format';
import { Money, RateNote, Time, usePrefs } from './prefs';

const TIMEFRAMES = ['All', '15m', '1h', '4h'];
const DIRECTIONS = ['All', 'Long', 'Short'];
const STATUS_OPTIONS = ['All', 'In Entry Zone', 'In Trade', 'Pending', 'Target Hit', 'Stopped Out'];
const HISTORY_SPANS = ['Today (24h)', '7 Days', '30 Days', 'All Time'];

export function AutoRefresh({ seconds = 30 }) {
  const router = useRouter();
  useEffect(() => {
    const id = setInterval(() => router.refresh(), seconds * 1000);
    return () => clearInterval(id);
  }, [router, seconds]);
  return null;
}

/**
 * Top Market Ticker Tape showing major crypto futures with live streaming prices
 */
export function MarketTickerTape({ tickers = {} }) {
  const { getPrice } = usePrefs();
  const pairs = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'DOGEUSDT', 'LINKUSDT', 'TRXUSDT'];

  return (
    <div className="ticker-tape">
      <div className="ticker-scroll">
        <div className="ticker-brand-badge">
          <span className="live-dot pulse" />
          <span>BINANCE FUTURES</span>
        </div>
        {pairs.map((sym) => {
          const baseTick = tickers?.[sym] || {};
          const live = getPrice(sym, baseTick.price);
          const price = live?.price || baseTick.price || 0;
          const change = live?.change != null ? live.change : (baseTick.change || 0);
          const isPos = change >= 0;

          return (
            <div key={sym} className={`ticker-item ${live?.tickDir ? `tick-${live.tickDir}` : ''}`}>
              <div className="ticker-sym">
                <span className="sym-name">{sym.replace('USDT', '')}</span>
                <span className="sym-quote">/USDT</span>
              </div>
              <div className="ticker-price-box">
                <span className="ticker-price">
                  <Money value={price} />
                </span>
                <span className={`ticker-change ${isPos ? 'pos' : 'neg'}`}>
                  {isPos ? '▲' : '▼'} {fmtPct(change, false, 2)}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/**
 * Paper Trading Session Controller:
 * Displays Days of Data Available, and provides [Start/Resume] and [Reset Win Rate] buttons.
 */
export function SessionController({ dataDays = 45 }) {
  const { isSessionRunning, toggleSessionRunning, resetWinRate, sessionStats, sessionStartTime, tz } = usePrefs();
  const [showConfirm, setShowConfirm] = useState(false);

  const handleReset = () => {
    resetWinRate();
    setShowConfirm(false);
  };

  return (
    <div className="session-ctrl-bar card">
      <div className="session-left">
        <div className="data-days-box">
          <span className="h">Historical Data Available</span>
          <div className="days-val-row">
            <span className="days-num font-num">{dataDays} Days</span>
            <span className="days-chip">Binance USD-M Candles</span>
          </div>
        </div>

        <div className="session-status-box">
          <span className="h">Live Session Track Record</span>
          <div className="session-status-row">
            <span className={`session-pill ${isSessionRunning ? 'running' : 'paused'}`}>
              <span className={`dot ${isSessionRunning ? 'green' : 'warn'}`} />
              {isSessionRunning ? 'Tracking Active' : 'Tracking Paused'}
            </span>
            <span className="session-start-sub">
              {sessionStats.isReset
                ? `Session restarted at ${fmtTime(sessionStartTime, tz)}`
                : `Active from ${fmtTime(sessionStartTime, tz, true)}`}
            </span>
          </div>
        </div>
      </div>

      <div className="session-actions">
        <button
          className={`tf ctrl-btn ${isSessionRunning ? 'pause-btn' : 'start-btn'}`}
          onClick={toggleSessionRunning}
          title={isSessionRunning ? 'Pause tracking new outcomes' : 'Start/Resume tracking'}
        >
          {isSessionRunning ? '⏸ Pause Session' : '▶ Start Session'}
        </button>

        <button
          className="tf ctrl-btn reset-btn"
          onClick={() => setShowConfirm(true)}
          title="Reset win rate and trade statistics back to 0"
        >
          🔄 Reset Win Rate
        </button>
      </div>

      {showConfirm && (
        <div className="modal-backdrop" onClick={() => setShowConfirm(false)}>
          <div className="modal-content confirm-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Reset Win Rate &amp; Track Record?</h3>
              <button className="close-btn" onClick={() => setShowConfirm(false)}>✕</button>
            </div>
            <div className="modal-body">
              <p>This will reset your paper trading win rate, closed trades count, and net P&amp;L back to <strong>0</strong> so you can measure a fresh tracking run from this moment onward.</p>
              <p className="sub">Your active signals and historical candle database will not be affected.</p>
            </div>
            <div className="modal-footer">
              <button className="tf" onClick={() => setShowConfirm(false)}>Cancel</button>
              <button className="tf reset-confirm-btn" onClick={handleReset}>Yes, Reset to 0</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Visual Progress Bar showing CMP position relative to Stop Loss, Entry, and Take Profit
 */
export function TradeLevelBar({ metrics }) {
  const { progressPct = 35 } = metrics || {};
  const isProfit = progressPct > 35;
  const isLoss = progressPct < 35 && progressPct > 0;

  return (
    <div className="trade-bar-wrap" title={`Position: ${progressPct.toFixed(0)}% (SL: 0%, Entry: 35%, TP: 100%)`}>
      <div className="trade-bar-labels">
        <span className="label-sl">SL</span>
        <span className="label-entry">Entry</span>
        <span className="label-tp">TP</span>
      </div>
      <div className="trade-bar-track">
        <div className="marker-entry" style={{ left: '35%' }} />
        {isProfit && (
          <div
            className="bar-fill profit"
            style={{ left: '35%', width: `${Math.min(65, progressPct - 35)}%` }}
          />
        )}
        {isLoss && (
          <div
            className="bar-fill loss"
            style={{ left: `${progressPct}%`, width: `${Math.max(0, 35 - progressPct)}%` }}
          />
        )}
        <div
          className={`bar-cursor ${isProfit ? 'profit' : isLoss ? 'loss' : 'neutral'}`}
          style={{ left: `${Math.max(2, Math.min(98, progressPct))}%` }}
        />
      </div>
    </div>
  );
}

/**
 * Main Signals & History Panel with Tabs, Filters, and Crash-Proof Handlers
 */
export function SignalsPanel({ signals = [], history = [] }) {
  const { getPrice, viewMode, openCalculator } = usePrefs();
  const [activeTab, setActiveTab] = useState('signals'); // 'signals' | 'history'
  const [tf, setTf] = useState('All');
  const [direction, setDirection] = useState('All');
  const [statusFilter, setStatusFilter] = useState('All');
  const [historySpan, setHistorySpan] = useState('All Time');
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState('time');

  // Defensive array checks
  const signalList = Array.isArray(signals) ? signals : [];
  const historyList = Array.isArray(history) ? history : [];

  // Enrich signals with live market price and metrics
  const enrichedRows = useMemo(() => {
    return signalList.map((sig) => {
      const live = getPrice(sig?.symbol, sig?.current_price || sig?.entry);
      const metrics = calcTradeMetrics(sig, live?.price);
      return {
        ...sig,
        livePrice: live?.price || sig?.entry || 0,
        tickDir: live?.tickDir,
        metrics,
      };
    });
  }, [signalList, getPrice]);

  // Filter signals
  const filteredRows = useMemo(() => {
    return enrichedRows.filter((s) => {
      if (!s) return false;
      if (tf !== 'All' && s.timeframe !== tf) return false;
      const sDir = String(s.direction || '').toLowerCase();
      if (direction !== 'All' && sDir !== direction.toLowerCase()) return false;
      if (search.trim()) {
        const query = search.trim().toUpperCase();
        if (!String(s.symbol || '').toUpperCase().includes(query)) return false;
      }
      if (statusFilter !== 'All') {
        const ph = s?.metrics?.phase;
        if (statusFilter === 'In Entry Zone' && ph !== 'IN_ENTRY_ZONE') return false;
        if (statusFilter === 'In Trade' && ph !== 'IN_TRADE') return false;
        if (statusFilter === 'Pending' && ph !== 'WAITING_ENTRY') return false;
        if (statusFilter === 'Target Hit' && s.status !== 'target_hit' && ph !== 'TARGET_HIT') return false;
        if (statusFilter === 'Stopped Out' && s.status !== 'stopped' && ph !== 'STOPPED') return false;
      }
      return true;
    }).sort((a, b) => {
      if (sortBy === 'confidence') return (b.probability || 0) - (a.probability || 0);
      if (sortBy === 'rr') return (b?.metrics?.rrRatio || 0) - (a?.metrics?.rrRatio || 0);
      if (sortBy === 'pnl') return (b?.metrics?.floatingPnlPct || 0) - (a?.metrics?.floatingPnlPct || 0);
      return new Date(b?.created_at || 0) - new Date(a?.created_at || 0);
    });
  }, [enrichedRows, tf, direction, search, statusFilter, sortBy]);

  // Filter history
  const filteredHistory = useMemo(() => {
    const nowMs = Date.now();
    return historyList.filter((h) => {
      if (!h) return false;
      if (tf !== 'All' && h.timeframe !== tf) return false;
      if (search.trim()) {
        const query = search.trim().toUpperCase();
        if (!String(h.symbol || '').toUpperCase().includes(query)) return false;
      }

      if (historySpan !== 'All Time' && h.closed_at) {
        const closeMs = new Date(h.closed_at).getTime();
        const diffHours = (nowMs - closeMs) / (1000 * 3600);
        if (historySpan === 'Today (24h)' && diffHours > 24) return false;
        if (historySpan === '7 Days' && diffHours > 24 * 7) return false;
        if (historySpan === '30 Days' && diffHours > 24 * 30) return false;
      }
      return true;
    }).sort((a, b) => new Date(b?.closed_at || 0) - new Date(a?.closed_at || 0));
  }, [historyList, tf, search, historySpan]);

  return (
    <div className="card main-panel">
      {/* Top Header with Tab Switch */}
      <div className="card-head">
        <div className="panel-tab-group">
          <button
            className={`panel-tab ${activeTab === 'signals' ? 'active' : ''}`}
            onClick={() => setActiveTab('signals')}
          >
            📡 Active Predictive Signals ({filteredRows.length})
          </button>
          <button
            className={`panel-tab ${activeTab === 'history' ? 'active' : ''}`}
            onClick={() => setActiveTab('history')}
          >
            📜 Performance &amp; Trade History ({filteredHistory.length})
          </button>
        </div>

        <div className="search-wrap">
          <input
            type="text"
            className="search-input"
            placeholder="Search coin (e.g. BTC)..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      {/* Filter Control Bar */}
      <div className="filters-bar">
        <div className="filter-group">
          <span className="filter-label">Timeframe:</span>
          <div className="pill-group">
            {TIMEFRAMES.map((f) => (
              <button key={f} className="filter-pill" aria-pressed={tf === f} onClick={() => setTf(f)}>
                {f}
              </button>
            ))}
          </div>
        </div>

        {activeTab === 'signals' ? (
          <>
            <div className="filter-group">
              <span className="filter-label">Side:</span>
              <div className="pill-group">
                {DIRECTIONS.map((d) => (
                  <button key={d} className="filter-pill" aria-pressed={direction === d} onClick={() => setDirection(d)}>
                    {d}
                  </button>
                ))}
              </div>
            </div>

            <div className="filter-group">
              <span className="filter-label">Status:</span>
              <select
                className="filter-select"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
              >
                {STATUS_OPTIONS.map((st) => (
                  <option key={st} value={st}>{st}</option>
                ))}
              </select>
            </div>

            <div className="filter-group sort-group">
              <span className="filter-label">Sort:</span>
              <select
                className="filter-select"
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
              >
                <option value="time">Latest Time</option>
                <option value="confidence">Highest Confidence</option>
                <option value="rr">Best Risk / Reward</option>
                <option value="pnl">Floating PnL</option>
              </select>
            </div>
          </>
        ) : (
          <div className="filter-group">
            <span className="filter-label">History Period:</span>
            <div className="pill-group">
              {HISTORY_SPANS.map((sp) => (
                <button
                  key={sp}
                  className="filter-pill"
                  aria-pressed={historySpan === sp}
                  onClick={() => setHistorySpan(sp)}
                >
                  {sp}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Main Tab Content */}
      {activeTab === 'signals' ? (
        viewMode === 'table' ? (
          <div className="table-container">
            <table className="signals-table">
              <thead>
                <tr>
                  <th>Time &amp; Symbol</th>
                  <th>Side &amp; AI Conf</th>
                  <th>Live Price (CMP)</th>
                  <th>Expected Entry</th>
                  <th>Expected Stop Loss</th>
                  <th>Expected Target</th>
                  <th>R:R</th>
                  <th style={{ minWidth: '130px' }}>Trade Level Visualizer</th>
                  <th>Floating P&amp;L / Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredRows.map((s, idx) => {
                  const isLong = String(s.direction || '').toLowerCase() === 'long';
                  const m = s.metrics;
                  const tickClass = s.tickDir ? `tick-${s.tickDir}` : '';
                  const pnlPos = (m?.floatingPnlPct || 0) >= 0;

                  return (
                    <tr key={s.id || s.symbol + s.timeframe + idx} className={`signal-row ${s.status}`}>
                      <td>
                        <div className="sym-cell">
                          <span className="coin-symbol">{String(s.symbol || '').replace('USDT', '')}</span>
                          <span className="sym-meta">
                            <span className="tf-badge">{s.timeframe}</span>
                            <Time iso={s.created_at} />
                          </span>
                        </div>
                      </td>

                      <td>
                        <div className="dir-cell">
                          <span className={`dir-badge ${isLong ? 'long' : 'short'}`}>
                            {isLong ? '▲ LONG' : '▼ SHORT'}
                          </span>
                          <div className="conf-bar-wrap" title={`LightGBM probability: ${Math.round((s.probability || 0.5) * 100)}%`}>
                            <div className="conf-bar" style={{ width: `${Math.round((s.probability || 0.5) * 100)}%` }} />
                            <span className="conf-text">{Math.round((s.probability || 0.5) * 100)}%</span>
                          </div>
                          {s.meta_probability && (
                            <span className="meta-badge" title={`Meta-labeling model score: ${(s.meta_probability * 100).toFixed(0)}%`}>
                              ✓ Meta
                            </span>
                          )}
                        </div>
                      </td>

                      <td>
                        <div className={`cmp-cell ${tickClass}`}>
                          <div className="cmp-header-row">
                            <span className="live-dot pulse" />
                            <span className="cmp-val font-num">
                              <Money value={s.livePrice} />
                            </span>
                          </div>
                          <div className="cmp-sub-row">
                            {s.change_24h != null && (
                              <span className={`change-badge ${s.change_24h >= 0 ? 'pos' : 'neg'}`}>
                                {s.change_24h >= 0 ? '▲' : '▼'}{Math.abs(Number(s.change_24h)).toFixed(1)}%
                              </span>
                            )}
                            <span className="cmp-diff-tag" title="Difference from Expected Entry">
                              {s.livePrice >= s.entry ? '+' : ''}{(s.livePrice - s.entry).toFixed(s.livePrice < 1 ? 4 : 1)}
                            </span>
                          </div>
                        </div>
                      </td>

                      <td>
                        <div className="level-cell entry-cell">
                          <span className="level-val font-num font-bold">
                            <Money value={s.entry} />
                          </span>
                          <span className={`entry-dist ${m?.phase === 'IN_ENTRY_ZONE' ? 'ready' : ''}`}>
                            {m?.phase === 'IN_ENTRY_ZONE'
                              ? '🎯 In Zone'
                              : (m?.distToEntryPct || 0) > 0
                              ? `+${m.distToEntryPct.toFixed(2)}% to entry`
                              : `${(m?.distToEntryPct || 0).toFixed(2)}% past`}
                          </span>
                        </div>
                      </td>

                      <td>
                        <div className="level-cell sl-cell">
                          <span className="level-val font-num text-sl">
                            <Money value={s.stop_loss} />
                          </span>
                          <span className="risk-tag">
                            {fmtPct(m?.riskPct, false)} risk
                          </span>
                        </div>
                      </td>

                      <td>
                        <div className="level-cell tp-cell">
                          <span className="level-val font-num text-tp">
                            <Money value={s.take_profit} />
                          </span>
                          <span className="reward-tag">
                            +{fmtPct(m?.rewardPct, false)} reward
                          </span>
                        </div>
                      </td>

                      <td>
                        <span className="rr-badge">
                          1 : {(m?.rrRatio || 1).toFixed(1)}
                        </span>
                      </td>

                      <td>
                        <TradeLevelBar metrics={m} />
                      </td>

                      <td>
                        {s.status === 'target_hit' ? (
                          <span className="status-pill hit">✓ Target Hit</span>
                        ) : s.status === 'stopped' ? (
                          <span className="status-pill stop">✕ Stopped</span>
                        ) : m?.phase === 'IN_TRADE' || m?.phase === 'IN_ENTRY_ZONE' ? (
                          <div className="pnl-cell">
                            <span className={`pnl-val font-num ${pnlPos ? 'pos' : 'neg'}`}>
                              {pnlPos ? '+' : ''}{(m?.floatingPnlPct || 0).toFixed(2)}%
                            </span>
                            <span className="pnl-label">Unrealized P&amp;L</span>
                          </div>
                        ) : (
                          <span className="status-pill pending">⏳ Pending Entry</span>
                        )}
                      </td>

                      <td>
                        <button
                          className="calc-btn"
                          onClick={() => openCalculator(s)}
                          title="Calculate exact position size and risk"
                        >
                          Calc Size
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {filteredRows.length === 0 && (
              <div className="empty-state">
                <p className="sub pad">No signals matching your current filters.</p>
              </div>
            )}
          </div>
        ) : (
          <div className="cards-grid">
            {filteredRows.map((s, idx) => {
              const isLong = String(s.direction || '').toLowerCase() === 'long';
              const m = s.metrics;
              const pnlPos = (m?.floatingPnlPct || 0) >= 0;

              return (
                <div key={s.id || s.symbol + s.timeframe + idx} className={`signal-card ${isLong ? 'is-long' : 'is-short'}`}>
                  <div className="card-top">
                    <div className="card-coin-info">
                      <span className="card-symbol">{String(s.symbol || '').replace('USDT', '')}</span>
                      <span className="card-timeframe">{s.timeframe}</span>
                      <span className={`dir-badge ${isLong ? 'long' : 'short'}`}>
                        {isLong ? '▲ LONG' : '▼ SHORT'}
                      </span>
                    </div>
                    <div className={`card-cmp-box ${s.tickDir ? `tick-${s.tickDir}` : ''}`}>
                      <span className="cmp-label">
                        <span className="live-dot pulse" /> LIVE CMP (1s)
                      </span>
                      <span className="card-cmp font-num">
                        <Money value={s.livePrice} />
                      </span>
                      <span className="cmp-diff-tag">
                        {s.livePrice >= s.entry ? '+' : ''}{(s.livePrice - s.entry).toFixed(s.livePrice < 1 ? 4 : 1)} diff
                      </span>
                    </div>
                  </div>

                  <div className="card-ai-row">
                    <div className="ai-conf-wrap">
                      <span className="ai-label">AI Confidence:</span>
                      <span className="ai-score">{Math.round((s.probability || 0.5) * 100)}%</span>
                    </div>
                    {s.meta_probability && (
                      <span className="meta-badge">✓ Meta-Filter Approved</span>
                    )}
                    <span className="rr-badge">1 : {(m?.rrRatio || 1).toFixed(1)} R:R</span>
                  </div>

                  <div className="levels-grid">
                    <div className="level-box entry-box">
                      <span className="box-title">EXPECTED ENTRY</span>
                      <span className="box-price font-num font-bold">
                        <Money value={s.entry} />
                      </span>
                      <span className="box-sub">
                        {m?.phase === 'IN_ENTRY_ZONE' ? '🎯 In Entry Zone' : `${(m?.distToEntryPct || 0) > 0 ? '+' : ''}${(m?.distToEntryPct || 0).toFixed(2)}%`}
                      </span>
                    </div>
                    <div className="level-box sl-box">
                      <span className="box-title">STOP LOSS</span>
                      <span className="box-price font-num text-sl">
                        <Money value={s.stop_loss} />
                      </span>
                      <span className="box-sub text-sl">-{fmtPct(m?.riskPct, false)} Risk</span>
                    </div>
                    <div className="level-box tp-box">
                      <span className="box-title">TARGET / TP</span>
                      <span className="box-price font-num text-tp">
                        <Money value={s.take_profit} />
                      </span>
                      <span className="box-sub text-tp">+{fmtPct(m?.rewardPct, false)} Reward</span>
                    </div>
                  </div>

                  <div className="card-bar-section">
                    <TradeLevelBar metrics={m} />
                  </div>

                  <div className="card-footer">
                    <div className="card-status-box">
                      {s.status === 'target_hit' ? (
                        <span className="status-pill hit">✓ Target Hit</span>
                      ) : s.status === 'stopped' ? (
                        <span className="status-pill stop">✕ Stopped Out</span>
                      ) : (
                        <span className={`pnl-chip ${pnlPos ? 'pos' : 'neg'}`}>
                          P&amp;L: {pnlPos ? '+' : ''}{(m?.floatingPnlPct || 0).toFixed(2)}%
                        </span>
                      )}
                    </div>
                    <button className="calc-btn" onClick={() => openCalculator(s)}>
                      ⚡ Calc Position Size
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )
      ) : (
        /* Performance & Trade History Viewer Tab */
        <div className="history-container">
          <div className="history-summary-strip">
            <div className="hist-stat">
              <span className="sub">Filtered Trades</span>
              <span className="font-num font-bold big-stat">{filteredHistory.length}</span>
            </div>
            <div className="hist-stat">
              <span className="sub">Realized Win Rate</span>
              <span className="font-num font-bold text-tp big-stat">
                {filteredHistory.length > 0
                  ? (filteredHistory.filter(h => h.pnl_pct > 0).length / filteredHistory.length * 100).toFixed(1) + '%'
                  : '0.0%'}
              </span>
            </div>
            <div className="hist-stat">
              <span className="sub">Cumulative Return</span>
              <span className="font-num font-bold text-tp big-stat">
                {filteredHistory.length > 0
                  ? '+' + filteredHistory.reduce((acc, h) => acc + (h.pnl_pct || 0), 0).toFixed(2) + '%'
                  : '0.0%'}
              </span>
            </div>
          </div>

          <div className="table-container">
            <table className="signals-table history-table">
              <thead>
                <tr>
                  <th>Closed Time</th>
                  <th>Asset &amp; TF</th>
                  <th>Direction</th>
                  <th>Entry Price</th>
                  <th>Exit Price</th>
                  <th>Realized Net Return</th>
                  <th>Exit Reason</th>
                </tr>
              </thead>
              <tbody>
                {filteredHistory.map((h, i) => {
                  const isLong = String(h.direction || '').toLowerCase() === 'long';
                  const isProfit = (h.pnl_pct || 0) >= 0;

                  return (
                    <tr key={h.id || i} className="history-row">
                      <td>
                        <Time iso={h.closed_at} withDate />
                      </td>
                      <td>
                        <div className="sym-cell">
                          <span className="coin-symbol">{String(h.symbol || '').replace('USDT', '')}</span>
                          <span className="tf-badge">{h.timeframe}</span>
                        </div>
                      </td>
                      <td>
                        <span className={`dir-badge ${isLong ? 'long' : 'short'}`}>
                          {isLong ? '▲ LONG' : '▼ SHORT'}
                        </span>
                      </td>
                      <td>
                        <Money value={h.entry} />
                      </td>
                      <td>
                        <Money value={h.exit_price} />
                      </td>
                      <td>
                        <span className={`font-num font-bold ${isProfit ? 'text-tp' : 'text-sl'}`}>
                          {isProfit ? '+' : ''}{Number(h.pnl_pct).toFixed(2)}%
                        </span>
                      </td>
                      <td>
                        <span className={`status-pill ${isProfit ? 'hit' : 'stop'}`}>
                          {h.exit_reason || (isProfit ? 'Target Hit' : 'Stopped Out')}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {filteredHistory.length === 0 && (
              <div className="empty-state">
                <p className="sub pad">No trade history recorded for this time range.</p>
              </div>
            )}
          </div>
        </div>
      )}

      <RateNote />
    </div>
  );
}

/**
 * Interactive Position Size & Risk Calculator Drawer/Modal
 */
export function PositionCalculatorModal() {
  const { isCalcOpen, closeCalculator, calcSignal, cur } = usePrefs();
  const [balance, setBalance] = useState(cur === 'INR' ? 860000 : 10000);
  const [riskPct, setRiskPct] = useState(1.0);
  const [leverage, setLeverage] = useState(2.0);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    setBalance(cur === 'INR' ? 860000 : 10000);
  }, [cur]);

  if (!isCalcOpen || !calcSignal) return null;

  const isLong = String(calcSignal.direction || 'long').toLowerCase() === 'long';
  const entry = Number(calcSignal.entry || 1);
  const sl = Number(calcSignal.stop_loss || entry * 0.985);
  const tp = Number(calcSignal.take_profit || entry * 1.03);

  const riskPerUnit = isLong ? Math.max(0.00001, entry - sl) : Math.max(0.00001, sl - entry);
  const rewardPerUnit = isLong ? Math.max(0.00001, tp - entry) : Math.max(0.00001, entry - tp);
  const riskFraction = (riskPerUnit / entry);
  const rewardFraction = (rewardPerUnit / entry);

  const maxLossAmount = balance * (riskPct / 100);
  const recommendedPositionSize = maxLossAmount / (riskFraction || 0.01);
  const contractQuantity = recommendedPositionSize / entry;
  const estimatedProfit = recommendedPositionSize * rewardFraction;
  const marginRequired = recommendedPositionSize / leverage;
  const rrRatio = rewardFraction / (riskFraction || 1);

  const copyLevels = () => {
    const text = `Trade AI Order Setup:
Symbol: ${calcSignal.symbol} (${String(calcSignal.direction).toUpperCase()} - ${calcSignal.timeframe})
Entry: ${entry}
Stop Loss: ${sl} (-${(riskFraction * 100).toFixed(2)}%)
Take Profit: ${tp} (+${(rewardFraction * 100).toFixed(2)}%)
R:R Ratio: 1 : ${rrRatio.toFixed(2)}`;
    try {
      navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {}
  };

  return (
    <div className="modal-backdrop" onClick={closeCalculator}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h3 className="modal-title">Position Size &amp; Risk Calculator</h3>
            <p className="sub">{calcSignal.symbol} • {calcSignal.timeframe} • {String(calcSignal.direction).toUpperCase()}</p>
          </div>
          <button className="close-btn" onClick={closeCalculator}>✕</button>
        </div>

        <div className="modal-body">
          <div className="calc-inputs">
            <div className="input-field">
              <label>Account Portfolio Balance ({cur})</label>
              <input
                type="number"
                value={balance}
                onChange={(e) => setBalance(Math.max(1, Number(e.target.value)))}
                step="100"
              />
            </div>
            <div className="input-field">
              <label>Max Risk Per Trade (%)</label>
              <input
                type="number"
                value={riskPct}
                onChange={(e) => setRiskPct(Math.max(0.1, Math.min(10, Number(e.target.value))))}
                step="0.25"
                min="0.1"
                max="10"
              />
            </div>
            <div className="input-field">
              <label>Simulated Leverage ({leverage}x)</label>
              <input
                type="range"
                min="1"
                max="3"
                step="0.5"
                value={leverage}
                onChange={(e) => setLeverage(Number(e.target.value))}
              />
            </div>
          </div>

          <div className="calc-results">
            <div className="result-row highlight">
              <span>Recommended Position Size:</span>
              <span className="font-num font-bold">
                {cur === 'INR' ? '\u20B9' : '$'}{recommendedPositionSize.toLocaleString(undefined, { maximumFractionDigits: 1 })}
              </span>
            </div>
            <div className="result-row">
              <span>Required Margin ({leverage}x leverage):</span>
              <span className="font-num">
                {cur === 'INR' ? '\u20B9' : '$'}{marginRequired.toLocaleString(undefined, { maximumFractionDigits: 1 })}
              </span>
            </div>
            <div className="result-row">
              <span>Exact Contract Quantity:</span>
              <span className="font-num text-cyan font-bold">
                {contractQuantity >= 1 ? contractQuantity.toFixed(3) : contractQuantity.toFixed(4)} {String(calcSignal.symbol).replace('USDT', '')}
              </span>
            </div>
            <div className="result-row loss">
              <span>Max Allowable Loss (If Stopped):</span>
              <span className="font-num text-sl font-bold">
                -{cur === 'INR' ? '\u20B9' : '$'}{maxLossAmount.toLocaleString(undefined, { maximumFractionDigits: 1 })} (-{riskPct}%)
              </span>
            </div>
            <div className="result-row profit">
              <span>Estimated Profit (If Target Hit):</span>
              <span className="font-num text-tp font-bold">
                +{cur === 'INR' ? '\u20B9' : '$'}{estimatedProfit.toLocaleString(undefined, { maximumFractionDigits: 1 })} (+{(rewardFraction * 100).toFixed(1)}%)
              </span>
            </div>
            <div className="result-row">
              <span>Risk to Reward Ratio:</span>
              <span className="font-num rr-badge">
                1 : {rrRatio.toFixed(2)}
              </span>
            </div>
          </div>

          <div className="levels-preview">
            <div className="preview-item">
              <span className="sub">ENTRY</span>
              <span className="font-num font-bold"><Money value={entry} /></span>
            </div>
            <div className="preview-item">
              <span className="sub">STOP LOSS</span>
              <span className="font-num text-sl"><Money value={sl} /></span>
            </div>
            <div className="preview-item">
              <span className="sub">TAKE PROFIT</span>
              <span className="font-num text-tp"><Money value={tp} /></span>
            </div>
          </div>
        </div>

        <div className="modal-footer">
          <button className="tf copy-btn" onClick={copyLevels}>
            {copied ? '✓ Levels Copied to Clipboard!' : '📋 Copy Order Levels'}
          </button>
          <button className="tf primary-btn" onClick={closeCalculator}>
            Done
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * 30-Day Paper Equity Chart with Area Fill and Drawdown Visualizer
 */
export function EquityChart({ points = [] }) {
  const ptsList = Array.isArray(points) ? points : [];
  if (ptsList.length < 2) return <p className="sub">Not enough data yet.</p>;
  const v = ptsList.map((p) => p?.equity || 100);
  const min = Math.min(...v);
  const max = Math.max(...v);
  const span = max - min || 1;

  const width = 420;
  const height = 150;
  const padBottom = 25;
  const usableHeight = height - padBottom;

  const pts = v
    .map((y, i) => {
      const x = (i / (v.length - 1)) * width;
      const normalizedY = usableHeight - ((y - min) / span) * (usableHeight - 20) - 10;
      return `${x.toFixed(1)},${normalizedY.toFixed(1)}`;
    })
    .join(' ');

  const areaPts = `0,${usableHeight} ${pts} ${width},${usableHeight}`;
  const startEq = v[0];
  const endEq = v[v.length - 1];
  const changePct = ((endEq - startEq) / startEq) * 100;
  const isPos = changePct >= 0;

  return (
    <div className="equity-chart-box">
      <div className="chart-header-stats">
        <span className="stat-cur font-num font-bold">{endEq.toFixed(1)} USDT</span>
        <span className={`stat-change ${isPos ? 'pos' : 'neg'}`}>
          {isPos ? '+' : ''}{changePct.toFixed(2)}% (30D)
        </span>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} width="100%" role="img" aria-label="Paper equity curve over the last 30 days">
        <defs>
          <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#10B981" stopOpacity="0.25" />
            <stop offset="100%" stopColor="#10B981" stopOpacity="0.0" />
          </linearGradient>
        </defs>
        {[30, 70, 110].map((y) => (
          <line key={y} x1="0" y1={y} x2={width} y2={y} stroke="#1F2937" strokeDasharray="3 3" />
        ))}
        <polygon points={areaPts} fill="url(#eqGrad)" />
        <polyline points={pts} fill="none" stroke="#10B981" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        <text x="0" y={height - 5} fontSize="11" fill="#9AA4B2">30d ago</text>
        <text x={width} y={height - 5} fontSize="11" fill="#9AA4B2" textAnchor="end">Today</text>
      </svg>
    </div>
  );
}
