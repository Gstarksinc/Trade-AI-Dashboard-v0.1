const API = process.env.API_URL || 'http://api:8000';
const CG = process.env.COINGECKO_BASE_URL || 'https://api.coingecko.com/api/v3';

const ago = (min) => new Date(Date.now() - min * 60000).toISOString();

function nextSunday0200() {
  const d = new Date();
  d.setUTCHours(2, 0, 0, 0);
  d.setUTCDate(d.getUTCDate() + ((7 - d.getUTCDay()) % 7));
  if (d <= new Date()) d.setUTCDate(d.getUTCDate() + 7);
  return d.toISOString();
}

// Shown only when an API endpoint is missing or unreachable. Prices are USDT.
function sample() {
  return {
    summary: { open_signals: 6, symbols_scanned: 8, win_rate_30d: 54.2, closed_30d: 128, net_pnl_30d: 6.8, max_drawdown: -4.1, drawdown_limit: 8 },
    signals: [
      { symbol: 'BTCUSDT', timeframe: '1h', direction: 'long', probability: 0.61, entry: 98420, stop_loss: 97310, take_profit: 100640, status: 'open', created_at: ago(12) },
      { symbol: 'ETHUSDT', timeframe: '15m', direction: 'short', probability: 0.58, entry: 3412.5, stop_loss: 3448, take_profit: 3341.5, status: 'open', created_at: ago(34) },
      { symbol: 'SOLUSDT', timeframe: '4h', direction: 'long', probability: 0.63, entry: 182.4, stop_loss: 176.9, take_profit: 193.4, status: 'open', created_at: ago(55) },
      { symbol: 'BNBUSDT', timeframe: '1h', direction: 'short', probability: 0.56, entry: 702.1, stop_loss: 710.4, take_profit: 685.5, status: 'open', created_at: ago(83) },
      { symbol: 'TRXUSDT', timeframe: '4h', direction: 'long', probability: 0.57, entry: 0.285, stop_loss: 0.279, take_profit: 0.296, status: 'open', created_at: ago(100) },
      { symbol: 'LINKUSDT', timeframe: '15m', direction: 'short', probability: 0.55, entry: 17.8, stop_loss: 18.1, take_profit: 17.2, status: 'open', created_at: ago(120) },
      { symbol: 'XRPUSDT', timeframe: '15m', direction: 'long', probability: 0.57, entry: 2.314, stop_loss: 2.281, take_profit: 2.38, status: 'target_hit', created_at: ago(190) },
      { symbol: 'DOGEUSDT', timeframe: '1h', direction: 'short', probability: 0.55, entry: 0.1842, stop_loss: 0.1871, take_profit: 0.1784, status: 'stopped', created_at: ago(260) },
    ],
    equity: [100, 101.2, 100.5, 102.8, 102.1, 104, 103.5, 105.2, 104.6, 106.1, 105.7, 107.3, 106.9, 106.8].map((equity) => ({ equity })),
    status: { last_candle_age_min: 2, model_version: 'sample', next_retrain: nextSunday0200(), daily_loss_used: 1.2, daily_loss_limit: 3, max_leverage: 3, correlated_open: 2, correlated_cap: 3 },
  };
}

async function get(path, fallback) {
  try {
    const res = await fetch(API + path, { cache: 'no-store', signal: AbortSignal.timeout(4000) });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    return { data: await res.json(), live: true };
  } catch {
    return { data: fallback, live: false };
  }
}

// Value of 1 USDT in USD and INR (USDT is the quote currency of every contract).
async function loadRates() {
  const fallback = Number(process.env.USDT_INR_FALLBACK) || null;
  try {
    const headers = process.env.COINGECKO_API_KEY ? { 'x-cg-demo-api-key': process.env.COINGECKO_API_KEY } : {};
    const res = await fetch(CG + '/simple/price?ids=tether&vs_currencies=usd,inr', {
      headers, next: { revalidate: 300 }, signal: AbortSignal.timeout(4000),
    });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const t = (await res.json()).tether;
    if (!t || !t.inr) throw new Error('no rate');
    return { usd: t.usd || 1, inr: t.inr, source: 'CoinGecko' };
  } catch {
    return { usd: 1, inr: fallback, source: fallback ? 'fixed fallback rate' : null };
  }
}

export async function loadDashboard() {
  const s = sample();
  const [summary, signals, equity, status, health, rates] = await Promise.all([
    get('/summary', s.summary),
    get('/signals?limit=20', s.signals),
    get('/equity?days=30', s.equity),
    get('/status', s.status),
    get('/health', null),
    loadRates(),
  ]);
  return {
    summary: summary.data,
    signals: signals.data,
    equity: equity.data,
    status: status.data,
    health: health.data,
    rates,
    fetchedAt: new Date().toISOString(),
    sample: ![summary, signals, equity, status].every((x) => x.live),
  };
}
