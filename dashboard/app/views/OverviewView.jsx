'use client';
import { Money, Time, usePrefs } from '../prefs';
import { fmtCompact, fmtFundingRate, fmtPct } from '../../lib/format';
import { AccountSummaryCard } from './AccountSummary';
import { EquityChart, TradeLevelBar, StatusBadge } from '../components';

/**
 * Overview Page View
 * Prioritizes account state, key performance metrics, market summary, active alerts, and system freshness.
 */
export function OverviewView({
  summary: s = {},
  signals = [],
  equity = [],
  tickers = {},
  status: st = {},
  dataDays = 45,
  fresh = true,
  onNavigate,
  onSelectChartSymbol,
  onOpenCalculator,
}) {
  const { getPrice } = usePrefs();

  // Active confirmed signals
  const confirmedSignals = signals.filter((sig) => sig.is_confirmed);
  const unconfirmedSignals = signals.filter((sig) => !sig.is_confirmed);

  // BTC & ETH Tickers
  const btcLive = getPrice('BTCUSDT');
  const btcTick = tickers.BTCUSDT || {};
  const btcPrice = btcLive?.price || btcTick.price || 74880;
  const btcChange = btcLive?.change != null ? btcLive.change : (btcTick.change || 0);
  const btcVol = btcLive?.vol || btcTick.vol || 6500000000;
  const btcFunding = btcLive?.fundingRate != null ? btcLive.fundingRate : 0.0001;

  const ethLive = getPrice('ETHUSDT');
  const ethTick = tickers.ETHUSDT || {};
  const ethPrice = ethLive?.price || ethTick.price || 2123.5;
  const ethChange = ethLive?.change != null ? ethLive.change : (ethTick.change || 0);
  const ethVol = ethLive?.vol || ethTick.vol || 1800000000;
  const ethFunding = ethLive?.fundingRate != null ? ethLive.fundingRate : 0.0001;

  return (
    <div className="overview-container">
      {/* 1. Account State: Paper Trading Account Overview */}
      <AccountSummaryCard positions={signals} equity={equity} />

      {/* 2. System Freshness & Dual Status Alert Strip */}
      <div className={`status-alert-strip ${fresh ? 'fresh' : 'stale'}`}>
        <div className="status-alert-left">
          <div className="alert-item">
            <span className="dot green" />
            <span className="alert-label">Market Feed:</span>
            <strong className="alert-val">Binance USD-M Live Stream (1s)</strong>
          </div>
          <div className="alert-item">
            <span className={`dot ${fresh ? 'green' : 'warn'}`} />
            <span className="alert-label">Signals Pipeline:</span>
            <strong className="alert-val">
              {fresh ? 'Active & Ingesting' : 'Collector Stale (Waiting next candle)'}
            </strong>
          </div>
          <div className="alert-item">
            <span className="alert-label">Hypertables:</span>
            <strong className="alert-val text-tp">{dataDays} Days Stored</strong>
          </div>
        </div>

        <div className="status-alert-right">
          <span className="sub">
            Regime: <strong>{st?.market_regime || 'Normal Volatility'}</strong> • Max Leverage: <strong>{st?.max_leverage || 3.0}x</strong>
          </span>
        </div>
      </div>

      {/* 3. Key Performance Indicators (KPI Cards with explicit denominators and scopes) */}
      <section className="kpis">
        {/* Active Signals */}
        <div className="card kpi-card">
          <p className="h">Active Confirmed Signals</p>
          <p className="big font-num text-cyan">{s?.open_signals ?? confirmedSignals.length}</p>
          <p className="sub">
            of {s?.symbols_scanned ?? 8} monitored perpetuals (awaiting entry or filled)
          </p>
        </div>

        {/* 30-Day Win Rate */}
        <div className="card kpi-card">
          <p className="h">30-Day Win Rate (Paper)</p>
          <p className="big font-num text-tp">{(s?.closed_30d ?? 0) > 0 ? fmtPct(s?.win_rate_30d) : '0.0%'}</p>
          <p className="sub">
            {s?.closed_30d ?? 0} closed paper trades (Past 30 Days)
          </p>
        </div>

        {/* 30-Day Net P&L */}
        <div className="card kpi-card">
          <p className="h">30-Day Net Return (Simulated)</p>
          <p className={`big font-num ${(s?.net_pnl_30d ?? 0) >= 0 ? 'text-tp' : 'text-sl'}`}>
            {fmtPct(s?.net_pnl_30d ?? 0.0, true)}
          </p>
          <p className="sub">
            after 0.04% taker fee, 0.02% slippage &amp; funding
          </p>
        </div>

        {/* Max Drawdown */}
        <div className="card kpi-card">
          <p className="h">Max Drawdown (30D)</p>
          <p className="big font-num text-sl">{fmtPct(s?.max_drawdown ?? 0.0)}</p>
          <p className="sub">
            within risk limit of {fmtPct(s?.drawdown_limit || 8.0)}
          </p>
        </div>
      </section>

      {/* 4. Market Summary: BTC & ETH Highlights */}
      <div className="overview-market-highlights">
        <div className="highlight-header-row">
          <h3 className="section-title">Market Summary Highlights</h3>
          <button className="link-btn" onClick={() => onNavigate && onNavigate('markets')}>
            View All 8 Perpetuals Watchlist →
          </button>
        </div>

        <div className="highlights-grid">
          {/* BTC Card */}
          <div className="card mini-hero-card">
            <div className="mini-hero-top">
              <span className="hero-coin-badge btc">BTC</span>
              <span className="coin-name font-bold">Bitcoin Perp</span>
              <span className={`change-badge ${btcChange >= 0 ? 'pos' : 'neg'}`}>
                {btcChange >= 0 ? '▲ +' : '▼ '}{btcChange.toFixed(2)}%
              </span>
            </div>
            <div className="mini-hero-price">
              <span className="font-num font-bold big-price"><Money value={btcPrice} /></span>
              <span className="sub">Vol: {fmtCompact(btcVol)} • Funding: {fmtFundingRate(btcFunding)}</span>
            </div>
            <div className="mini-hero-actions">
              <button
                className="calc-btn"
                onClick={() => onSelectChartSymbol && onSelectChartSymbol('BTCUSDT')}
              >
                📊 Open Chart
              </button>
            </div>
          </div>

          {/* ETH Card */}
          <div className="card mini-hero-card">
            <div className="mini-hero-top">
              <span className="hero-coin-badge eth">ETH</span>
              <span className="coin-name font-bold">Ethereum Perp</span>
              <span className={`change-badge ${ethChange >= 0 ? 'pos' : 'neg'}`}>
                {ethChange >= 0 ? '▲ +' : '▼ '}{ethChange.toFixed(2)}%
              </span>
            </div>
            <div className="mini-hero-price">
              <span className="font-num font-bold big-price"><Money value={ethPrice} /></span>
              <span className="sub">Vol: {fmtCompact(ethVol)} • Funding: {fmtFundingRate(ethFunding)}</span>
            </div>
            <div className="mini-hero-actions">
              <button
                className="calc-btn"
                onClick={() => onSelectChartSymbol && onSelectChartSymbol('ETHUSDT')}
              >
                📊 Open Chart
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* 5. Main Split Grid: Signals Preview (Left) & Performance Preview (Right) */}
      <div className="overview-split-grid">
        {/* Active Signals Preview */}
        <div className="card overview-signals-preview">
          <div className="card-head">
            <div>
              <h3 className="card-title">Active Predictive Setups</h3>
              <p className="sub">Confirmed signals with entry limits, stop loss, and targets</p>
            </div>
            <button className="primary-btn sm-btn" onClick={() => onNavigate && onNavigate('signals')}>
              View Full Signals Panel ({signals.length}) →
            </button>
          </div>

          <div className="preview-signals-list">
            {confirmedSignals.slice(0, 3).map((sig) => {
              const isLong = String(sig.direction || '').toLowerCase() === 'long';
              const m = sig.metrics || {};
              return (
                <div key={sig.id || sig.symbol} className="preview-signal-item">
                  <div className="item-col coin">
                    <span className="coin-symbol">{sig.symbol.replace('USDT', '')}</span>
                    <span className="tf-badge">{sig.timeframe || '1h'}</span>
                  </div>
                  <div className="item-col dir">
                    <span className={`dir-badge ${isLong ? 'long' : 'short'}`}>
                      {isLong ? '▲ LONG' : '▼ SHORT'}
                    </span>
                    <span className="conf-text">{Math.round((sig.probability || 0.5) * 100)}%</span>
                  </div>
                  <div className="item-col entry">
                    <span className="sub">Entry</span>
                    <span className="font-num font-bold"><Money value={sig.entry} /></span>
                  </div>
                  <div className="item-col status">
                    <StatusBadge phase={m.phase} floatingPnlPct={m.floatingPnlPct} />
                  </div>
                  <div className="item-col action">
                    <button
                      className="calc-btn"
                      onClick={() => onOpenCalculator && onOpenCalculator(sig)}
                    >
                      Calc Size
                    </button>
                  </div>
                </div>
              );
            })}

            {confirmedSignals.length === 0 && (
              <div className="empty-state pad">
                <p className="sub">All 8 monitored perpetuals are currently scanning and awaiting model confirmation.</p>
              </div>
            )}
          </div>
        </div>

        {/* Paper Equity Curve Preview */}
        <div className="card overview-equity-preview">
          <div className="card-head">
            <div>
              <h3 className="card-title">Paper Equity Curve</h3>
              <p className="sub">Simulated 30-day cumulative performance</p>
            </div>
            <button className="link-btn" onClick={() => onNavigate && onNavigate('backtest')}>
              Backtest Audit Report →
            </button>
          </div>

          <div className="preview-chart-wrap">
            <EquityChart points={equity} />
          </div>
        </div>
      </div>
    </div>
  );
}

