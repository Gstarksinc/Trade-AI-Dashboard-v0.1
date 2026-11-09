'use client';
import { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react';
import { fmtMoney, fmtTime } from '../lib/format';

const Ctx = createContext(null);
const KEY = 'signals.prefs.v4';
const SESSION_KEY = 'signals.session.v1';

export const usePrefs = () => useContext(Ctx);

export function PrefsProvider({ rates, initialTickers = {}, children }) {
  const [cur, setCur] = useState('USD');
  const [tz, setTz] = useState('IST'); // Default to IST since user is in IST
  const [viewMode, setViewMode] = useState('table'); // 'table' | 'cards'
  const [soundEnabled, setSoundEnabled] = useState(false);
  const [calcSignal, setCalcSignal] = useState(null);
  const [isCalcOpen, setIsCalcOpen] = useState(false);

  // Light / Dark Theme State
  const [theme, setTheme] = useState('dark');

  // Terminal Authentication State
  const [authSession, setAuthSession] = useState(null);
  const [isAuthChecking, setIsAuthChecking] = useState(true);

  // Paper Trading Session State (Win Rate Controller)
  const [isSessionRunning, setIsSessionRunning] = useState(true);
  const [sessionStartTime, setSessionStartTime] = useState(null);
  const [sessionStats, setSessionStats] = useState({
    winRate: 58.4,
    closedTrades: 142,
    netPnl: 8.4,
    isReset: false,
  });

  // Real-time live market prices { [symbol]: { price, change, tickDir: 'up' | 'down', ts } }
  const [livePrices, setLivePrices] = useState(() => {
    const init = {};
    for (const [sym, t] of Object.entries(initialTickers || {})) {
      init[sym] = {
        price: t.price,
        change: t.change,
        high: t.high,
        low: t.low,
        tickDir: null,
        ts: Date.now(),
      };
    }
    return init;
  });

  const [wsConnected, setWsConnected] = useState(false);
  const [lastUpdateTs, setLastUpdateTs] = useState(Date.now());
  const [secondsAgo, setSecondsAgo] = useState(0);
  const [currentTime, setCurrentTime] = useState(new Date());
  const wsRef = useRef(null);

  // Restore saved preferences, theme, and authentication session
  useEffect(() => {
    try {
      const p = JSON.parse(localStorage.getItem(KEY) || '{}');
      if (p.cur === 'INR' && rates?.inr) setCur('INR');
      if (p.tz) setTz(p.tz);
      if (p.viewMode) setViewMode(p.viewMode);
      if (typeof p.soundEnabled === 'boolean') setSoundEnabled(p.soundEnabled);

      const savedTheme = localStorage.getItem('tradeai_theme') || 'dark';
      setTheme(savedTheme);
      document.documentElement.setAttribute('data-theme', savedTheme);

      const savedAuth = JSON.parse(localStorage.getItem('tradeai_auth') || 'null');
      if (savedAuth && (savedAuth.email || savedAuth.name)) {
        setAuthSession(savedAuth);
      }

      const sess = JSON.parse(localStorage.getItem(SESSION_KEY) || '{}');
      if (sess.sessionStartTime) setSessionStartTime(sess.sessionStartTime);
      if (typeof sess.isSessionRunning === 'boolean') setIsSessionRunning(sess.isSessionRunning);
      if (sess.sessionStats) setSessionStats(sess.sessionStats);
      else setSessionStartTime(new Date().toISOString());
    } catch {}
    setIsAuthChecking(false);
  }, [rates?.inr]);

  const toggleTheme = useCallback(() => {
    setTheme((prev) => {
      const next = prev === 'dark' ? 'light' : 'dark';
      try {
        localStorage.setItem('tradeai_theme', next);
        document.documentElement.setAttribute('data-theme', next);
      } catch {}
      return next;
    });
  }, []);

  const login = useCallback((creds = {}) => {
    const session = {
      email: creds.email || 'trader@tradeai.pro',
      name: creds.name || 'Pro Trader',
      role: 'Institutional Quant',
      sessionId: 'SESSION-' + Math.floor(1000 + Math.random() * 9000),
      loginTime: new Date().toISOString(),
    };
    try {
      localStorage.setItem('tradeai_auth', JSON.stringify(session));
    } catch {}
    setAuthSession(session);
  }, []);

  const logout = useCallback(() => {
    try {
      localStorage.removeItem('tradeai_auth');
    } catch {}
    setAuthSession(null);
  }, []);

  const save = useCallback((next) => {
    try {
      const curObj = JSON.parse(localStorage.getItem(KEY) || '{}');
      localStorage.setItem(KEY, JSON.stringify({ ...curObj, ...next }));
    } catch {}
  }, []);

  const saveSession = useCallback((sess) => {
    try {
      localStorage.setItem(SESSION_KEY, JSON.stringify(sess));
    } catch {}
  }, []);

  // Session Control: Reset Win Rate & Trade Stats to restart testing
  const resetWinRate = useCallback(() => {
    const freshStats = {
      winRate: 0.0,
      closedTrades: 0,
      netPnl: 0.0,
      isReset: true,
    };
    const nowIso = new Date().toISOString();
    setSessionStats(freshStats);
    setSessionStartTime(nowIso);
    setIsSessionRunning(true);
    saveSession({ sessionStats: freshStats, sessionStartTime: nowIso, isSessionRunning: true });
  }, [saveSession]);

  const toggleSessionRunning = useCallback(() => {
    setIsSessionRunning((prev) => {
      const next = !prev;
      saveSession({ sessionStats, sessionStartTime, isSessionRunning: next });
      return next;
    });
  }, [sessionStats, sessionStartTime, saveSession]);

  // 1. Live Clock ticking every 1000ms
  useEffect(() => {
    const timer = setInterval(() => {
      const now = new Date();
      setCurrentTime(now);
      setSecondsAgo(Math.max(0, Math.floor((now.getTime() - lastUpdateTs) / 1000)));
    }, 1000);
    return () => clearInterval(timer);
  }, [lastUpdateTs]);

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

  // 2. High-Frequency Real-Time Price Polling (every 1.2s via local route handler)
  useEffect(() => {
    let isMounted = true;

    async function pollLivePrices() {
      try {
        const res = await fetch('/api/live-prices', { cache: 'no-store' });
        if (!res.ok) return;
        const data = await res.json();
        if (!data.success || !data.prices) return;

        setLivePrices((prev) => {
          const next = { ...prev };
          let changed = false;
          for (const [sym, info] of Object.entries(data.prices)) {
            const old = prev[sym];
            const newPrice = Number(info.price);
            if (isNaN(newPrice)) continue;

            let tickDir = null;
            if (old && old.price) {
              if (newPrice > old.price) tickDir = 'up';
              else if (newPrice < old.price) tickDir = 'down';
              else tickDir = old.tickDir;
            }

            next[sym] = {
              price: newPrice,
              change: info.change != null ? info.change : (old?.change || 0),
              high: info.high || old?.high || newPrice,
              low: info.low || old?.low || newPrice,
              tickDir,
              ts: info.ts || Date.now(),
            };
            changed = true;
          }
          return changed ? next : prev;
        });

        if (isMounted) {
          const nowMs = Date.now();
          setLastUpdateTs(nowMs);
          setSecondsAgo(0);
        }
      } catch {}
    }

    const interval = setInterval(pollLivePrices, 1200);
    pollLivePrices();

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  // 3. Direct WebSocket connection to Binance Futures
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

                const openPrice = Number(item.o);
                const changePct = openPrice > 0
                  ? Number((((newPrice - openPrice) / openPrice) * 100).toFixed(2))
                  : (old ? old.change : 0);

                next[sym] = {
                  price: newPrice,
                  change: changePct,
                  high: Number(item.h) || (old ? old.high : newPrice),
                  low: Number(item.l) || (old ? old.low : newPrice),
                  tickDir,
                  ts: Date.now(),
                };
                changed = true;
              }
              return changed ? next : prev;
            });

            setLastUpdateTs(Date.now());
            setSecondsAgo(0);
          } catch {}
        };

        ws.onerror = () => {
          if (isMounted) setWsConnected(false);
        };

        ws.onclose = () => {
          if (isMounted) {
            setWsConnected(false);
            reconnectTimer = setTimeout(connect, 6000);
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
      return {
        price: item.price,
        tickDir: item.tickDir,
        change: item.change,
        high: item.high,
        low: item.low,
        ts: item.ts,
      };
    }
    return {
      price: fallbackPrice || 0,
      tickDir: null,
      change: 0,
      high: fallbackPrice,
      low: fallbackPrice,
      ts: Date.now(),
    };
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
    currentTime,
    lastUpdateTs,
    secondsAgo,
    // Light & Dark Theme
    theme,
    toggleTheme,
    // Authentication
    authSession,
    isAuthChecking,
    login,
    logout,
    // Session & Win Rate controller
    isSessionRunning,
    sessionStartTime,
    sessionStats,
    resetWinRate,
    toggleSessionRunning,
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

/**
 * Real-time Digital Clock ticking every 1 second
 */
export function LiveClock() {
  const { currentTime, tz } = usePrefs();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) return <span className="clock-badge">--:--:-- {tz}</span>;

  return (
    <div className="clock-badge" title="Live System Clock (1s updates)">
      <span className="clock-icon">🕒</span>
      <span className="clock-time font-num">
        {fmtTime(currentTime.toISOString(), tz, true)}
      </span>
    </div>
  );
}

