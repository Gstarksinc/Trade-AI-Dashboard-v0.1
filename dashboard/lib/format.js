export function fmtPct(v, signed = false, decimals = 1) {
  if (v == null || isNaN(v)) return '-';
  const num = Number(v);
  const sign = signed && num > 0 ? '+' : num < 0 ? '\u2212' : '';
  return sign + Math.abs(num).toFixed(decimals) + '%';
}

const CURRENCY = { USD: { locale: 'en-US', code: 'USD' }, INR: { locale: 'en-IN', code: 'INR' } };

// value is a USDT price; rates = { usd, inr } are the value of 1 USDT in each currency.
export function fmtMoney(value, cur = 'USD', rates = { usd: 1, inr: 86.5 }) {
  if (value == null || isNaN(value)) return '-';
  const rate = cur === 'INR' ? (rates?.inr || 86.5) : (rates?.usd || 1);
  const v = Number(value) * rate;
  const a = Math.abs(v);
  const digits = a >= 1000 ? (a >= 10000 ? 1 : 2) : a >= 10 ? 2 : a >= 1 ? 3 : a >= 0.01 ? 4 : 6;
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

export function fmtTime(iso, tz = 'UTC', withDate = false) {
  if (!iso) return '-';
  try {
    const opts = { timeZone: (ZONES[tz] || ZONES.UTC).zone, hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' };
    if (withDate) Object.assign(opts, { day: '2-digit', month: 'short' });
    return new Intl.DateTimeFormat('en-GB', opts).format(new Date(iso)) + ' ' + (ZONES[tz] || ZONES.UTC).label;
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
 * Calculates trade metrics: Risk, Reward, R:R ratio, distances, floating PnL,
 * and a 0-100 visual progress gauge where 35% is Entry, 0% is Stop Loss, 100% is Take Profit.
 */
export function calcTradeMetrics(signal, currentPrice) {
  const entry = Number(signal.entry);
  const sl = Number(signal.stop_loss);
  const tp = Number(signal.take_profit);
  const isLong = String(signal.direction).toLowerCase() === 'long';
  const cmp = currentPrice != null ? Number(currentPrice) : entry;

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

  // Trade phase logic
  let phase = 'PENDING';
  let isTriggered = false;

  if (signal.status === 'target_hit') {
    phase = 'TARGET_HIT';
  } else if (signal.status === 'stopped') {
    phase = 'STOPPED';
  } else {
    // Check based on CMP
    if (isLong) {
      if (cmp >= tp) {
        phase = 'TARGET_HIT';
      } else if (cmp <= sl) {
        phase = 'STOPPED';
      } else if (Math.abs(cmp - entry) / entry <= 0.002) {
        phase = 'IN_ENTRY_ZONE';
        isTriggered = true;
      } else if (cmp > entry) {
        phase = 'IN_TRADE';
        isTriggered = true;
      } else {
        phase = 'WAITING_ENTRY';
      }
    } else {
      if (cmp <= tp) {
        phase = 'TARGET_HIT';
      } else if (cmp >= sl) {
        phase = 'STOPPED';
      } else if (Math.abs(cmp - entry) / entry <= 0.002) {
        phase = 'IN_ENTRY_ZONE';
        isTriggered = true;
      } else if (cmp < entry) {
        phase = 'IN_TRADE';
        isTriggered = true;
      } else {
        phase = 'WAITING_ENTRY';
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
    isTriggered,
    progressPct,
  };
}
