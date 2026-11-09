'use client';
import { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react';
import { fmtMoney, fmtTime } from '../lib/format';

const Ctx = createContext(null);
const KEY = 'signals.prefs.v2';

export const usePrefs = () => useContext(Ctx);

export function PrefsProvider({ rates, initialTickers = {}, children }) {
  const [cur, setCur] = useState('USD');
  const [tz, setTz] = useState('UTC');
  const [viewMode, setViewMode] = useState('table'); // 'table' | 'cards'
  const [soundEnabled, setSoundEnabled] = useState(false);
  const [calcSignal, setCalcSignal] = useState(null); // signal to calculate position size for
  const [isCalcOpen, setIsCalcOpen] = useState(false);

  // Real-time live market prices { [symbol]: { price, change, tickDir: 'up' | 'down' } }
  const [livePrices, setLivePrices] = useState(() => {
    const init = {};
    for (const [sym, t] of Object.entries(initialTickers || {})) {
      init[sym] = { price: t.price, change: t.change, high: t.high, low: t.low, tickDir: null, ts: Date.now() };
    }
    return init;
  });

  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = useRef(null);

  // Restore saved preferences
  useEffect(() => {
    try {
      const p = JSON.parse(localStorage.getItem(KEY) || '{}');
      if (p.cur === 'INR' && rates?.inr) setCur('INR');
      if (p.tz === 'IST') setTz('IST');
      if (p.viewMode) setViewMode(p.viewMode);
      if (typeof p.soundEnabled === 'boolean') setSoundEnabled(p.soundEnabled);
    } catch {}
  }, [rates?.inr]);

  const save = useCallback((next) => {
    try {
      const curObj = JSON.parse(localStorage.getItem(KEY) || '{}');
      localStorage.setItem(KEY, JSON.stringify({ ...curObj, ...next }));
    } catch {}
  }, []);

  // Web Audio chime for professional trading feedback
  const playChime = useCallback((type = 'notify') => {
    if (!soundEnabled || typeof window === 'undefined') return;
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) return;
      const ctx = new AudioCtx();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);

      const now = ctx.currentTime;
      if (type === 'target') {
        osc.frequency.setValueAtTime(587.33, now); // D5
        osc.frequency.exponentialRampToValueAtTime(880, now + 0.15); // A5
        gain.gain.setValueAtTime(0.08, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.4);
        osc.start(now);
        osc.stop(now + 0.4);
      } else {
        osc.frequency.setValueAtTime(523.25, now); // C5
        osc.frequency.setValueAtTime(659.25, now + 0.1); // E5
        gain.gain.setValueAtTime(0.06, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.3);
        osc.start(now);
        osc.stop(now + 0.3);
      }
    } catch {}
  }, [soundEnabled]);

  // Connect to Binance Futures public real-time WebSocket mini-ticker
  useEffect(() => {
    if (typeof window === 'undefined') return;
    let isMounted = true;
    let ws = null;
    let reconnectTimer = null;

    function connect() {
      try {
        ws = new WebSocket('wss://fstream.binance.com/ws/!miniTicker@arr');
        wsRef.current = ws;

        ws.onopen = () => {
          if (isMounted) setWsConnected(true);
        };

        ws.onmessage = (event) => {
          if (!isMounted) return;
          try {
            const list = JSON.parse(event.data);
            if (!Array.isArray(list)) return;

            setLivePrices((prev) => {
              let changed = false;
              const next = { ...prev };
              for (const item of list) {
                const sym = item.s;
                const newPrice = Number(item.c);
                if (isNaN(newPrice)) continue;

                const old = prev[sym];
                let tickDir = null;
                if (old && old.price) {
                  if (newPrice > old.price) tickDir = 'up';
                  else if (newPrice < old.price) tickDir = 'down';
                  else tickDir = old.tickDir;
                }

                next[sym] = {
                  price: newPrice,
                  change: old ? old.change : 0,
                  high: Number(item.h) || (old ? old.high : newPrice),
                  low: Number(item.l) || (old ? old.low : newPrice),
                  tickDir,
                  ts: Date.now(),
                };
                changed = true;
              }
              return changed ? next : prev;
            });
          } catch {}
        };

        ws.onerror = () => {
          if (isMounted) setWsConnected(false);
        };

        ws.onclose = () => {
          if (isMounted) {
            setWsConnected(false);
            reconnectTimer = setTimeout(connect, 5000);
          }
        };
      } catch {
        if (isMounted) {
          setWsConnected(false);
          reconnectTimer = setTimeout(connect, 10000);
        }
      }
    }

    connect();

    return () => {
      isMounted = false;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (ws) {
        try { ws.close(); } catch {}
      }
    };
  }, []);

  const getPrice = useCallback((symbol, fallbackPrice) => {
    const item = livePrices[symbol];
    if (item && item.price != null && !isNaN(item.price)) {
      return { price: item.price, tickDir: item.tickDir, change: item.change, high: item.high, low: item.low };
    }
    return { price: fallbackPrice || 0, tickDir: null, change: 0, high: fallbackPrice, low: fallbackPrice };
  }, [livePrices]);

  const openCalculator = (signal) => {
    setCalcSignal(signal);
    setIsCalcOpen(true);
  };

  const closeCalculator = () => {
    setIsCalcOpen(false);
  };

  const value = {
    cur,
    tz,
    rates,
    viewMode,
    soundEnabled,
    livePrices,
    wsConnected,
    isCalcOpen,
    calcSignal,
    setCur: (c) => { setCur(c); save({ cur: c }); },
    setTz: (z) => { setTz(z); save({ tz: z }); },
    setViewMode: (m) => { setViewMode(m); save({ viewMode: m }); },
    setSoundEnabled: (s) => { setSoundEnabled(s); save({ soundEnabled: s }); },
    getPrice,
    playChime,
    openCalculator,
    closeCalculator,
  };

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function Money({ value, className = '' }) {
  const { cur, rates } = usePrefs();
  return <span className={className}>{fmtMoney(value, cur, rates)}</span>;
}