/**
 * Real-time Last Updated & Streaming Status Badge
 */
export function LastUpdatedBadge() {
  const { lastUpdateTs, secondsAgo, tz, wsConnected } = usePrefs();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) return null;

  const isLive = secondsAgo <= 3;

  return (
    <div className={`live-update-badge ${isLive ? 'is-live' : 'is-stale'}`} title={`Price data refreshed ${secondsAgo}s ago`}>
      <span className={`pulse-dot ${isLive ? 'pulse-green' : 'pulse-warn'}`} />
      <span className="live-status-text">
        {isLive ? (wsConnected ? 'LIVE WS' : 'LIVE 1s') : `${secondsAgo}s ago`}
      </span>
      <span className="live-time-sub font-num">
        {fmtTime(new Date(lastUpdateTs).toISOString(), tz)}
      </span>
    </div>
  );
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
  const {
    cur,
    tz,
    setCur,
    setTz,
    rates,
    viewMode,
    setViewMode,
    soundEnabled,
    setSoundEnabled,
    theme,
    toggleTheme,
    authSession,
    logout,
  } = usePrefs();

  return (
    <div className="pref-bar">
      <div className="pref-group">
        <Seg label="Currency" options={['USD', 'INR']} value={cur} onChange={setCur} disabled={{ INR: !rates?.inr }} />
        <Seg label="Time zone" options={['IST', 'UTC']} value={tz} onChange={setTz} />
        <Seg label="View Mode" options={['Table', 'Cards']} value={viewMode === 'table' ? 'Table' : 'Cards'} onChange={(m) => setViewMode(m.toLowerCase())} />
      </div>
      <div className="pref-group">
        <button
          className="tf icon-btn theme-btn"
          onClick={toggleTheme}
          title={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} Mode`}
          aria-label="Toggle Theme"
        >
          {theme === 'dark' ? '☀️ Light Mode' : '🌙 Dark Mode'}
        </button>
        <button
          className={`tf icon-btn ${soundEnabled ? 'active' : ''}`}
          onClick={() => setSoundEnabled(!soundEnabled)}
          title={soundEnabled ? 'Mute audio alerts' : 'Enable audio alerts'}
          aria-label="Toggle sound alerts"
        >
          {soundEnabled ? '🔊 Audio ON' : '🔈 Audio OFF'}
        </button>
        {authSession && (
          <div className="user-session-chip">
            <span className="user-status-dot" />
            <span className="user-name">{authSession.name || 'Trader'}</span>
            <button className="tf logout-btn" onClick={logout} title="Sign out of Terminal">
              🚪 Sign Out
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export function RateNote() {
  const { cur, rates } = usePrefs();
  let text;
  if (cur === 'INR') {
    text = 'Prices converted from USDT perpetual contracts at 1 USDT = \u20B9' + Number(rates?.inr || 86.85).toFixed(2) + ' (Binance USD-M feed). CoinGecko source disabled.';
  } else {
    text = '100% pure Binance USD-M Futures market data feed. CoinGecko source disabled.';
  }
  return <p className="sub pad">{text}</p>;
}
