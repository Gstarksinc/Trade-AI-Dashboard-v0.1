'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { fmtPrice } from '../lib/format';

const FILTERS = ['All', '15m', '1h', '4h'];
const STATUS = { open: 'Open', target_hit: 'Target hit', stopped: 'Stopped out' };

export function AutoRefresh({ seconds = 30 }) {
  const router = useRouter();
  useEffect(() => {
    const id = setInterval(() => router.refresh(), seconds * 1000);
    return () => clearInterval(id);
  }, [router, seconds]);
  return null;
}

export function SignalsPanel({ signals }) {
  const [tf, setTf] = useState('All');
  const rows = tf === 'All' ? signals : signals.filter((s) => s.timeframe === tf);
  return (
    <div className="card main">
      <div className="card-head">
        <h2 className="h">Live signals</h2>
        <div className="filters">
          {FILTERS.map((f) => (
            <button key={f} className="tf" aria-pressed={tf === f} onClick={() => setTf(f)}>
              {f}
            </button>
          ))}
        </div>
      </div>
      <div className="scroll">
        <table>
          <thead>
            <tr>
              <th>Symbol</th><th>TF</th><th>Direction</th><th>Confidence</th>
              <th>Entry</th><th>Stop</th><th>Target</th><th>Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((s, i) => (
              <tr key={s.symbol + s.timeframe + i}>
                <td>{s.symbol}</td>
                <td>{s.timeframe}</td>
                <td className={String(s.direction).toLowerCase()}>
                  {String(s.direction).toLowerCase() === 'long' ? 'Long' : 'Short'}
                </td>
                <td>{Math.round(s.probability * 100)}%</td>
                <td>{fmtPrice(s.entry)}</td>
                <td>{fmtPrice(s.stop_loss)}</td>
                <td>{fmtPrice(s.take_profit)}</td>
                <td>{STATUS[s.status] || s.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && <p className="sub pad">No signals for this timeframe yet.</p>}
      </div>
    </div>
  );
}

export function EquityChart({ points }) {
  if (!points || points.length < 2) return <p className="sub">Not enough data yet.</p>;
  const v = points.map((p) => p.equity);
  const min = Math.min(...v);
  const span = Math.max(...v) - min || 1;
  const pts = v.map((y, i) => (i / (v.length - 1)) * 400 + ',' + (130 - ((y - min) / span) * 100)).join(' ');
  return (
    <svg viewBox="0 0 400 170" width="100%" role="img" aria-label="Paper equity curve over the last 30 days">
      {[30, 80, 130].map((y) => <line key={y} x1="0" y1={y} x2="400" y2={y} stroke="#262D36" />)}
      <polyline points={pts} fill="none" stroke="#6DB3FF" strokeWidth="2.5" strokeLinejoin="round" />
      <text x="0" y="162" fontSize="11" fill="#9AA4B2">30 days ago</text>
      <text x="400" y="162" fontSize="11" fill="#9AA4B2" textAnchor="end">Today</text>
    </svg>
  );
}
