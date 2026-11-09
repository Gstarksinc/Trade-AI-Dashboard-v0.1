'use client';
import { useEffect, useMemo, useState, useRef } from 'react';
import { Money, usePrefs } from '../prefs';
import { fmtCompact, fmtTime } from '../../lib/format';
import { EquityChart } from '../components';

/**
 * Calculates Exponential Moving Average
 */
function calcEMA(candles, period) {
  if (!candles || candles.length < period) return [];
  const k = 2 / (period + 1);
  const emas = [];
  let prevEma = candles.slice(0, period).reduce((acc, c) => acc + c.close, 0) / period;
  emas.push({ time: candles[period - 1].time, value: prevEma, idx: period - 1 });

  for (let i = period; i < candles.length; i++) {
    const curClose = candles[i].close;
    const curEma = (curClose * k) + (prevEma * (1 - k));
    emas.push({ time: candles[i].time, value: curEma, idx: i });
    prevEma = curEma;
  }
  return emas;
}

/**
 * Responsive Candlestick Chart View with Overlays, Indicators, and Volume
 */
export function CandlestickChartView({
  initialSymbol = 'BTCUSDT',
  signals = [],
  equity = [],
}) {
  const { getPrice } = usePrefs();
  const [symbol, setSymbol] = useState(initialSymbol);
  const [interval, setInterval] = useState('1h');
  const [chartMode, setChartMode] = useState('candles'); // 'candles' | 'equity'
  const [candles, setCandles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Indicator controls
  const [showEma20, setShowEma20] = useState(true);
  const [showEma50, setShowEma50] = useState(true);
  const [showOverlays, setShowOverlays] = useState(true);
  const [hoverIndex, setHoverIndex] = useState(null);

  const symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'DOGEUSDT', 'LINKUSDT', 'TRXUSDT'];
  const intervals = [
    { label: '15m', val: '15m' },
    { label: '1h', val: '1h' },
    { label: '4h', val: '4h' },
    { label: '1D', val: '1d' },
  ];

  // Fetch real Binance Futures candlesticks
  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    setError(null);

    fetch(`/api/candles?symbol=${symbol}&interval=${interval}&limit=50`)
      .then((res) => res.json())
      .then((data) => {
        if (!isMounted) return;
        if (data.success && Array.isArray(data.candles) && data.candles.length > 0) {
          setCandles(data.candles);
        } else {
          setError(data.error || 'Failed to load candlestick data from Binance Futures');
        }
      })
      .catch((err) => {
        if (isMounted) setError(err.message || 'Network error fetching candles');
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [symbol, interval]);

  // Live market price
  const live = getPrice(symbol);
  const livePrice = live?.price || (candles.length > 0 ? candles[candles.length - 1].close : 0);

  // Active signal for overlays
  const activeSignal = signals.find((s) => s.symbol === symbol && s.is_confirmed);

  // Chart dimensions & scaling
  const width = 880;
  const height = 400;
  const padTop = 25;
  const padBottom = 75;
  const padLeft = 15;
  const padRight = 75;
  const priceAreaHeight = height - padTop - padBottom;
  const volAreaHeight = 55;

  const { minPrice, maxPrice, maxVol } = useMemo(() => {
    if (candles.length === 0) return { minPrice: 1, maxPrice: 10, maxVol: 1 };
    let min = Infinity;
    let max = -Infinity;
    let maxV = 0;
    candles.forEach((c) => {
      if (c.low < min) min = c.low;
      if (c.high > max) max = c.high;
      if (c.volume > maxV) maxV = c.volume;
    });

    // Also include overlays in price range if enabled
    if (showOverlays && activeSignal) {
      if (activeSignal.entry) {
        min = Math.min(min, activeSignal.entry);
        max = Math.max(max, activeSignal.entry);
      }
      if (activeSignal.stop_loss) {
        min = Math.min(min, activeSignal.stop_loss);
        max = Math.max(max, activeSignal.stop_loss);
      }
      if (activeSignal.take_profit) {
        min = Math.min(min, activeSignal.take_profit);
        max = Math.max(max, activeSignal.take_profit);
      }
    }

    if (livePrice > 0) {
      min = Math.min(min, livePrice);
      max = Math.max(max, livePrice);
    }

    // Add 2% padding to price bounds
    const pRange = max - min || 1;
    min -= pRange * 0.02;
    max += pRange * 0.02;

    return { minPrice: min, maxPrice: max, maxVol: maxV || 1 };
  }, [candles, showOverlays, activeSignal, livePrice]);

  const yPrice = (p) => {
    if (maxPrice <= minPrice) return priceAreaHeight / 2;
    return padTop + priceAreaHeight - ((p - minPrice) / (maxPrice - minPrice)) * priceAreaHeight;
  };

  const xCandle = (i, count) => {
    const availWidth = width - padLeft - padRight;
    return padLeft + (i / Math.max(1, count - 1)) * availWidth;
  };

  // Compute EMAs
  const ema20 = useMemo(() => (showEma20 ? calcEMA(candles, 20) : []), [candles, showEma20]);
  const ema50 = useMemo(() => (showEma50 ? calcEMA(candles, 50) : []), [candles, showEma50]);

  const candleCount = candles.length;
  const candleW = Math.max(3, Math.min(14, ((width - padLeft - padRight) / Math.max(1, candleCount)) * 0.65));

  // Current hovered or latest candle for stats
  const activeCandle = hoverIndex != null && candles[hoverIndex]
    ? candles[hoverIndex]
    : (candles.length > 0 ? candles[candles.length - 1] : null);

  return (
    <div className="card chart-view-card">
      {/* Top Header & Chart Mode Switch */}
      <div className="chart-header-strip">
        <div className="chart-title-group">
          <div className="chart-mode-tabs">
            <button
              className={`panel-tab ${chartMode === 'candles' ? 'active' : ''}`}
              onClick={() => setChartMode('candles')}
            >
              📊 Candlesticks &amp; Overlays
            </button>
            <button
              className={`panel-tab ${chartMode === 'equity' ? 'active' : ''}`}
              onClick={() => setChartMode('equity')}
            >
              📈 Paper Equity Curve (30D)
            </button>
          </div>

          {chartMode === 'candles' && (
            <div className="chart-symbol-picker">
              <select
                className="filter-select symbol-select"
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
              >
                {symbols.map((s) => (
                  <option key={s} value={s}>
                    {s.replace('USDT', '')} / USDT Perpetual
                  </option>
                ))}
              </select>

              <div className="timeframe-buttons">
                {intervals.map((it) => (
                  <button
                    key={it.val}
                    className={`filter-pill ${interval === it.val ? 'active' : ''}`}
                    onClick={() => setInterval(it.val)}
                  >
                    {it.label}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {chartMode === 'candles' && (
          <div className="chart-indicators-bar">
            <label className="indicator-toggle">
              <input
                type="checkbox"
                checked={showEma20}
                onChange={(e) => setShowEma20(e.target.checked)}
              />
              <span className="ind-color-box ema20" /> 20 EMA
            </label>
            <label className="indicator-toggle">
              <input
                type="checkbox"
                checked={showEma50}
                onChange={(e) => setShowEma50(e.target.checked)}
              />
              <span className="ind-color-box ema50" /> 50 EMA
            </label>
            <label className="indicator-toggle">
              <input
                type="checkbox"
                checked={showOverlays}
                onChange={(e) => setShowOverlays(e.target.checked)}
              />
              <span className="ind-color-box overlays" /> Signal Levels
            </label>
          </div>
        )}
      </div>

      {/* Candlestick Mode */}
      {chartMode === 'candles' ? (
        <div className="candlestick-wrapper">
          {/* Candle Stats Bar (Open, High, Low, Close, Volume) */}
          <div className="candle-stats-bar">
            <div className="stats-coin-tag">
              <span className="font-bold">{symbol.replace('USDT', '')}</span>
              <span className="tf-badge">{interval}</span>
              <span className="sub">Binance Futures</span>
            </div>

            {activeCandle && (
              <div className="stats-ohlcv">
                <span>O: <strong className="font-num"><Money value={activeCandle.open} /></strong></span>
                <span>H: <strong className="font-num"><Money value={activeCandle.high} /></strong></span>
                <span>L: <strong className="font-num"><Money value={activeCandle.low} /></strong></span>
                <span>
                  C: <strong className={`font-num ${activeCandle.close >= activeCandle.open ? 'text-tp' : 'text-sl'}`}>
                    <Money value={activeCandle.close} />
                  </strong>
                </span>
                <span>Vol: <strong className="font-num">{fmtCompact(activeCandle.volume)}</strong></span>
                {activeCandle.time && (
                  <span className="stat-time"><Time iso={new Date(activeCandle.time).toISOString()} /></span>
                )}
              </div>
            )}
          </div>

          {/* SVG Candlestick Rendering */}
          <div className="svg-chart-container">
            {loading ? (
              <div className="chart-loading-box">
                <div className="spinner" />
                <p className="sub pad">Streaming real {symbol} candles from Binance Futures...</p>
              </div>
            ) : error ? (
              <div className="chart-error-box">
                <p className="sub text-sl">✕ {error}</p>
                <button className="primary-btn" onClick={() => setInterval((prev) => prev)}>Retry</button>
              </div>
            ) : (
              <svg
                viewBox={`0 0 ${width} ${height}`}
                className="svg-candlestick-chart"
                onMouseLeave={() => setHoverIndex(null)}
              >
                {/* Horizontal Gridlines */}
                {[0, 0.25, 0.5, 0.75, 1].map((pct) => {
                  const y = padTop + priceAreaHeight * pct;
                  const priceVal = maxPrice - pct * (maxPrice - minPrice);
                  return (
                    <g key={pct}>
                      <line
                        x1={padLeft}
                        y1={y}
                        x2={width - padRight}
                        y2={y}
                        stroke="rgba(255, 255, 255, 0.05)"
                        strokeDasharray="3 3"
                      />
                      <text
                        x={width - padRight + 6}
                        y={y + 4}
                        fill="var(--text-dim)"
                        fontSize="10"
                        fontFamily="ui-monospace, monospace"
                      >
                        {priceVal.toFixed(priceVal < 1 ? 4 : priceVal < 20 ? 3 : 1)}
                      </text>
                    </g>
                  );
                })}

                {/* Volume Baseline Grid */}
                <line
                  x1={padLeft}
                  y1={height - padBottom}
                  x2={width - padRight}
                  y2={height - padBottom}
                  stroke="rgba(255, 255, 255, 0.08)"
                />

                {/* Volume Histogram Bars */}
                {candles.map((c, i) => {
                  const x = xCandle(i, candleCount);
                  const isUp = c.close >= c.open;
                  const vHeight = Math.min(volAreaHeight, (c.volume / maxVol) * volAreaHeight);
                  const y = height - padBottom - vHeight;
                  return (
                    <rect
                      key={`vol-${i}`}
                      x={x - candleW / 2}
                      y={y}
                      width={candleW}
                      height={Math.max(1, vHeight)}
                      fill={isUp ? 'rgba(16, 185, 129, 0.25)' : 'rgba(244, 63, 94, 0.25)'}
                    />
                  );
                })}

                {/* Candlesticks (Wicks and Bodies) */}
                {candles.map((c, i) => {
                  const x = xCandle(i, candleCount);
                  const isUp = c.close >= c.open;
                  const yHigh = yPrice(c.high);
                  const yLow = yPrice(c.low);
                  const yTop = yPrice(Math.max(c.open, c.close));
                  const yBottom = yPrice(Math.min(c.open, c.close));
                  const bHeight = Math.max(2, yBottom - yTop);
                  const color = isUp ? '#10B981' : '#F43F5E';

                  return (
                    <g
                      key={`candle-${i}`}
                      className="candle-node"
                      onMouseEnter={() => setHoverIndex(i)}
                    >
                      {/* Upper & Lower Wick */}
                      <line
                        x1={x}
                        y1={yHigh}
                        x2={x}
                        y2={yLow}
                        stroke={color}
                        strokeWidth="1.2"
                      />
                      {/* Body Rect */}
                      <rect
                        x={x - candleW / 2}
                        y={yTop}
                        width={candleW}
                        height={bHeight}
                        fill={color}
                        rx="1"
                      />
                    </g>
                  );
                })}

                {/* 20 EMA Path */}
                {showEma20 && ema20.length > 1 && (
                  <path
                    d={ema20
                      .map((pt, idx) => `${idx === 0 ? 'M' : 'L'} ${xCandle(pt.idx, candleCount)} ${yPrice(pt.value)}`)
                      .join(' ')}
                    fill="none"
                    stroke="#F59E0B"
                    strokeWidth="1.5"
                  />
                )}

                {/* 50 EMA Path */}
                {showEma50 && ema50.length > 1 && (
                  <path
                    d={ema50
                      .map((pt, idx) => `${idx === 0 ? 'M' : 'L'} ${xCandle(pt.idx, candleCount)} ${yPrice(pt.value)}`)
                      .join(' ')}
                    fill="none"
                    stroke="#8B5CF6"
                    strokeWidth="1.5"
                  />
                )}

                {/* Predictive Signal Overlays (Entry, SL, TP) */}
                {showOverlays && activeSignal && (
                  <g className="signal-overlays">
                    {/* Take Profit Target */}
                    {activeSignal.take_profit && (
                      <g>
                        <line
                          x1={padLeft}
                          y1={yPrice(activeSignal.take_profit)}
                          x2={width - padRight}
                          y2={yPrice(activeSignal.take_profit)}
                          stroke="#10B981"
                          strokeDasharray="4 3"
                          strokeWidth="1.4"
                        />
                        <rect
                          x={width - padRight + 2}
                          y={yPrice(activeSignal.take_profit) - 9}
                          width="68"
                          height="18"
                          fill="rgba(16, 185, 129, 0.2)"
                          stroke="#10B981"
                          rx="3"
                        />
                        <text
                          x={width - padRight + 6}
                          y={yPrice(activeSignal.take_profit) + 3}
                          fill="#10B981"
                          fontSize="9"
                          fontWeight="bold"
                        >
                          TP {activeSignal.take_profit}
                        </text>
                      </g>
                    )}

                    {/* Expected Entry */}
                    {activeSignal.entry && (
                      <g>
                        <line
                          x1={padLeft}
                          y1={yPrice(activeSignal.entry)}
                          x2={width - padRight}
                          y2={yPrice(activeSignal.entry)}
                          stroke="#38BDF8"
                          strokeDasharray="4 3"
                          strokeWidth="1.4"
                        />
                        <rect
                          x={width - padRight + 2}
                          y={yPrice(activeSignal.entry) - 9}
                          width="68"
                          height="18"
                          fill="rgba(56, 189, 248, 0.2)"
                          stroke="#38BDF8"
                          rx="3"
                        />
                        <text
                          x={width - padRight + 6}
                          y={yPrice(activeSignal.entry) + 3}
                          fill="#38BDF8"
                          fontSize="9"
                          fontWeight="bold"
                        >
                          Entry {activeSignal.entry}
                        </text>
                      </g>
                    )}

                    {/* Stop Loss */}
                    {activeSignal.stop_loss && (
                      <g>
                        <line
                          x1={padLeft}
                          y1={yPrice(activeSignal.stop_loss)}
                          x2={width - padRight}
                          y2={yPrice(activeSignal.stop_loss)}
                          stroke="#F43F5E"
                          strokeDasharray="4 3"
                          strokeWidth="1.4"
                        />
                        <rect
                          x={width - padRight + 2}
                          y={yPrice(activeSignal.stop_loss) - 9}
                          width="68"
                          height="18"
                          fill="rgba(244, 63, 94, 0.2)"
                          stroke="#F43F5E"
                          rx="3"
                        />
                        <text
                          x={width - padRight + 6}
                          y={yPrice(activeSignal.stop_loss) + 3}
                          fill="#F43F5E"
                          fontSize="9"
                          fontWeight="bold"
                        >
                          SL {activeSignal.stop_loss}
                        </text>
                      </g>
                    )}
                  </g>
                )}

                {/* Live Current Market Price (CMP) Line with Pulse */}
                {livePrice > 0 && (
                  <g className="cmp-overlay-line">
                    <line
                      x1={padLeft}
                      y1={yPrice(livePrice)}
                      x2={width - padRight}
                      y2={yPrice(livePrice)}
                      stroke="#FACC15"
                      strokeWidth="1.4"
                    />
                    <circle
                      cx={width - padRight - 6}
                      cy={yPrice(livePrice)}
                      r="4"
                      fill="#FACC15"
                    />
                    <rect
                      x={width - padRight + 2}
                      y={yPrice(livePrice) - 9}
                      width="68"
                      height="18"
                      fill="#FACC15"
                      rx="3"
                    />
                    <text
                      x={width - padRight + 6}
                      y={yPrice(livePrice) + 4}
                      fill="#06090E"
                      fontSize="9"
                      fontWeight="bold"
                    >
                      {livePrice.toFixed(livePrice < 1 ? 4 : livePrice < 20 ? 3 : 1)}
                    </text>
                  </g>
                )}

                {/* Hover Crosshair */}
                {hoverIndex != null && (
                  <line
                    x1={xCandle(hoverIndex, candleCount)}
                    y1={padTop}
                    x2={xCandle(hoverIndex, candleCount)}
                    y2={height - padBottom}
                    stroke="rgba(255, 255, 255, 0.4)"
                    strokeDasharray="2 2"
                  />
                )}
              </svg>
            )}
          </div>
        </div>
      ) : (
        /* Equity Chart Mode */
        <div className="chart-equity-mode pad">
          <EquityChart points={equity} />
        </div>
      )}
    </div>
  );
}
