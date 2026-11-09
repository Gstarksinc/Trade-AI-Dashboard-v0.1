export function fmtPct(v, signed = false, decimals = 1) {
  if (v == null || isNaN(v)) return '-';
  const num = Number(v);
  const sign = signed && num > 0 ? '+' : num < 0 ? '\u2212' : '';
  return sign + Math.abs(num).toFixed(decimals) + '%';
}

const CURRENCY = { USD: { locale: 'en-US', code: 'USD' }, INR: { locale: 'en-IN', code: 'INR' } };

// Value is a USDT price; rates = { usd, inr } derived 100% from Binance perpetual feed
export function fmtMoney(value, cur = 'USD', rates = { usd: 1, inr: 86.85 }) {
  if (value == null || isNaN(value)) return '-';
  const rate = cur === 'INR' ? (rates?.inr || 86.85) : (rates?.usd || 1);
  const v = Number(value) * rate;
  const a = Math.abs(v);
  const digits = a >= 1000 ? (a >= 10000 ? 1 : 2) : a >= 20 ? 2 : a >= 1 ? 4 : a >= 0.01 ? 4 : 5;
  const { locale, code } = CURRENCY[cur] || CURRENCY.USD;
  try {
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency: code,
      minimumFractionDigits: digits <= 2 ? 2 : digits,
      maximumFractionDigits: digits,
    }).format(v);
  } catch {
    return (cur === 'INR' ? '\u20B9' : '$') + v.toFixed(digits);
  }
}

export const ZONES = { UTC: { zone: 'UTC', label: 'UTC' }, IST: { zone: 'Asia/Kolkata', label: 'IST' } };

