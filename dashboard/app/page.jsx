import { loadDashboard } from '../lib/data';
import { fmtPct } from '../lib/format';
import { AutoRefresh, EquityChart, MarketTickerTape, PositionCalculatorModal, SessionController, SignalsPanel } from './components';
import { LastUpdatedBadge, LiveClock, PrefToggles, PrefsProvider, Time } from './prefs';

export const dynamic = 'force-dynamic';

const up = (v) => (v === 'ok' ? 'OK' : 'Unreachable');

export default async function Page() {
  const { summary: s, signals, history, equity, status: st, health, rates, tickers, fetchedAt, sample } = await loadDashboard();
  const fresh = (st.last_candle_age_min || 0) <= 20;
  const dataDays = s.data_available_days || st.data_available_days || 45;

  return (
    <PrefsProvider rates={rates} initialTickers={tickers}>
      <main className="page">
        {/* Real-time Market Ticker Tape */}
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
                LightGBM + Meta-Labeling • 15m, 1h and 4h horizons across {s.symbols_scanned} active perpetuals
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
              <p className="big font-num">{s.open_signals}</p>
              <p className="sub">of {s.symbols_scanned} monitored symbols</p>
            </div>
            <div className="card kpi-card">
              <p className="h">Tracked Win Rate</p>
              <p className="big font-num text-tp">{fmtPct(s.win_rate_30d)}</p>
              <p className="sub">{s.closed_30d} closed paper trades (Session)</p>
            </div>
            <div className="card kpi-card">
              <p className="h">Net P&amp;L (30D)</p>
              <p className={`big font-num ${s.net_pnl_30d >= 0 ? 'text-tp' : 'text-sl'}`}>
                {fmtPct(s.net_pnl_30d, true)}
              </p>
              <p className="sub">after fees, slippage &amp; funding</p>
            </div>
            <div className="card kpi-card">
              <p className="h">Max Drawdown</p>
              <p className="big font-num text-sl">{fmtPct(s.max_drawdown)}</p>
              <p className="sub">within limit {fmtPct(s.drawdown_limit)}</p>
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
                  <span className="font-num text-cyan">{st.model_version}</span>
                </div>
                <div className="kv">
                  <span>Next Retrain Run</span>
                  <span><Time iso={st.next_retrain} withDate /></span>
                </div>
              </div>

              {/* Risk Engine & Constraints */}
              <div className="card side-card">
                <h2 className="h">Risk Engine Controls</h2>
                <div className="kv">
                  <span>Daily Loss Used</span>
                  <span className="font-num">
                    {st.daily_loss_used}% of {st.daily_loss_limit}% max
                  </span>
                </div>
                <div className="kv">
                  <span>Max Simulated Leverage</span>
                  <span className="font-num text-cyan">{st.max_leverage}x isolated</span>
                </div>
                <div className="kv">
                  <span>Correlated Open Signals</span>
                  <span className="font-num">
                    {st.correlated_open} of {st.correlated_cap} cap
                  </span>
                </div>
                <div className="kv">
                  <span>Market Regime</span>
                  <span className="regime-tag">{st.market_regime || 'Normal Volatility'}</span>
                </div>
              </div>
            </div>
          </section>
        </div>

        {/* Interactive Position Size & Risk Calculator Modal */}
        <PositionCalculatorModal />

        <AutoRefresh seconds={30} />
      </main>
    </PrefsProvider>
  );
}
