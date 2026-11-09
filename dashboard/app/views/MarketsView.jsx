'use client';
import { useMemo, useState } from 'react';
import { Money, usePrefs } from '../prefs';
import { fmtCompact, fmtFundingRate, fmtPct } from '../../lib/format';

/**
 * Markets & Watchlist View
 * Searchable, sortable Binance USD-M Futures watchlist with prominent BTC & ETH highlights.
 */
export function MarketsView({ tickers = {}, signals = [], onSelectChartSymbol, onOpenCalculator }) {
  const { getPrice } = usePrefs();
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState('volume'); // 'volume' | 'change' | 'price' | 'symbol'
  const [sortDir, setSortDir] = useState('desc');

  const trackedSymbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'DOGEUSDT', 'LINKUSDT', 'TRXUSDT'];

  // Map symbols with live prices, high, low, volume, and funding rates
  const marketRows = useMemo(() => {
    return trackedSymbols.map((sym) => {
      const live = getPrice(sym);
      const tick = tickers[sym] || {};
      const price = live?.price || tick.price || 0;
      const change = live?.change != null ? live.change : (tick.change || 0);
      const high = live?.high || tick.high || 0;
      const low = live?.low || tick.low || 0;
      const vol = live?.vol || tick.vol || 0;
      const fundingRate = live?.fundingRate != null ? live.fundingRate : (tick.fundingRate || 0.0001);
      const tickDir = live?.tickDir;

      // Find if this symbol has an active confirmed signal
      const matchingSignal = signals.find((s) => s.symbol === sym && s.is_confirmed);
      const signalPhase = matchingSignal?.metrics?.phase || 'WAITING_CONFIRMATION';
      const isLong = matchingSignal ? String(matchingSignal.direction || '').toLowerCase() === 'long' : null;

      return {
        symbol: sym,
        base: sym.replace('USDT', ''),
        price,
        change,
        high,
        low,
        vol,
        fundingRate,
        tickDir,
        signalPhase,
        matchingSignal,
        isLong,
      };
    });
  }, [tickers, getPrice, signals]);

  // Filter and sort rows
  const filteredRows = useMemo(() => {
    let rows = marketRows.filter((r) => {
      if (!search.trim()) return true;
      const query = search.trim().toUpperCase();
      return r.symbol.includes(query) || r.base.includes(query);
    });

    rows.sort((a, b) => {
      let diff = 0;
      if (sortBy === 'symbol') diff = a.base.localeCompare(b.base);
      else if (sortBy === 'price') diff = a.price - b.price;
      else if (sortBy === 'change') diff = a.change - b.change;
      else if (sortBy === 'volume') diff = (a.vol || 0) - (b.vol || 0);
      return sortDir === 'asc' ? diff : -diff;
    });

    return rows;
  }, [marketRows, search, sortBy, sortDir]);

  // Highlight items for BTC and ETH
  const btcItem = marketRows.find((r) => r.symbol === 'BTCUSDT');
  const ethItem = marketRows.find((r) => r.symbol === 'ETHUSDT');

  const toggleSort = (col) => {
    if (sortBy === col) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(col);
      setSortDir('desc');
    }
  };

  return (
    <div className="markets-container">
      {/* BTC & ETH Prominent Highlight Hero Cards */}
      <div className="market-heroes-grid">
        {/* BTC Hero */}
        {btcItem && (
          <div className="card market-hero-card is-btc">
            <div className="hero-top">
              <div className="hero-coin-header">
                <span className="hero-coin-badge btc">BTC</span>
                <div>
                  <h3 className="hero-coin-title">Bitcoin Perpetual</h3>
                  <span className="hero-coin-subtitle">BTC/USDT • Binance USD-M</span>
                </div>
              </div>
              <span className={`hero-change-pill ${btcItem.change >= 0 ? 'pos' : 'neg'}`}>
                {btcItem.change >= 0 ? '▲ +' : '▼ '}{btcItem.change.toFixed(2)}%
              </span>
            </div>

            <div className="hero-price-row">
              <div className="hero-cmp-box">
                <span className="hero-price-label">Live Price (CMP)</span>
                <span className={`hero-price-val font-num font-bold ${btcItem.tickDir ? `tick-${btcItem.tickDir}` : ''}`}>
                  <Money value={btcItem.price} />
                </span>
              </div>
              <div className="hero-meta-stats">
                <div className="h-stat">
                  <span className="h-stat-label">24h High</span>
                  <span className="h-stat-val font-num"><Money value={btcItem.high} /></span>
                </div>
                <div className="h-stat">
                  <span className="h-stat-label">24h Low</span>
                  <span className="h-stat-val font-num"><Money value={btcItem.low} /></span>
                </div>
                <div className="h-stat">
                  <span className="h-stat-label">24h Volume</span>
                  <span className="h-stat-val font-num">{fmtCompact(btcItem.vol)}</span>
                </div>
                <div className="h-stat">
                  <span className="h-stat-label">Funding Rate</span>
                  <span className="h-stat-val font-num text-cyan">{fmtFundingRate(btcItem.fundingRate)}</span>
                </div>
              </div>
            </div>

            <div className="hero-actions">
              <button
                className="primary-btn hero-chart-btn"
                onClick={() => onSelectChartSymbol && onSelectChartSymbol('BTCUSDT')}
              >
                📊 Open Candlestick Chart
              </button>
              {btcItem.matchingSignal && (
                <button
                  className="calc-btn hero-calc-btn"
                  onClick={() => onOpenCalculator && onOpenCalculator(btcItem.matchingSignal)}
                >
                  ⚡ Calc Position Size
                </button>
              )}
            </div>
          </div>
        )}

        {/* ETH Hero */}
        {ethItem && (
          <div className="card market-hero-card is-eth">
            <div className="hero-top">
              <div className="hero-coin-header">
                <span className="hero-coin-badge eth">ETH</span>
                <div>
                  <h3 className="hero-coin-title">Ethereum Perpetual</h3>
                  <span className="hero-coin-subtitle">ETH/USDT • Binance USD-M</span>
                </div>
              </div>
              <span className={`hero-change-pill ${ethItem.change >= 0 ? 'pos' : 'neg'}`}>
                {ethItem.change >= 0 ? '▲ +' : '▼ '}{ethItem.change.toFixed(2)}%
              </span>
            </div>

            <div className="hero-price-row">
              <div className="hero-cmp-box">
                <span className="hero-price-label">Live Price (CMP)</span>
                <span className={`hero-price-val font-num font-bold ${ethItem.tickDir ? `tick-${ethItem.tickDir}` : ''}`}>
                  <Money value={ethItem.price} />
                </span>
              </div>
              <div className="hero-meta-stats">
                <div className="h-stat">
                  <span className="h-stat-label">24h High</span>
                  <span className="h-stat-val font-num"><Money value={ethItem.high} /></span>
                </div>
                <div className="h-stat">
                  <span className="h-stat-label">24h Low</span>
                  <span className="h-stat-val font-num"><Money value={ethItem.low} /></span>
                </div>
                <div className="h-stat">
                  <span className="h-stat-label">24h Volume</span>
                  <span className="h-stat-val font-num">{fmtCompact(ethItem.vol)}</span>
                </div>
                <div className="h-stat">
                  <span className="h-stat-label">Funding Rate</span>
                  <span className="h-stat-val font-num text-cyan">{fmtFundingRate(ethItem.fundingRate)}</span>
                </div>
              </div>
            </div>

            <div className="hero-actions">
              <button
                className="primary-btn hero-chart-btn"
                onClick={() => onSelectChartSymbol && onSelectChartSymbol('ETHUSDT')}
              >
                📊 Open Candlestick Chart
              </button>
              {ethItem.matchingSignal && (
                <button
                  className="calc-btn hero-calc-btn"
                  onClick={() => onOpenCalculator && onOpenCalculator(ethItem.matchingSignal)}
                >
                  ⚡ Calc Position Size
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Main Futures Watchlist Card */}
      <div className="card watchlist-card">
        <div className="watchlist-head">
          <div>
            <h2 className="card-title">Binance USDT-M Futures Watchlist</h2>
            <p className="sub">Real-time streaming prices, 24h ranges, quote volumes, and funding rates across all {trackedSymbols.length} perpetuals</p>
          </div>
          <div className="watchlist-controls">
            <div className="search-wrap">
              <input
                type="text"
                className="search-input"
                placeholder="Search symbol (e.g. SOL, BNB)..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <div className="sort-pill-wrap">
              <span className="sort-label">Sort:</span>
              <button
                className={`sort-pill ${sortBy === 'volume' ? 'active' : ''}`}
                onClick={() => toggleSort('volume')}
              >
                Volume {sortBy === 'volume' && (sortDir === 'desc' ? '▼' : '▲')}
              </button>
              <button
                className={`sort-pill ${sortBy === 'change' ? 'active' : ''}`}
                onClick={() => toggleSort('change')}
              >
                24h Change {sortBy === 'change' && (sortDir === 'desc' ? '▼' : '▲')}
              </button>
              <button
                className={`sort-pill ${sortBy === 'price' ? 'active' : ''}`}
                onClick={() => toggleSort('price')}
              >
                Price {sortBy === 'price' && (sortDir === 'desc' ? '▼' : '▲')}
              </button>
            </div>
          </div>
        </div>

        <div className="table-container">
          <table className="signals-table watchlist-table">
            <thead>
              <tr>
                <th onClick={() => toggleSort('symbol')} className="sortable-th">
                  Asset {sortBy === 'symbol' && (sortDir === 'desc' ? '▼' : '▲')}
                </th>
                <th onClick={() => toggleSort('price')} className="sortable-th">
                  Live Price (CMP) {sortBy === 'price' && (sortDir === 'desc' ? '▼' : '▲')}
                </th>
                <th onClick={() => toggleSort('change')} className="sortable-th">
                  24h Change {sortBy === 'change' && (sortDir === 'desc' ? '▼' : '▲')}
                </th>
                <th>24h High</th>
                <th>24h Low</th>
                <th onClick={() => toggleSort('volume')} className="sortable-th">
                  24h Volume {sortBy === 'volume' && (sortDir === 'desc' ? '▼' : '▲')}
                </th>
                <th>Funding Rate (8h)</th>
                <th>Model Signal Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredRows.map((r) => {
                const tickClass = r.tickDir ? `tick-${r.tickDir}` : '';
                return (
                  <tr key={r.symbol} className="market-row">
                    <td>
                      <div className="sym-cell">
                        <span className="coin-symbol">{r.base}</span>
                        <span className="sym-meta">
                          <span className="perp-badge">PERP</span>
                          <span className="sub font-num">USDT</span>
                        </span>
                      </div>
                    </td>

                    <td>
                      <div className={`cmp-cell ${tickClass}`}>
                        <span className="live-dot pulse" />
                        <span className="cmp-val font-num font-bold">
                          <Money value={r.price} />
                        </span>
                      </div>
                    </td>

                    <td>
                      <span className={`change-badge ${r.change >= 0 ? 'pos' : 'neg'}`}>
                        {r.change >= 0 ? '▲ +' : '▼ '}{r.change.toFixed(2)}%
                      </span>
                    </td>

                    <td>
                      <span className="font-num text-muted"><Money value={r.high} /></span>
                    </td>

                    <td>
                      <span className="font-num text-muted"><Money value={r.low} /></span>
                    </td>

                    <td>
                      <span className="font-num font-bold">{fmtCompact(r.vol)}</span>
                    </td>

                    <td>
                      <span className="font-num text-cyan funding-badge">
                        {fmtFundingRate(r.fundingRate)}
                      </span>
                    </td>

                    <td>
                      {r.matchingSignal ? (
                        <div className="market-signal-badge-wrap">
                          <span className={`dir-badge ${r.isLong ? 'long' : 'short'}`}>
                            {r.isLong ? '▲ LONG' : '▼ SHORT'}
                          </span>
                          <span className="badge-status badge-waiting-entry">
                            {r.matchingSignal.metrics?.phaseLabel || 'Active Setup'}
                          </span>
                        </div>
                      ) : (
                        <span className="badge-status badge-waiting-conf">
                          ⏳ Waiting for confirmation
                        </span>
                      )}
                    </td>

                    <td>
                      <div className="market-row-actions">
                        <button
                          className="calc-btn chart-action-btn"
                          onClick={() => onSelectChartSymbol && onSelectChartSymbol(r.symbol)}
                          title="Open Candlestick Chart"
                        >
                          📊 Chart
                        </button>
                        {r.matchingSignal && (
                          <button
                            className="calc-btn"
                            onClick={() => onOpenCalculator && onOpenCalculator(r.matchingSignal)}
                            title="Calculate Position Size"
                          >
                            Calc Size
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {filteredRows.length === 0 && (
            <div className="empty-state">
              <p className="sub pad">No perpetual symbols match your search "{search}".</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

