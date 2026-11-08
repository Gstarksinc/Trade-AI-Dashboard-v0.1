export function fmtPrice(v) {
  if (v == null) return '-';
  const d = v >= 1000 ? 1 : v >= 10 ? 2 : v >= 1 ? 3 : 4;
  return Number(v).toLocaleString('en-US', { maximumFractionDigits: d });
}

export function fmtPct(v, signed = false) {
  if (v == null) return '-';
  const sign = signed && v > 0 ? '+' : v < 0 ? '\u2212' : '';
  return sign + Math.abs(v).toFixed(1) + '%';
}
