import { loadDashboard } from '../lib/data';
import { DashboardShell } from './components';
import { PrefsProvider } from './prefs';

export const dynamic = 'force-dynamic';

export default async function Page() {
  const { summary: s, signals, history, equity, status: st, health, rates, tickers, fetchedAt, sample } = await loadDashboard();
  const fresh = (st.last_candle_age_min || 0) <= 20;
  const dataDays = s.data_available_days || st.data_available_days || 45;

  return (
    <PrefsProvider rates={rates} initialTickers={tickers}>
      <DashboardShell
        summary={s}
        signals={signals}
        history={history}
        equity={equity}
        status={st}
        health={health}
        rates={rates}
        tickers={tickers}
        dataDays={dataDays}
        sample={sample}
        fresh={fresh}
      />
    </PrefsProvider>
  );
}