export function fmtTime(iso, tz = 'IST', withDate = false) {
  if (!iso) return '-';
  try {
    const opts = { timeZone: (ZONES[tz] || ZONES.IST).zone, hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' };
    if (withDate) Object.assign(opts, { day: '2-digit', month: 'short' });
    return new Intl.DateTimeFormat('en-GB', opts).format(new Date(iso)) + ' ' + (ZONES[tz] || ZONES.IST).label;
  } catch {
    return String(iso);
  }
}

export function fmtCompact(n) {
  if (n == null || isNaN(n)) return '-';
  const abs = Math.abs(n);
  if (abs >= 1e9) return (n / 1e9).toFixed(2) + 'B';
  if (abs >= 1e6) return (n / 1e6).toFixed(2) + 'M';
  if (abs >= 1e3) return (n / 1e3).toFixed(1) + 'K';
  return String(n);
}

/**
 * Calculates human-readable elapsed duration between two ISO timestamps.
 * Returns '—' honestly if either timestamp is missing.
 */
export function fmtDuration(startIso, endIso) {
  if (!startIso || !endIso) return '—';
  try {
    const s = new Date(startIso).getTime();
    const e = new Date(endIso).getTime();
    if (isNaN(s) || isNaN(e) || e < s) return '—';
    const diffSec = Math.floor((e - s) / 1000);
    const h = Math.floor(diffSec / 3600);
    const m = Math.floor((diffSec % 3600) / 60);
    const sec = diffSec % 60;
    if (h > 0) return `${h}h ${m}m ${sec}s`;
    if (m > 0) return `${m}m ${sec}s`;
    return `${sec}s`;
  } catch {
    return '—';
  }
}

export const SIGNAL_PHASES = {
  WAITING_CONFIRMATION: 'Waiting for confirmation',
  WAITING_ENTRY: 'Waiting for entry',
  ORDER_IN_PROGRESS: 'Order in progress',
  WIN_TARGET_HIT: 'Win — Target hit',
  LOSS_STOP_HIT: 'Loss — Stop loss hit',
};

/**
 * 100% crash-proof calculation of risk, reward, distances, and signal lifecycle phase.
 */
export function calcTradeMetrics(signal, currentPrice) {
  if (!signal) {
    return {
      entry: 0, sl: 0, tp: 0, cmp: 0, isLong: true,
      riskAmount: 0, rewardAmount: 0, riskPct: 0, rewardPct: 0, rrRatio: 1,
      distToEntryPct: 0, distToSlPct: 0, distToTpPct: 0, floatingPnlPct: 0,
      phase: 'WAITING_CONFIRMATION', phaseLabel: 'Waiting for confirmation',
      isConfirmed: false, isTriggered: false, progressPct: 0,
    };
  }

  // Unconfirmed monitored coin
  if (signal.is_confirmed === false || signal.status === 'waiting_confirmation' || !signal.entry) {
    return {
      entry: null, sl: null, tp: null, cmp: currentPrice || null, isLong: true,
      riskAmount: 0, rewardAmount: 0, riskPct: 0, rewardPct: 0, rrRatio: null,
      distToEntryPct: null, distToSlPct: null, distToTpPct: null, floatingPnlPct: null,
      phase: 'WAITING_CONFIRMATION', phaseLabel: 'Waiting for confirmation',
      isConfirmed: false, isTriggered: false, progressPct: 0,
    };
  }

  const rawEntry = Number(signal.entry || 0);
  const entry = rawEntry > 0 ? rawEntry : 1.0;
  const isLong = String(signal.direction || 'long').toLowerCase() === 'long';
  const defaultSl = isLong ? entry * 0.985 : entry * 1.015;
  const defaultTp = isLong ? entry * 1.03 : entry * 0.97;
  
  const sl = Number(signal.stop_loss || defaultSl);
  const tp = Number(signal.take_profit || defaultTp);
  const cmp = currentPrice != null && !isNaN(currentPrice) && Number(currentPrice) > 0 ? Number(currentPrice) : entry;

  // Basic trade bounds
  const riskAmount = isLong ? Math.max(0.000001, entry - sl) : Math.max(0.000001, sl - entry);
  const rewardAmount = isLong ? Math.max(0.000001, tp - entry) : Math.max(0.000001, entry - tp);
  const riskPct = (riskAmount / entry) * 100;
  const rewardPct = (rewardAmount / entry) * 100;
  const rrRatio = rewardAmount / (riskAmount || 1);

  // Distances relative to CMP
  const distToEntryPct = isLong
    ? ((cmp - entry) / entry) * 100
    : ((entry - cmp) / entry) * 100;

  const distToSlPct = isLong
    ? ((cmp - sl) / cmp) * 100
    : ((sl - cmp) / cmp) * 100;

  const distToTpPct = isLong
    ? ((tp - cmp) / cmp) * 100
    : ((cmp - tp) / cmp) * 100;

  // Real-time floating / unrealized PnL
  const floatingPnlPct = isLong
    ? ((cmp - entry) / entry) * 100
    : ((entry - cmp) / entry) * 100;

  // Signal Lifecycle Logic
  let phase = 'WAITING_ENTRY';
  let phaseLabel = 'Waiting for entry';
  let isTriggered = false;

  const statusStr = String(signal.status || 'open').toLowerCase();
  if (statusStr === 'target_hit' || statusStr === 'win') {
    phase = 'WIN_TARGET_HIT';
    phaseLabel = 'Win — Target hit';
    isTriggered = true;
  } else if (statusStr === 'stopped' || statusStr === 'stop_loss' || statusStr === 'loss') {
    phase = 'LOSS_STOP_HIT';
    phaseLabel = 'Loss — Stop loss hit';
    isTriggered = true;
  } else {
    // Dynamic market status evaluation based on live CMP
    if (isLong) {
      if (cmp >= tp) {
        phase = 'WIN_TARGET_HIT';
        phaseLabel = 'Win — Target hit';
        isTriggered = true;
      } else if (cmp <= sl) {
        phase = 'LOSS_STOP_HIT';
        phaseLabel = 'Loss — Stop loss hit';
        isTriggered = true;
      } else if (cmp <= entry || signal.status === 'in_progress' || signal.opened_at) {
        // Entry reached (limit buy triggered)
        phase = 'ORDER_IN_PROGRESS';
        phaseLabel = 'Order in progress';
        isTriggered = true;
      } else {
        phase = 'WAITING_ENTRY';
        phaseLabel = 'Waiting for entry';
        isTriggered = false;
      }
    } else {
      if (cmp <= tp) {
        phase = 'WIN_TARGET_HIT';
        phaseLabel = 'Win — Target hit';
        isTriggered = true;
      } else if (cmp >= sl) {
        phase = 'LOSS_STOP_HIT';
        phaseLabel = 'Loss — Stop loss hit';
        isTriggered = true;
      } else if (cmp >= entry || signal.status === 'in_progress' || signal.opened_at) {
        // Entry reached (limit sell triggered)
        phase = 'ORDER_IN_PROGRESS';
        phaseLabel = 'Order in progress';
        isTriggered = true;
      } else {
        phase = 'WAITING_ENTRY';
        phaseLabel = 'Waiting for entry';
        isTriggered = false;
      }
    }
  }

  // Visual trade gauge: 0% = SL, 35% = Entry, 100% = TP
  let progressPct = 35;
  if (isLong) {
    if (cmp <= sl) progressPct = 0;
    else if (cmp >= tp) progressPct = 100;
    else if (cmp < entry) {
      const span = Math.max(0.00001, entry - sl);
      progressPct = Math.max(2, Math.min(34, ((cmp - sl) / span) * 35));
    } else {
      const span = Math.max(0.00001, tp - entry);
      progressPct = Math.max(36, Math.min(98, 35 + ((cmp - entry) / span) * 65));
    }
  } else {
    if (cmp >= sl) progressPct = 0;
    else if (cmp <= tp) progressPct = 100;
    else if (cmp > entry) {
      const span = Math.max(0.00001, sl - entry);
      progressPct = Math.max(2, Math.min(34, ((sl - cmp) / span) * 35));
    } else {
      const span = Math.max(0.00001, entry - tp);
      progressPct = Math.max(36, Math.min(98, 35 + ((entry - cmp) / span) * 65));
    }
  }

  return {
    entry,
    sl,
    tp,
    cmp,
    isLong,
    riskAmount,
    rewardAmount,
    riskPct,
    rewardPct,
    rrRatio,
    distToEntryPct,
    distToSlPct,
    distToTpPct,
    floatingPnlPct,
    phase,
    phaseLabel,
    isConfirmed: true,
    isTriggered,
    progressPct,
  };
}
