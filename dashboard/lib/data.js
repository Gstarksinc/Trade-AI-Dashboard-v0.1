const API = process.env.API_URL || 'http://api:8000';
const CG = process.env.COINGECKO_BASE_URL || 'https://api.coingecko.com/api/v3';
const BINANCE_FAPI = process.env.BINANCE_FAPI_URL || 'https://fapi.binance.com';

const ago = (min) => new Date(Date.now() - min * 60000).toISOString();

function nextSunday0200() {
  const d = new Date();
  d.setUTCHours(2, 0, 0, 0);
  d.setUTCDate(d.getUTCDate() + ((7 - d.getUTCDay()) % 7));
  if (d <= new Date()) d.setUTCDate(d.getUTCDate() + 7);
  return d.toISOString();
}

// Default fallback tickers if Binance is unreachable
const DEFAULT_TICKERS = {
  BTCUSDT: { price: 74250.0, change: 1.85, high: 75200.0, low: 73100.0, vol: '2.4B' },
  ETHUSDT: { price: 3415.5, change: -0.62, high: 3490.0, low: 3370.0, vol: '1.1B' },
  SOLUSDT: { price: 184.2, change: 3.45, high: 188.5, low: 178.0, vol: '840M' },
  BNBUSDT: { price: 704.8, change: 0.32, high: 712.0, low: 698.0, vol: '310M' },
  XRPUSDT: { price: 2.345, change: 4.12, high: 2.42, low: 2.25, vol: '520M' },
  DOGEUSDT: { price: 0.1835, change: -1.75, high: 0.191, low: 0.181, vol: '290M' },
  LINKUSDT: { price: 17.65, change: 1.15, high: 18.2, low: 17.1, vol: '180M' },
  TRXUSDT: { price: 0.2865, change: 0.45, high: 0.292, low: 0.282, vol: '95M' },
};