export function Time({ iso, withDate = false }) {
  const { tz } = usePrefs();
  return <>{fmtTime(iso, tz, withDate)}</>;
}

function Seg({ label, options, value, onChange, disabled = {} }) {
  return (
    <div className="seg" role="group" aria-label={label}>
      {options.map((o) => (
        <button
          key={o}
          className="tf"
          aria-pressed={value === o}
          disabled={!!disabled[o]}
          title={disabled[o] ? 'Option unavailable' : undefined}
          onClick={() => onChange(o)}
        >
          {o}
        </button>
      ))}
    </div>
  );
}

export function PrefToggles() {
  const { cur, tz, setCur, setTz, rates, viewMode, setViewMode, soundEnabled, setSoundEnabled, wsConnected } = usePrefs();
  return (
    <div className="pref-bar">
      <div className="pref-group">
        <Seg label="Currency" options={['USD', 'INR']} value={cur} onChange={setCur} disabled={{ INR: !rates?.inr }} />
        <Seg label="Time zone" options={['UTC', 'IST']} value={tz} onChange={setTz} />
        <Seg label="View Mode" options={['Table', 'Cards']} value={viewMode === 'table' ? 'Table' : 'Cards'} onChange={(m) => setViewMode(m.toLowerCase())} />
      </div>
      <div className="pref-group">
        <button
          className={`tf icon-btn ${soundEnabled ? 'active' : ''}`}
          onClick={() => setSoundEnabled(!soundEnabled)}
          title={soundEnabled ? 'Mute audio alerts' : 'Enable audio alerts'}
          aria-label="Toggle sound alerts"
        >
          {soundEnabled ? '🔊 Audio ON' : '🔈 Audio OFF'}
        </button>
        <span className={`chip stream-badge ${wsConnected ? 'live' : 'rest'}`} title={wsConnected ? 'Real-time WebSocket streaming from Binance Futures' : 'Falling back to 30s REST polling'}>
          <span className={`dot ${wsConnected ? 'green' : 'warn'}`} />
          {wsConnected ? 'Live WS' : 'REST 30s'}
        </span>
      </div>
    </div>
  );
}

export function RateNote() {
  const { cur, rates } = usePrefs();
  let text;
  if (cur === 'INR') {
    text = 'Prices converted from USDT at 1 USDT = \u20B9' + Number(rates?.inr || 86.8).toFixed(2) + ' (' + (rates?.source || 'Fallback') + ').';
  } else if (!rates?.source) {
    text = 'Prices are USDT perpetual prices shown as USD (1 USDT = $1). The INR rate is currently falling back.';
  } else {
    text = 'Prices are USDT perpetual prices shown as USD at 1 USDT = $' + Number(rates?.usd || 1).toFixed(4) + ' (' + rates.source + ').';
  }
  return <p className="sub pad">{text}</p>;
}
