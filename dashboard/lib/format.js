export function fmtPct(v, signed = false) {
  if (v == null) return '-';
  const sign = signed && v > 0 ? '+' : v < 0 ? '\u2212' : '';
  return sign + Math.abs(v).toFixed(1) + '%';
}

const CURRENCY = { USD: { locale: 'en-US', code: 'USD' }, INR: { locale: 'en-IN', code: 'INR' } };

// value is a USDT price; rates = { usd, inr } are the value of 1 USDT in each currency.
export function fmtMoney(value, cur, rates) {
  if (value == null) return '-';
  const rate = cur === 'INR' ? rates.inr : rates.usd;
  if (!rate) return '-';
  const v = value * rate;
  const a = Math.abs(v);
  const digits = a >= 1000 ? 1 : a >= 10 ? 2 : a >= 1 ? 3 : 4;
  const { locale, code } = CURRENCY[cur];
  return new Intl.NumberFormat(locale, { style: 'currency', currency: code, minimumFractionDigits: 0, maximumFractionDigits: digits }).format(v);
}

export const ZONES = { UTC: { zone: 'UTC', label: 'UTC' }, IST: { zone: 'Asia/Kolkata', label: 'IST' } };

export function fmtTime(iso, tz, withDate = false) {
  if (!iso) return '-';
  const opts = { timeZone: ZONES[tz].zone, hour: '2-digit', minute: '2-digit', hourCycle: 'h23' };
  if (withDate) Object.assign(opts, { day: '2-digit', month: 'short' });
  return new Intl.DateTimeFormat('en-GB', opts).format(new Date(iso)) + ' ' + ZONES[tz].label;
}
