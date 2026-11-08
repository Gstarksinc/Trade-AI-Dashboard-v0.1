const API = process.env.API_URL || 'http://api:8000';

// Shown only when the API endpoint is missing or unreachable.
const SAMPLE = {
  summary: { open_signals: 4, symbols_scanned: 30, win_rate_30d: 54.2, closed_30d: 128, net_pnl_30d: 6.8, max_drawdown: -4.1, drawdown_limit: 8 },
  signals: [
    { symbol: 'BTCUSDT', timeframe: '1h', direction: 'long', probability: 0.61, entry: 98420, stop_loss: 97310, take_profit: 100640, status: 'open' },
    { symbol: 'ETHUSDT', timeframe: '15m', direction: 'short', probability: 0.58, entry: 3412.5, stop_loss: 3448, take_profit: 3341.5, status: 'open' },
    { symbol: 'SOLUSDT', timeframe: '4h', direction: 'long', probability: 0.63, entry: 182.4, stop_loss: 176.9, take_profit: 193.4, status: 'open' },
    { symbol: 'BNBUSDT', timeframe: '1h', direction: 'short', probability: 0.56, entry: 702.1, stop_loss: 710.4, take_profit: 685.5, status: 'open' },
    { symbol: 'XRPUSDT', timeframe: '15m', direction: 'long', probability: 0.57, entry: 2.314, stop_loss: 2.281, take_profit: 2.38, status: 'target_hit' },
    { symbol: 'DOGEUSDT', timeframe: '1h', direction: 'short', probability: 0.55, entry: 0.1842, stop_loss: 0.1871, take_profit: 0.1784, status: 'stopped' },
  ],
  equity: [100, 101.2, 100.5, 102.8, 102.1, 104, 103.5, 105.2, 104.6, 106.1, 105.7, 107.3, 106.9, 106.8].map((equity) => ({ equity })),
  status: { last_candle_age_min: 2, model_version: 'sample', next_retrain: 'Sunday 02:00 UTC', daily_loss_used: 1.2, daily_loss_limit: 3, max_leverage: 3, correlated_open: 2, correlated_cap: 3 },
};

async function get(path, fallback) {
  try {
    const res = await fetch(API + path, { cache: 'no-store', signal: AbortSignal.timeout(4000) });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    return { data: await res.json(), live: true };
  } catch {
    return { data: fallback, live: false };
  }
}

export async function loadDashboard() {
  const [summary, signals, equity, status, health] = await Promise.all([
    get('/summary', SAMPLE.summary),
    get('/signals?limit=20', SAMPLE.signals),
    get('/equity?days=30', SAMPLE.equity),
    get('/status', SAMPLE.status),
    get('/health', null),
  ]);
  return {
    summary: summary.data,
    signals: signals.data,
    equity: equity.data,
    status: status.data,
    health: health.data,
    sample: ![summary, signals, equity, status].every((x) => x.live),
  };
}
