'use client';
import { createContext, useContext, useEffect, useState } from 'react';
import { fmtMoney, fmtTime } from '../lib/format';

const Ctx = createContext(null);
const KEY = 'signals.prefs';

export const usePrefs = () => useContext(Ctx);

export function PrefsProvider({ rates, children }) {
  const [cur, setCur] = useState('USD');
  const [tz, setTz] = useState('UTC');

  // Restore the saved choice after mount, so server and first client render match.
  useEffect(() => {
    try {
      const p = JSON.parse(localStorage.getItem(KEY) || '{}');
      if (p.cur === 'INR' && rates.inr) setCur('INR');
      if (p.tz === 'IST') setTz('IST');
    } catch {}
  }, [rates.inr]);

  const save = (next) => {
    try { localStorage.setItem(KEY, JSON.stringify(next)); } catch {}
  };
  const value = {
    cur, tz, rates,
    setCur: (c) => { setCur(c); save({ cur: c, tz }); },
    setTz: (z) => { setTz(z); save({ cur, tz: z }); },
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function Money({ value }) {
  const { cur, rates } = usePrefs();
  return <>{fmtMoney(value, cur, rates)}</>;
}

export function Time({ iso, withDate = false }) {
  const { tz } = usePrefs();
  return <>{fmtTime(iso, tz, withDate)}</>;
}

function Seg({ label, options, value, onChange, disabled = {} }) {
  return (
    <div className="seg" role="group" aria-label={label}>
      {options.map((o) => (
        <button key={o} className="tf" aria-pressed={value === o} disabled={!!disabled[o]}
          title={disabled[o] ? 'INR rate unavailable' : undefined} onClick={() => onChange(o)}>
          {o}
        </button>
      ))}
    </div>
  );
}

export function PrefToggles() {
  const { cur, tz, setCur, setTz, rates } = usePrefs();
  return (
    <>
      <Seg label="Currency" options={['USD', 'INR']} value={cur} onChange={setCur} disabled={{ INR: !rates.inr }} />
      <Seg label="Time zone" options={['UTC', 'IST']} value={tz} onChange={setTz} />
    </>
  );
}

export function RateNote() {
  const { cur, rates } = usePrefs();
  let text;
  if (cur === 'INR') {
    text = 'Prices converted from USDT at 1 USDT = \u20B9' + Number(rates.inr).toFixed(2) + ' (' + rates.source + ').';
  } else if (!rates.source) {
    text = 'Prices are USDT perpetual prices shown as USD (1 USDT = $1). The INR rate is unavailable.';
  } else {
    text = 'Prices are USDT perpetual prices shown as USD at 1 USDT = $' + Number(rates.usd).toFixed(4) + ' (' + rates.source + ').';
  }
  return <p className="sub pad">{text}</p>;
}