// Shown only when an API endpoint is missing or unreachable. Prices are in USDT.
function sample(livePrices = {}) {
  const btcPrice = livePrices.BTCUSDT?.price || 74250;
  const ethPrice = livePrices.ETHUSDT?.price || 3415.5;
  const solPrice = livePrices.SOLUSDT?.price || 184.2;
  const bnbPrice = livePrices.BNBUSDT?.price || 704.8;
  const trxPrice = livePrices.TRXUSDT?.price || 0.2865;
  const linkPrice = livePrices.LINKUSDT?.price || 17.65;
  const xrpPrice = livePrices.XRPUSDT?.price || 2.345;
  const dogePrice = livePrices.DOGEUSDT?.price || 0.1835;

  return {
    summary: {
      open_signals: 6,
      symbols_scanned: 8,
      win_rate_30d: 58.4,
      closed_30d: 142,
      net_pnl_30d: 8.4,
      max_drawdown: -3.8,
      drawdown_limit: 8.0,
      profit_factor: 1.74,
      avg_rr: 2.3,
    },
    signals: [
      {
        id: 1,
        symbol: 'BTCUSDT',
        timeframe: '1h',
        direction: 'long',
        probability: 0.64,
        meta_probability: 0.76,
        current_price: btcPrice,
        entry: Math.round(btcPrice * 0.998),
        stop_loss: Math.round(btcPrice * 0.987),
        take_profit: Math.round(btcPrice * 1.022),
        atr: 820.0,
        status: 'open',
        created_at: ago(12),
        model_version: 'lgb-meta-v0.1',
      },
      {
        id: 2,
        symbol: 'ETHUSDT',
        timeframe: '15m',
        direction: 'short',
        probability: 0.59,
        meta_probability: 0.68,
        current_price: ethPrice,
        entry: Number((ethPrice * 1.002).toFixed(1)),
        stop_loss: Number((ethPrice * 1.011).toFixed(1)),
        take_profit: Number((ethPrice * 0.981).toFixed(1)),
        atr: 38.5,
        status: 'open',
        created_at: ago(28),
        model_version: 'lgb-meta-v0.1',
      },
      {
        id: 3,
        symbol: 'SOLUSDT',
        timeframe: '4h',
        direction: 'long',
        probability: 0.67,
        meta_probability: 0.81,
        current_price: solPrice,
        entry: Number((solPrice * 0.996).toFixed(2)),
        stop_loss: Number((solPrice * 0.968).toFixed(2)),
        take_profit: Number((solPrice * 1.058).toFixed(2)),
        atr: 6.4,
        status: 'open',
        created_at: ago(55),
        model_version: 'lgb-meta-v0.1',
      },
      {
        id: 4,
        symbol: 'BNBUSDT',
        timeframe: '1h',
        direction: 'short',
        probability: 0.58,
        meta_probability: 0.70,
        current_price: bnbPrice,
        entry: Number((bnbPrice * 1.003).toFixed(1)),
        stop_loss: Number((bnbPrice * 1.014).toFixed(1)),
        take_profit: Number((bnbPrice * 0.978).toFixed(1)),
        atr: 8.9,
        status: 'open',
        created_at: ago(82),
        model_version: 'lgb-meta-v0.1',
      },
      {
        id: 5,
        symbol: 'TRXUSDT',
        timeframe: '4h',
        direction: 'long',
        probability: 0.61,
        meta_probability: 0.72,
        current_price: trxPrice,
        entry: Number((trxPrice * 0.995).toFixed(4)),
        stop_loss: Number((trxPrice * 0.975).toFixed(4)),
        take_profit: Number((trxPrice * 1.038).toFixed(4)),
        atr: 0.007,
        status: 'open',
        created_at: ago(110),
        model_version: 'lgb-meta-v0.1',
      },
      {
        id: 6,
        symbol: 'LINKUSDT',
        timeframe: '15m',
        direction: 'short',
        probability: 0.56,
        meta_probability: 0.65,
        current_price: linkPrice,
        entry: Number((linkPrice * 1.004).toFixed(2)),
        stop_loss: Number((linkPrice * 1.016).toFixed(2)),
        take_profit: Number((linkPrice * 0.976).toFixed(2)),
        atr: 0.42,
        status: 'open',
        created_at: ago(140),
        model_version: 'lgb-meta-v0.1',
      },
      {
        id: 7,
        symbol: 'XRPUSDT',
        timeframe: '15m',
        direction: 'long',
        probability: 0.63,
        meta_probability: 0.78,
        current_price: xrpPrice,
        entry: Number((xrpPrice * 0.97).toFixed(3)),
        stop_loss: Number((xrpPrice * 0.95).toFixed(3)),
        take_profit: Number((xrpPrice * 1.02).toFixed(3)),
        atr: 0.045,
        status: 'target_hit',
        created_at: ago(210),
        model_version: 'lgb-meta-v0.1',
      },
      {
        id: 8,
        symbol: 'DOGEUSDT',
        timeframe: '1h',
        direction: 'short',
        probability: 0.54,
        meta_probability: 0.61,
        current_price: dogePrice,
        entry: Number((dogePrice * 1.02).toFixed(4)),
        stop_loss: Number((dogePrice * 1.04).toFixed(4)),
        take_profit: Number((dogePrice * 0.97).toFixed(4)),
        atr: 0.006,
        status: 'stopped',
        created_at: ago(320),
        model_version: 'lgb-meta-v0.1',
      },
    ],
    equity: [
      { ts: ago(30 * 1440), equity: 100 },
      { ts: ago(27 * 1440), equity: 101.4 },
      { ts: ago(24 * 1440), equity: 100.8 },
      { ts: ago(21 * 1440), equity: 102.9 },
      { ts: ago(18 * 1440), equity: 102.2 },
      { ts: ago(15 * 1440), equity: 104.5 },
      { ts: ago(12 * 1440), equity: 103.9 },
      { ts: ago(9 * 1440), equity: 105.8 },
      { ts: ago(6 * 1440), equity: 105.1 },
      { ts: ago(4 * 1440), equity: 107.0 },
      { ts: ago(2 * 1440), equity: 106.6 },
      { ts: ago(1 * 1440), equity: 108.2 },
      { ts: ago(0), equity: 108.4 },
    ],
    status: {
      last_candle_age_min: 1,
      model_version: 'LightGBM-v0.1 + Meta-Filter',
      next_retrain: nextSunday0200(),
      daily_loss_used: 0.85,
      daily_loss_limit: 3.0,
      max_leverage: 3.0,
      correlated_open: 2,
      correlated_cap: 3,
      market_regime: 'Moderate Volatility / Bullish Bias',
    },
  };
}

