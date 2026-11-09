import { loadDashboard } from '../lib/data';
import { fmtPct } from '../lib/format';
import { AutoRefresh, EquityChart, SignalsPanel } from './components';
import { PrefToggles, PrefsProvider, Time } from './prefs';

export const dynamic = 'force-dynamic';

const up = (v) => (v === 'ok' ? 'OK' : 'Unreachable');

export default async function Page() {
  const { summary: s, signals, equity, status: st, health, rates, fetchedAt, sample } = await loadDashboard();
  const fresh = st.last_candle_age_min <= 20;
  return (
    <PrefsProvider rates={rates}>
    <main className="page">
      <div className="wrap">
        <header className="top">
          <div>
            <h1>Signal Dashboard</h1>
            <p className="sub">Crypto futures: 15m, 1h and 4h signals across {s.symbols_scanned} symbols</p>
          </div>
          <div className="chips">
            <PrefToggles />
            <span className="chip">Paper mode</span>
            {sample && <span className="chip">Sample data</span>}
            <span className="chip">Updated <Time iso={fetchedAt} /></span>
            <span className="chip"><span className={fresh ? 'dot' : 'dot warn'} />{fresh ? 'Collector healthy' : 'Collector stale'}</span>
          </div>
        </header>

        <section className="kpis">
          <div className="card"><p className="h">Open signals</p><p className="big">{s.open_signals}</p><p className="sub">of {s.symbols_scanned} symbols scanned</p></div>
          <div className="card"><p className="h">Win rate, 30 days</p><p className="big">{fmtPct(s.win_rate_30d)}</p><p className="sub">{s.closed_30d} closed signals</p></div>
          <div className="card"><p className="h">Net P&amp;L, 30 days</p><p className="big">{fmtPct(s.net_pnl_30d, true)}</p><p className="sub">after fees, slippage, funding</p></div>
          <div className="card"><p className="h">Max drawdown</p><p className="big">{fmtPct(s.max_drawdown)}</p><p className="sub">limit {fmtPct(s.drawdown_limit)}</p></div>
        </section>

        <section className="grid">
          <SignalsPanel signals={signals} />
          <div className="side">
            <div className="card">
              <h2 className="h">Paper equity, 30 days</h2>
              <EquityChart points={equity} />
            </div>
            <div className="card">
              <h2 className="h">Pipeline health</h2>
              <div className="kv"><span>API</span><span>{health ? 'OK' : 'Unreachable'}</span></div>
              <div className="kv"><span>Database</span><span>{up(health && health.db)}</span></div>
              <div className="kv"><span>Redis cache</span><span>{up(health && health.redis)}</span></div>
              <div className="kv"><span>Last 15m candle</span><span>{st.last_candle_age_min} min ago</span></div>
              <div className="kv"><span>Model</span><span>{st.model_version}</span></div>
              <div className="kv"><span>Next retrain</span><span><Time iso={st.next_retrain} withDate /></span></div>
            </div>
            <div className="card">
              <h2 className="h">Risk limits</h2>
              <div className="kv"><span>Daily loss used</span><span>{st.daily_loss_used}% of {st.daily_loss_limit}%</span></div>
              <div className="kv"><span>Max leverage</span><span>{st.max_leverage}x simulated</span></div>
              <div className="kv"><span>Correlated open signals</span><span>{st.correlated_open} of {st.correlated_cap}</span></div>
            </div>
          </div>
        </section>
      </div>
      <AutoRefresh seconds={30} />
    </main>
    </PrefsProvider>
  );
}
