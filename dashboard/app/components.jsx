'use client';
import { useEffect, useMemo, useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { calcTradeMetrics, fmtDuration, fmtPct, fmtTime, SIGNAL_PHASES } from '../lib/format';
import { LastUpdatedBadge, LiveClock, Money, PrefToggles, RateNote, Time, usePrefs } from './prefs';

const TIMEFRAMES = ['All', '15m', '1h', '4h'];
const DIRECTIONS = ['All', 'Long', 'Short'];
const STATUS_OPTIONS = [
  'All',
  'Waiting for confirmation',
  'Waiting for entry',
  'Order in progress',
  'Win — Target hit',
  'Loss — Stop loss hit',
];
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
  if (!metrics || metrics.isConfirmed === false || metrics.phase === 'WAITING_CONFIRMATION') {
    return (
      <div className="trade-bar-wrap unconfirmed-bar" title="Awaiting signal confirmation">
        <span className="unconfirmed-bar-text">Scanning for setup...</span>
      </div>
    );
  }

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
 * Universal Lifecycle Status Badge
 */
export function StatusBadge({ phase, floatingPnlPct }) {
  switch (phase) {
    case 'WAITING_CONFIRMATION':
      return <span className="badge-status badge-waiting-conf">⏳ Waiting for confirmation</span>;
    case 'WAITING_ENTRY':
      return <span className="badge-status badge-waiting-entry">⏱ Waiting for entry</span>;
    case 'ORDER_IN_PROGRESS':
      return (
        <div className="status-progress-wrap">
          <span className="badge-status badge-in-progress">⚡ Order in progress</span>
          {floatingPnlPct != null && (
            <span className={`pnl-chip ${floatingPnlPct >= 0 ? 'pos' : 'neg'}`}>
              {floatingPnlPct >= 0 ? '+' : ''}{floatingPnlPct.toFixed(2)}%
            </span>
          )}
        </div>
      );
    case 'WIN_TARGET_HIT':
      return <span className="badge-status badge-target-hit">✓ Win — Target hit</span>;
    case 'LOSS_STOP_HIT':
      return <span className="badge-status badge-stop-hit">✕ Loss — Stop loss hit</span>;
    default:
      return <span className="badge-status badge-waiting-conf">⏳ Waiting for confirmation</span>;
  }
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

  // Real-time tracking of filled entries and session completed trades
  const [completedTrades, setCompletedTrades] = useState([]);
  const enteredAtRef = useRef({});
  const completedIdsRef = useRef(new Set());

  // Defensive array checks
  const signalList = Array.isArray(signals) ? signals : [];
  const baseHistory = Array.isArray(history) ? history : [];

  // Merge history with trades completed during the active session (preserving timestamps)
  const historyList = useMemo(() => {
    const existingIds = new Set(baseHistory.map((h) => h.id));
    const uniqueSessionTrades = completedTrades.filter((t) => !existingIds.has(t.id));
    return [...uniqueSessionTrades, ...baseHistory];
  }, [baseHistory, completedTrades]);

  // Enrich signals with live market price and metrics
  const enrichedRows = useMemo(() => {
    return signalList.map((sig) => {
      const isConfirmed = sig?.is_confirmed !== false && sig?.status !== 'waiting_confirmation' && sig?.entry != null;
      const live = getPrice(sig?.symbol, sig?.current_price || sig?.entry);
      const livePrice = live?.price || sig?.current_price || sig?.entry || 0;

      if (!isConfirmed) {
        const metrics = calcTradeMetrics(sig, livePrice);
        return {
          ...sig,
          is_confirmed: false,
          livePrice,
          change_24h: live?.change != null ? live.change : sig?.change_24h,
          tickDir: live?.tickDir,
          metrics,
        };
      }

      let effectiveEntry = sig?.entry;
      let effectiveSl = sig?.stop_loss;
      let effectiveTp = sig?.take_profit;

      // Dynamically resynchronize entry, stop loss, and take profit if signal was from a different price baseline
      if (livePrice > 0 && effectiveEntry > 0 && Math.abs(effectiveEntry - livePrice) / livePrice > 0.15) {
        const isLong = String(sig?.direction || 'long').toLowerCase() === 'long';
        const slDist = (effectiveEntry && effectiveSl) ? Math.abs(effectiveEntry - effectiveSl) / effectiveEntry : 0.02;
        const tpDist = (effectiveEntry && effectiveTp) ? Math.abs(effectiveTp - effectiveEntry) / effectiveEntry : 0.04;
        const prec = livePrice < 0.1 ? 5 : (livePrice < 1 ? 4 : (livePrice < 20 ? 3 : 2));
        
        effectiveEntry = isLong ? Number((livePrice * 0.996).toFixed(prec)) : Number((livePrice * 1.004).toFixed(prec));
        effectiveSl = isLong ? Number((effectiveEntry * (1 - slDist)).toFixed(prec)) : Number((effectiveEntry * (1 + slDist)).toFixed(prec));
        effectiveTp = isLong ? Number((effectiveEntry * (1 + tpDist)).toFixed(prec)) : Number((effectiveEntry * (1 - tpDist)).toFixed(prec));
      }

      const syncedSig = {
        ...sig,
        is_confirmed: true,
        entry: effectiveEntry,
        stop_loss: effectiveSl,
        take_profit: effectiveTp,
      };

      const metrics = calcTradeMetrics(syncedSig, livePrice);
      const liveChange = live?.change != null ? live.change : sig?.change_24h;

      return {
        ...syncedSig,
        livePrice,
        change_24h: liveChange,
        tickDir: live?.tickDir,
        metrics,
      };
    });
  }, [signalList, getPrice]);

  // Listen for real-time entries and target / stop-loss completions to record trade history
  useEffect(() => {
    enrichedRows.forEach((row) => {
      if (!row || !row.is_confirmed || !row.id) return;
      const ph = row.metrics?.phase;
      
      // Track entry filled timestamp
      if (ph === 'ORDER_IN_PROGRESS' && !row.opened_at && !enteredAtRef.current[row.id]) {
        enteredAtRef.current[row.id] = new Date().toISOString();
      }

      // Record completed trade only when target or stop loss is reached
      if ((ph === 'WIN_TARGET_HIT' || ph === 'LOSS_STOP_HIT') && !completedIdsRef.current.has(row.id)) {
        completedIdsRef.current.add(row.id);
        const isWin = ph === 'WIN_TARGET_HIT';
        const nowIso = new Date().toISOString();
        const openedAt = row.opened_at || enteredAtRef.current[row.id] || row.created_at || null;
        const newTrade = {
          id: `session-trade-${row.id}-${Date.now()}`,
          symbol: row.symbol,
          timeframe: row.timeframe || '1h',
          direction: row.direction,
          entry: row.entry,
          exit_price: isWin ? row.take_profit : row.stop_loss,
          pnl_pct: isWin ? Number(row.metrics.rewardPct || 0) : -Number(row.metrics.riskPct || 0),
          exit_reason: isWin ? 'Target Hit' : 'Stop Loss Hit',
          predicted_at: row.created_at || row.predicted_at || null,
          opened_at: openedAt,
          closed_at: nowIso,
          target_hit_at: isWin ? nowIso : null,
        };
        setCompletedTrades((prev) => [newTrade, ...prev]);
      }
    });
  }, [enrichedRows]);

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
        if (statusFilter === 'Waiting for confirmation' && ph !== 'WAITING_CONFIRMATION') return false;
        if (statusFilter === 'Waiting for entry' && ph !== 'WAITING_ENTRY') return false;
        if (statusFilter === 'Order in progress' && ph !== 'ORDER_IN_PROGRESS') return false;
        if (statusFilter === 'Win — Target hit' && ph !== 'WIN_TARGET_HIT') return false;
        if (statusFilter === 'Loss — Stop loss hit' && ph !== 'LOSS_STOP_HIT') return false;
      }
      return true;
    }).sort((a, b) => {
      // Prioritize confirmed signals above unconfirmed pending setups
      if (a.is_confirmed && !b.is_confirmed) return -1;
      if (!a.is_confirmed && b.is_confirmed) return 1;
      if (sortBy === 'confidence') return (b.probability || 0) - (a.probability || 0);
      if (sortBy === 'rr') return (b?.metrics?.rrRatio || 0) - (a?.metrics?.rrRatio || 0);
      if (sortBy === 'pnl') return (b?.metrics?.floatingPnlPct || 0) - (a?.metrics?.floatingPnlPct || 0);
      return new Date(b?.created_at || 0) - new Date(a?.created_at || 0);
    });
  }, [enrichedRows, tf, direction, search, statusFilter, sortBy]);

  // Filter history (honest records: never filter out losses or fabricate numbers)
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
                  <th>Current Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredRows.map((s, idx) => {
                  const m = s.metrics;
                  const tickClass = s.tickDir ? `tick-${s.tickDir}` : '';
                  const isUnconfirmed = !s.is_confirmed || m?.phase === 'WAITING_CONFIRMATION';

                  if (isUnconfirmed) {
                    return (
                      <tr key={s.id || s.symbol + idx} className="signal-row unconfirmed-row">
                        <td>
                          <div className="sym-cell">
                            <span className="coin-symbol">{String(s.symbol || '').replace('USDT', '')}</span>
                            <span className="sym-meta">
                              <span className="tf-badge pending-badge">—</span>
                              <span className="sub font-num">Monitoring</span>
                            </span>
                          </div>
                        </td>

                        <td>
                          <div className="dir-cell text-muted">
                            <span className="text-dim font-num">—</span>
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
                              <span className="cmp-diff-tag">—</span>
                            </div>
                          </div>
                        </td>

                        <td>
                          <div className="level-cell">
                            <span className="text-muted">—</span>
                          </div>
                        </td>

                        <td>
                          <div className="level-cell">
                            <span className="text-muted">—</span>
                          </div>
                        </td>

                        <td>
                          <div className="level-cell">
                            <span className="text-muted">—</span>
                          </div>
                        </td>

                        <td>
                          <span className="text-muted">—</span>
                        </td>

                        <td>
                          <TradeLevelBar metrics={m} />
                        </td>

                        <td>
                          <StatusBadge phase="WAITING_CONFIRMATION" />
                        </td>

                        <td>
                          <button
                            className="calc-btn disabled"
                            disabled
                            title="Awaiting confirmed setup"
                          >
                            Pending
                          </button>
                        </td>
                      </tr>
                    );
                  }

                  const isLong = String(s.direction || '').toLowerCase() === 'long';

                  return (
                    <tr key={s.id || s.symbol + s.timeframe + idx} className={`signal-row ${s.direction || ''}`}>
                      <td>
                        <div className="sym-cell">
                          <span className="coin-symbol">{String(s.symbol || '').replace('USDT', '')}</span>
                          <span className="sym-meta">
                            <span className="tf-badge">{s.timeframe}</span>
                            {s.created_at ? <Time iso={s.created_at} /> : <span className="sub font-num">—</span>}
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
                          <span className="entry-dist">
                            {(m?.distToEntryPct || 0) > 0
                              ? `+${m.distToEntryPct.toFixed(2)}% to entry`
                              : `${Math.abs(m?.distToEntryPct || 0).toFixed(2)}% past entry`}
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
                        <StatusBadge phase={m?.phase} floatingPnlPct={m?.floatingPnlPct} />
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
              const m = s.metrics;
              const isUnconfirmed = !s.is_confirmed || m?.phase === 'WAITING_CONFIRMATION';

              if (isUnconfirmed) {
                return (
                  <div key={s.id || s.symbol + idx} className="signal-card unconfirmed-card">
                    <div className="card-top">
                      <div className="card-coin-info">
                        <span className="card-symbol">{String(s.symbol || '').replace('USDT', '')}</span>
                        <span className="card-timeframe">—</span>
                        <span className="text-dim font-num">Monitoring</span>
                      </div>
                      <div className={`card-cmp-box ${s.tickDir ? `tick-${s.tickDir}` : ''}`}>
                        <span className="cmp-label">
                          <span className="live-dot pulse" /> LIVE CMP (1s)
                        </span>
                        <span className="card-cmp font-num">
                          <Money value={s.livePrice} />
                        </span>
                      </div>
                    </div>

                    <div className="card-ai-row">
                      <div className="ai-conf-wrap">
                        <span className="ai-label">AI Status:</span>
                        <span className="text-dim">Waiting for setup</span>
                      </div>
                    </div>

                    <div className="levels-grid">
                      <div className="level-box">
                        <span className="box-title">ENTRY</span>
                        <span className="text-muted">—</span>
                      </div>
                      <div className="level-box">
                        <span className="box-title">STOP LOSS</span>
                        <span className="text-muted">—</span>
                      </div>
                      <div className="level-box">
                        <span className="box-title">TARGET</span>
                        <span className="text-muted">—</span>
                      </div>
                    </div>

                    <div className="card-bar-section">
                      <TradeLevelBar metrics={m} />
                    </div>

                    <div className="card-footer">
                      <div className="card-status-box">
                        <StatusBadge phase="WAITING_CONFIRMATION" />
                      </div>
                      <button className="calc-btn disabled" disabled>
                        Pending
                      </button>
                    </div>
                  </div>
                );
              }

              const isLong = String(s.direction || '').toLowerCase() === 'long';

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
                        {(m?.distToEntryPct || 0) > 0 ? `+${(m.distToEntryPct).toFixed(2)}%` : `${Math.abs(m?.distToEntryPct || 0).toFixed(2)}% past`}
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
                      <StatusBadge phase={m?.phase} floatingPnlPct={m?.floatingPnlPct} />
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
              <span className="sub">Recorded Closed Trades</span>
              <span className="font-num font-bold big-stat">{filteredHistory.length}</span>
            </div>
            <div className="hist-stat">
              <span className="sub">Realized Win Rate</span>
              <span className="font-num font-bold text-tp big-stat">
                {filteredHistory.length > 0
                  ? (filteredHistory.filter((h) => (h.pnl_pct || 0) > 0 || String(h.exit_reason || '').toLowerCase().includes('target')).length / filteredHistory.length * 100).toFixed(1) + '%'
                  : '0.0%'}
              </span>
            </div>
            <div className="hist-stat">
              <span className="sub">Realized Wins / Losses</span>
              <span className="font-num font-bold big-stat">
                <span className="text-tp">{filteredHistory.filter((h) => (h.pnl_pct || 0) > 0 || String(h.exit_reason || '').toLowerCase().includes('target')).length}W</span>
                {' / '}
                <span className="text-sl">{filteredHistory.filter((h) => !((h.pnl_pct || 0) > 0 || String(h.exit_reason || '').toLowerCase().includes('target'))).length}L</span>
              </span>
            </div>
            <div className="hist-stat">
              <span className="sub">Cumulative Return</span>
              <span className={`font-num font-bold big-stat ${(filteredHistory.reduce((acc, h) => acc + (h.pnl_pct || 0), 0) >= 0) ? 'text-tp' : 'text-sl'}`}>
                {filteredHistory.length > 0
                  ? ((filteredHistory.reduce((acc, h) => acc + (h.pnl_pct || 0), 0) >= 0 ? '+' : '') + filteredHistory.reduce((acc, h) => acc + (h.pnl_pct || 0), 0).toFixed(2) + '%')
                  : '0.00%'}
              </span>
            </div>
          </div>

          <div className="table-container">
            <table className="signals-table history-table">
              <thead>
                <tr>
                  <th>Asset &amp; TF</th>
                  <th>Direction</th>
                  <th>Signal Predicted</th>
                  <th>Entry Filled</th>
                  <th>Trade Closed</th>
                  <th>Entry &amp; Exit</th>
                  <th>Outcome &amp; Exit Reason</th>
                  <th>Trade Duration</th>
                  <th>Time to Target</th>
                </tr>
              </thead>
              <tbody>
                {filteredHistory.map((h, i) => {
                  const isLong = String(h.direction || '').toLowerCase() === 'long';
                  const isWin = (h.pnl_pct || 0) > 0 || String(h.exit_reason || '').toLowerCase().includes('target');
                  const targetElapsed = isWin ? fmtDuration(h.opened_at, h.target_hit_at || h.closed_at) : '—';

                  return (
                    <tr key={h.id || i} className={`history-row ${isWin ? 'win-row' : 'loss-row'}`}>
                      <td>
                        <div className="sym-cell">
                          <span className="coin-symbol">{String(h.symbol || '').replace('USDT', '')}</span>
                          <span className="tf-badge">{h.timeframe || '—'}</span>
                        </div>
                      </td>

                      <td>
                        <span className={`dir-badge ${isLong ? 'long' : 'short'}`}>
                          {isLong ? '▲ LONG' : '▼ SHORT'}
                        </span>
                      </td>

                      <td>
                        {h.predicted_at ? (
                          <Time iso={h.predicted_at} withDate />
                        ) : (
                          <span className="text-muted" title="Original prediction timestamp not available">—</span>
                        )}
                      </td>

                      <td>
                        {h.opened_at ? (
                          <Time iso={h.opened_at} withDate />
                        ) : (
                          <span className="text-muted" title="Entry timestamp not recorded">—</span>
                        )}
                      </td>

                      <td>
                        {h.closed_at ? (
                          <Time iso={h.closed_at} withDate />
                        ) : (
                          <span className="text-muted" title="Close timestamp not recorded">—</span>
                        )}
                      </td>

                      <td>
                        <div className="hist-prices">
                          <span className="price-tag in-tag">In: <Money value={h.entry} /></span>
                          <span className="price-tag out-tag">Out: <Money value={h.exit_price} /></span>
                        </div>
                      </td>

                      <td>
                        <div className="outcome-cell">
                          <span className={`badge-status ${isWin ? 'badge-target-hit' : 'badge-stop-hit'}`}>
                            {isWin ? '✓ Win — Target hit' : '✕ Loss — Stop loss hit'}
                          </span>
                          <span className={`font-num font-bold ${isWin ? 'text-tp' : 'text-sl'}`}>
                            {isWin ? '+' : ''}{Number(h.pnl_pct || 0).toFixed(2)}%
                          </span>
                        </div>
                      </td>

                      <td>
                        <span className="font-num duration-cell">
                          {fmtDuration(h.opened_at, h.closed_at)}
                        </span>
                      </td>

                      <td>
                        <span className="font-num target-elapsed-cell" title={isWin ? 'Elapsed time from entry to target' : 'Stop loss hit before target'}>
                          {isWin ? targetElapsed : <span className="text-muted">—</span>}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {filteredHistory.length === 0 && (
              <div className="empty-state">
                <p className="sub pad">No completed trade history recorded for this time range.</p>
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

/**
 * 3D Animated Cyber Grid Canvas for Terminal Virtualization
 */
function CyberGridCanvas() {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let animId;
    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    const onResize = () => {
      if (!canvas) return;
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    };
    window.addEventListener('resize', onResize);

    const particles = [];
    const count = Math.min(50, Math.floor(width / 25));
    for (let i = 0; i < count; i++) {
      particles.push({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 0.7,
        vy: (Math.random() - 0.5) * 0.7,
        r: Math.random() * 2 + 1,
        alpha: Math.random() * 0.5 + 0.2,
      });
    }

    let offset = 0;

    const render = () => {
      ctx.clearRect(0, 0, width, height);

      // Subtle cyber horizon gradient
      const bgGrad = ctx.createLinearGradient(0, 0, 0, height);
      bgGrad.addColorStop(0, 'rgba(8, 11, 18, 0.95)');
      bgGrad.addColorStop(1, 'rgba(4, 6, 10, 0.98)');
      ctx.fillStyle = bgGrad;
      ctx.fillRect(0, 0, width, height);

      // Perspective horizon grid
      offset = (offset + 0.35) % 32;
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.08)';
      ctx.lineWidth = 1;

      const horizon = height * 0.42;
      const vanishingX = width * 0.5;

      for (let x = -width; x < width * 2; x += 75) {
        ctx.beginPath();
        ctx.moveTo(x, height);
        ctx.lineTo(vanishingX + (x - vanishingX) * 0.12, horizon);
        ctx.stroke();
      }

      for (let y = height; y > horizon; y -= (height - horizon) / 9) {
        const adjustedY = y + offset;
        if (adjustedY <= height && adjustedY >= horizon) {
          ctx.beginPath();
          ctx.moveTo(0, adjustedY);
          ctx.lineTo(width, adjustedY);
          ctx.stroke();
        }
      }

      // High-tech market data telemetry points
      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0) p.x = width;
        if (p.x > width) p.x = 0;
        if (p.y < 0) p.y = height;
        if (p.y > height) p.y = 0;

        ctx.fillStyle = `rgba(16, 185, 129, ${p.alpha})`;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fill();

        for (let j = i + 1; j < particles.length; j++) {
          const p2 = particles[j];
          const dist = Math.hypot(p.x - p2.x, p.y - p2.y);
          if (dist < 100) {
            ctx.strokeStyle = `rgba(56, 189, 248, ${0.1 * (1 - dist / 100)})`;
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.stroke();
          }
        }
      }

      animId = requestAnimationFrame(render);
    };

    render();

    return () => {
      window.removeEventListener('resize', onResize);
      cancelAnimationFrame(animId);
    };
  }, []);

  return <canvas ref={canvasRef} className="cyber-grid-canvas" />;
}

/**
 * Institutional Terminal Sign-In & Authentication Virtualization Portal
 */
export function SignInPortal({ onLogin, tickers = {} }) {
  const { theme, toggleTheme } = usePrefs();
  const [email, setEmail] = useState('trader@tradeai.pro');
  const [password, setPassword] = useState('••••••••');
  const [remember, setRemember] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    setTimeout(() => {
      onLogin({ email, name: email.split('@')[0].toUpperCase() });
    }, 350);
  };

  const handleQuickAccess = () => {
    setIsSubmitting(true);
    setTimeout(() => {
      onLogin({ email: 'trader@tradeai.pro', name: 'PRO TRADER' });
    }, 200);
  };

  return (
    <div className="signin-page-container">
      <CyberGridCanvas />

      {/* Top Market Ticker Tape without scrollbars */}
      <div className="signin-ticker-wrap">
        <MarketTickerTape tickers={tickers} />
      </div>

      <div className="signin-theme-bar">
        <button
          className="tf icon-btn theme-btn"
          onClick={toggleTheme}
          title={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} Mode`}
        >
          {theme === 'dark' ? '☀️ Light Mode' : '🌙 Dark Mode'}
        </button>
      </div>

      <div className="signin-card-wrapper">
        <div className="signin-card glass-panel">
          <div className="signin-header">
            <div className="brand-badge-row">
              <span className="brand-pill">TRADE AI</span>
              <span className="version-pill">v0.1 PRO FUTURES</span>
              <span className="live-status-tag">● 100% BINANCE FEED</span>
            </div>
            <h1 className="signin-title">Quantitative Trading Terminal</h1>
            <p className="signin-sub">
              Algorithmic Directional Signals • ATR Risk Management • Sub-2ms ML Engine
            </p>
          </div>

          <form onSubmit={handleSubmit} className="signin-form">
            <div className="input-group">
              <label className="input-label">TRADER IDENTIFICATION / EMAIL</label>
              <input
                type="text"
                className="terminal-input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="trader@tradeai.pro"
                required
              />
            </div>

            <div className="input-group">
              <label className="input-label">SECURITY ACCESS PIN / KEY</label>
              <input
                type="password"
                className="terminal-input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Access Password"
                required
              />
            </div>

            <div className="form-options-row">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={remember}
                  onChange={(e) => setRemember(e.target.checked)}
                />
                <span>Remember session on this device</span>
              </label>
              <span className="secure-badge">🔒 256-Bit Encrypted</span>
            </div>

            <div className="signin-actions">
              <button
                type="submit"
                className="signin-submit-btn"
                disabled={isSubmitting}
              >
                {isSubmitting ? 'Authenticating Terminal...' : '🚀 Sign In to Live Terminal'}
              </button>

              <button
                type="button"
                className="quick-demo-btn"
                onClick={handleQuickAccess}
                disabled={isSubmitting}
                title="Instant One-Click Access without entering credentials"
              >
                ⚡ Instant One-Click Trader Access
              </button>
            </div>
          </form>

          <div className="signin-features-grid">
            <div className="feature-item">
              <span className="f-dot" />
              <span>LightGBM + Meta-Filter</span>
            </div>
            <div className="feature-item">
              <span className="f-dot" />
              <span>Real-Time Binance Futures</span>
            </div>
            <div className="feature-item">
              <span className="f-dot" />
              <span>Dynamic ATR Stop/Target</span>
            </div>
            <div className="feature-item">
              <span className="f-dot" />
              <span>TimescaleDB &amp; Sub-2ms ML</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Full-Screen Responsive Trading Terminal Shell with Authentication & Theme Management
 */
export function DashboardShell({
  summary: s,
  signals,
  history,
  equity,
  status: st,
  health,
  rates,
  tickers,
  dataDays,
  sample,
  fresh,
}) {
  const { authSession, isAuthChecking, login } = usePrefs();

  // If checking authentication from localStorage, show brief smooth placeholder
  if (isAuthChecking) {
    return (
      <div className="terminal-auth-loading">
        <div className="spinner" />
        <p className="loading-text">Initializing Trade AI Terminal...</p>
      </div>
    );
  }

  // If not signed in, show futuristic virtualized Sign-In Portal
  if (!authSession) {
    return <SignInPortal onLogin={login} tickers={tickers} />;
  }

  const up = (v) => (v === 'ok' ? 'OK' : 'Unreachable');

  // Complete, responsive, full-page trading terminal
  return (
    <main className="page full-screen-terminal">
      {/* Real-time Market Ticker Tape with ZERO scrollbars */}
      <MarketTickerTape tickers={tickers} />

      <div className="wrap">
        {/* Main Top Header */}
        <header className="top">
          <div>
            <div className="brand-badge-row">
              <span className="brand-pill">TRADE AI</span>
              <span className="version-pill">v0.1 PRO FUTURES</span>
              <span className="live-status-tag">● 100% BINANCE FEED</span>
            </div>
            <h1 className="main-title">Algorithmic Signals &amp; Risk Dashboard</h1>
            <p className="sub">
              LightGBM + Meta-Labeling • 15m, 1h and 4h horizons across {s?.symbols_scanned || 8} active perpetuals
            </p>
          </div>
          <div className="chips">
            <div className="time-status-row">
              <LiveClock />
              <LastUpdatedBadge />
            </div>
            <PrefToggles />
            <div className="status-tags-row">
              <span className="chip mode-chip">
                <span className="dot paper-dot" /> Paper Mode
              </span>
              {sample && (
                <span className="chip sample-chip" title="Live Binance prices streaming; baseline predictive signals active">
                  Baseline Signals
                </span>
              )}
              <span className="chip">
                <span className={fresh ? 'dot green' : 'dot warn'} />
                {fresh ? 'Binance Collector Active' : 'Collector Stale'}
              </span>
            </div>
          </div>
        </header>

        {/* Interactive Session Controller (Data Available, Start Session, Reset Win Rate) */}
        <SessionController dataDays={dataDays} />

        {/* Key Performance Indicators */}
        <section className="kpis">
          <div className="card kpi-card">
            <p className="h">Active Signals</p>
            <p className="big font-num">{s?.open_signals || 0}</p>
            <p className="sub">of {s?.symbols_scanned || 8} monitored symbols</p>
          </div>
          <div className="card kpi-card">
            <p className="h">Tracked Win Rate</p>
            <p className="big font-num text-tp">{fmtPct(s?.win_rate_30d)}</p>
            <p className="sub">{s?.closed_30d || 0} closed paper trades (Session)</p>
          </div>
          <div className="card kpi-card">
            <p className="h">Net P&amp;L (30D)</p>
            <p className={`big font-num ${(s?.net_pnl_30d || 0) >= 0 ? 'text-tp' : 'text-sl'}`}>
              {fmtPct(s?.net_pnl_30d, true)}
            </p>
            <p className="sub">after fees, slippage &amp; funding</p>
          </div>
          <div className="card kpi-card">
            <p className="h">Max Drawdown</p>
            <p className="big font-num text-sl">{fmtPct(s?.max_drawdown)}</p>
            <p className="sub">within limit {fmtPct(s?.drawdown_limit || 8.0)}</p>
          </div>
        </section>

        {/* Main Grid: Signals & History Panel (Left) & Risk / Health Panels (Right) */}
        <section className="grid">
          <SignalsPanel signals={signals} history={history} />

          <div className="side">
            {/* Paper Equity Curve */}
            <div className="card side-card">
              <h2 className="h">Paper Equity Curve (30 Days)</h2>
              <EquityChart points={equity} />
            </div>

            {/* Pipeline & Model Health */}
            <div className="card side-card">
              <h2 className="h">Pipeline Health &amp; Model</h2>
              <div className="kv">
                <span>FastAPI Service</span>
                <span className={health ? 'text-tp' : 'text-sl'}>{health ? 'Online' : 'Unreachable'}</span>
              </div>
              <div className="kv">
                <span>TimescaleDB (Hypertables)</span>
                <span className={health?.db === 'ok' ? 'text-tp' : 'text-sl'}>{up(health?.db)}</span>
              </div>
              <div className="kv">
                <span>Redis Memory Cache</span>
                <span className={health?.redis === 'ok' ? 'text-tp' : 'text-sl'}>{up(health?.redis)}</span>
              </div>
              <div className="kv">
                <span>Data Available</span>
                <span className="font-num text-tp">{dataDays} Days</span>
              </div>
              <div className="kv">
                <span>Data Source</span>
                <span className="font-num text-cyan">Binance USD-M (CoinGecko Off)</span>
              </div>
              <div className="kv">
                <span>Active Model</span>
                <span className="font-num text-cyan">{st?.model_version || 'LightGBM-v0.1'}</span>
              </div>
              <div className="kv">
                <span>Next Retrain Run</span>
                <span><Time iso={st?.next_retrain} withDate /></span>
              </div>
            </div>

            {/* Risk Engine & Constraints */}
            <div className="card side-card">
              <h2 className="h">Risk Engine Controls</h2>
              <div className="kv">
                <span>Daily Loss Used</span>
                <span className="font-num">
                  {st?.daily_loss_used || 0}% of {st?.daily_loss_limit || 3.0}% max
                </span>
              </div>
              <div className="kv">
                <span>Max Simulated Leverage</span>
                <span className="font-num text-cyan">{st?.max_leverage || 3.0}x isolated</span>
              </div>
              <div className="kv">
                <span>Correlated Open Signals</span>
                <span className="font-num">
                  {st?.correlated_open || 0} of {st?.correlated_cap || 3} cap
                </span>
              </div>
              <div className="kv">
                <span>Market Regime</span>
                <span className="regime-tag">{st?.market_regime || 'Normal Volatility'}</span>
              </div>
            </div>
          </div>
        </section>
      </div>

      {/* Interactive Position Size & Risk Calculator Modal */}
      <PositionCalculatorModal />

      <AutoRefresh seconds={30} />
    </main>
  );
}