async function get(path, fallback) {
  try {
    const res = await fetch(API + path, { cache: 'no-store', signal: AbortSignal.timeout(3500) });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    return { data: await res.json(), live: true };
  } catch {
    return { data: fallback, live: false };
  }
}

// Fetches live 24h ticker prices from Binance Futures public REST endpoint.
async function loadBinanceTickers() {
  const tracked = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'DOGEUSDT', 'LINKUSDT', 'TRXUSDT'];
  try {
    const res = await fetch(`${BINANCE_FAPI}/fapi/v1/ticker/24hr`, {
      next: { revalidate: 10 },
      signal: AbortSignal.timeout(3000),
    });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const list = await res.json();
    const map = {};
    for (const item of list) {
      if (tracked.includes(item.symbol)) {
        map[item.symbol] = {
          symbol: item.symbol,
          price: Number(item.lastPrice),
          change: Number(item.priceChangePercent),
          high: Number(item.highPrice),
          low: Number(item.lowPrice),
          vol: Number(item.quoteVolume),
        };
      }
    }
    return map;
  } catch {
    return DEFAULT_TICKERS;
  }
}

// Value of 1 USDT in USD and INR (USDT is the quote currency of every contract).
async function loadRates() {
  const fallback = Number(process.env.USDT_INR_FALLBACK) || 86.85;
  try {
    const headers = process.env.COINGECKO_API_KEY ? { 'x-cg-demo-api-key': process.env.COINGECKO_API_KEY } : {};
    const res = await fetch(CG + '/simple/price?ids=tether&vs_currencies=usd,inr', {
      headers,
      next: { revalidate: 300 },
      signal: AbortSignal.timeout(3500),
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
  const [tickers, rates] = await Promise.all([
    loadBinanceTickers(),
    loadRates(),
  ]);

  const s = sample(tickers);

  const [summary, signals, equity, status, health] = await Promise.all([
    get('/summary', s.summary),
    get('/signals?limit=25', s.signals),
    get('/equity?days=30', s.equity),
    get('/status', s.status),
    get('/health', null),
  ]);

  // Use live signals if present; otherwise fall back to predictive sample setups
  const rawSignals = (Array.isArray(signals.data) && signals.data.length > 0)
    ? signals.data
    : s.signals;

  // Enrich signals with live market price if not already provided by backend
  const enrichedSignals = rawSignals.map((sig) => {
    const tick = tickers[sig.symbol];
    const cmp = sig.current_price || tick?.price || sig.entry;
    const change24h = tick?.change || 0;
    return {
      ...sig,
      current_price: cmp,
      change_24h: change24h,
    };
  });

  const finalSummary = {
    ...s.summary,
    ...summary.data,
    open_signals: (summary.data?.open_signals > 0)
      ? summary.data.open_signals
      : enrichedSignals.filter((x) => x.status === 'open').length,
  };

  return {
    summary: finalSummary,
    signals: enrichedSignals,
    equity: equity.data && equity.data.length > 0 ? equity.data : s.equity,
    status: status.data || s.status,
    health: health.data,
    rates,
    tickers,
    fetchedAt: new Date().toISOString(),
    sample: !signals.live || !signals.data || signals.data.length === 0,
  };
}
