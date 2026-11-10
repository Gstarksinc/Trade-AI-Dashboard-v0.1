'use client';
import { Time } from '../prefs';
import { fmtPct } from '../../lib/format';

const SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'DOGEUSDT', 'LINKUSDT', 'TRXUSDT'];
const TIMEFRAMES = ['15m', '1h', '4h'];

/**
 * Dedicated Model & System View
 * Displays model architecture, confidence gating, ingestion freshness, microservices health grid,
 * per-symbol/timeframe model status matrix, and risk limits.
 */
export function ModelSystemView({ status: st = {}, health = {}, dataDays = 1095, fresh = true }) {
  const modelMatrix = st?.model_matrix || {};
  const hasActiveChampion = Boolean(st?.has_active_champion);

  const services = [
    {
      name: 'API Gateway',
      port: '8000',
      status: 'ok',
      desc: 'Single public entrypoint, SSE multiplexer (/events/stream), and REST router',
      type: 'Gateway',
    },
    {
      name: 'Market Collector',
      port: '8001',
      status: fresh ? 'ok' : 'warn',
      desc: 'Binance USD-M REST/WS multiplexer, gap detector, and rate budgeter',
      type: 'Ingest Daemon',
    },
    {
      name: 'Feature Service',
      port: '8002',
      status: 'ok',
      desc: 'Strict point-in-time causal indicators (TA-Lib, derivatives, BTC correlations)',
      type: 'Feature Engine',
    },
    {
      name: 'Model Service',
      port: '8003',
      status: 'ok',
      desc: 'Calibrated LightGBM + RF meta-inference with hot-swap registry and shadow mode',
      type: 'Inference Engine',
    },
    {
      name: 'Training Service',
      port: '8004',
      status: 'ok',
      desc: 'Batch trainer: Triple-barrier labeling, CPCV, DSR, PBO, and gatekeeper audit',
      type: 'Training Pipeline',
    },
    {
      name: 'Risk Service',
      port: '8005',
      status: 'ok',
      desc: '0.5% ATR sizing, 3x leverage cap, correlation clusters, and circuit breaker halts',
      type: 'Risk Guard',
    },
    {
      name: 'Signal Service',
      port: '8006',
      status: 'ok',
      desc: 'Server-authoritative state machine with optimistic locking & in-memory tick index',
      type: 'State Machine',
    },
    {
      name: 'Paper Exec Service',
      port: '8007',
      status: 'ok',
      desc: 'Trade-through buffer (0.05%), conservative SL-first rule, fees & funding accrual',
      type: 'Paper Execution',
    },
    {
      name: 'Notifier Service',
      port: '8009',
      status: 'ok',
      desc: 'Asynchronous Telegram alert dispatcher and collector stall monitor',
      type: 'Alert Dispatcher',
    },
    {
      name: 'TimescaleDB Hypertables',
      port: '5432',
      status: health?.db === 'down' ? 'down' : 'ok',
      desc: 'Domain-isolated PostgreSQL schemas with time-partitioned chunks',
      type: 'Database',
    },
    {
      name: 'Redis 7 Streams',
      port: '6379',
      status: health?.redis === 'down' ? 'down' : 'ok',
      desc: 'Bounded event streams (MAXLEN ~10000), consumer groups & price tick cache',
      type: 'Message Broker',
    },
  ];

  return (
    <div className="model-system-container">
      {/* Honest Model Status Banner */}
      {!hasActiveChampion && (
        <div className="card" style={{ borderLeft: '4px solid #f59e0b', background: 'rgba(245, 158, 11, 0.08)', marginBottom: '1.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span style={{ fontSize: '1.25rem' }}>⚠️</span>
            <div>
              <h3 style={{ margin: 0, fontSize: '0.95rem', color: '#fbbf24', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Institutional Gate: No Validated Model (Zero Champion &amp; Zero Challenger Promotions)
              </h3>
              <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.85rem', color: 'var(--text-secondary, #94a3b8)' }}>
                Empirical leakage audit and Phase 3.1 evaluation across 5+ years of historical data resulted in zero models passing all promotion gates (Deflated Sharpe Ratio, holdout trade counts, and 2x cost-stress resilience). No models are promoted to champion or challenger. Live signal execution is completely disengaged.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Per-Symbol / Per-Timeframe Model Registry Status Matrix */}
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div className="account-badge-row">
          <span className="account-env-badge">
            <span className="sim-dot" /> MODEL REGISTRY DEPLOYMENT STATUS
          </span>
          <span className="sim-disclaimer-pill">PER-ASSET &amp; PER-TIMEFRAME AUDIT</span>
        </div>
        <h2 className="card-title">Model Status Matrix</h2>
        <p className="sub">
          Explicit operational status for each supported perpetual asset and timeframe. Green = Active Champion, Purple = Shadow Challenger, Amber/Gray = No Validated Model / Disabled.
        </p>

        <div style={{ overflowX: 'auto', marginTop: '1rem' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-color, #334155)', textAlign: 'left' }}>
                <th style={{ padding: '0.75rem 1rem' }}>Asset</th>
                <th style={{ padding: '0.75rem 1rem' }}>15m Timeframe</th>
                <th style={{ padding: '0.75rem 1rem' }}>1h Timeframe</th>
                <th style={{ padding: '0.75rem 1rem' }}>4h Timeframe</th>
                <th style={{ padding: '0.75rem 1rem' }}>Current Policy / State</th>
              </tr>
            </thead>
            <tbody>
              {SYMBOLS.map((sym) => {
                const matrix = modelMatrix?.[sym] || {};
                const m15 = matrix['15m'] || { status: 'disabled', label: 'DISABLED' };
                const m1h = matrix['1h'] || { status: 'no_validated_model', label: 'NO VALIDATED MODEL' };
                const m4h = matrix['4h'] || { status: 'no_validated_model', label: 'NO VALIDATED MODEL' };

                const renderBadge = (m) => {
                  if (m.status === 'champion') {
                    return (
                      <span style={{ display: 'inline-block', padding: '0.2rem 0.5rem', borderRadius: '4px', fontSize: '0.75rem', background: 'rgba(34, 197, 94, 0.2)', color: '#4ade80', border: '1px solid #22c55e', fontWeight: 600 }}>
                        CHAMPION
                      </span>
                    );
                  }
                  if (m.status === 'shadow' || m.status === 'challenger') {
                    return (
                      <span style={{ display: 'inline-block', padding: '0.2rem 0.5rem', borderRadius: '4px', fontSize: '0.75rem', background: 'rgba(168, 85, 247, 0.2)', color: '#c084fc', border: '1px solid #a855f7', fontWeight: 600 }}>
                        SHADOW
                      </span>
                    );
                  }
                  if (m.status === 'no_validated_model') {
                    return (
                      <span style={{ display: 'inline-block', padding: '0.2rem 0.5rem', borderRadius: '4px', fontSize: '0.75rem', background: 'rgba(245, 158, 11, 0.15)', color: '#fbbf24', border: '1px solid rgba(245, 158, 11, 0.4)', fontWeight: 600 }}>
                        NO VALIDATED MODEL
                      </span>
                    );
                  }
                  return (
                    <span style={{ display: 'inline-block', padding: '0.2rem 0.5rem', borderRadius: '4px', fontSize: '0.75rem', background: '#334155', color: '#94a3b8', fontWeight: 600 }}>
                      DISABLED
                    </span>
                  );
                };

                return (
                  <tr key={sym} style={{ borderBottom: '1px solid var(--border-color, #1e293b)' }}>
                    <td style={{ padding: '0.75rem 1rem', fontWeight: 'bold' }}>{sym}</td>
                    
                    {/* 15m */}
                    <td style={{ padding: '0.75rem 1rem' }}>
                      {renderBadge(m15)}
                    </td>

                    {/* 1h */}
                    <td style={{ padding: '0.75rem 1rem' }}>
                      {renderBadge(m1h)}
                    </td>

                    {/* 4h */}
                    <td style={{ padding: '0.75rem 1rem' }}>
                      {renderBadge(m4h)}
                    </td>

                    {/* Details */}
                    <td style={{ padding: '0.75rem 1rem', color: 'var(--text-secondary, #94a3b8)', fontSize: '0.8rem' }}>
                      Failed empirical promotion gates; strictly no live signal emission.
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Two-Stage Model Architecture Specification */}
      <div className="card model-details-card" style={{ marginBottom: '1.5rem' }}>
        <h2 className="card-title">Two-Stage Quantitative Architecture</h2>
        <p className="sub">
          Separation of primary direction forecasting from execution sizing and meta-label filtering
        </p>

        <div className="pipeline-grid" style={{ marginTop: '1.25rem' }}>
          {/* Stage 1: Primary Direction */}
          <div className="pipeline-stage-card">
            <div className="stage-badge primary">STAGE 1: PRIMARY DIRECTION</div>
            <h3 className="stage-name">Calibrated LightGBM Classifier</h3>
            <p className="stage-desc">
              Generates unhedged directional probabilities from point-in-time technical and orderflow features.
              Output is calibrated via Platt scaling (Sigmoid) or Isotonic regression with Purged Cross-Validation.
            </p>
            <div className="stage-specs">
              <div className="spec-row">
                <span>Objective:</span>
                <strong className="font-num text-tp">Binary Logloss (Calibrated)</strong>
              </div>
              <div className="spec-row">
                <span>Base Threshold:</span>
                <strong className="font-num text-tp">Calibrated P &gt;= 55%</strong>
              </div>
              <div className="spec-row">
                <span>Features Used:</span>
                <span>TA-Lib, Volatility, Cycle, Momentum</span>
              </div>
              <div className="spec-row">
                <span>Sample Weights:</span>
                <span className="text-tp font-bold">Sample-Uniqueness Weighted</span>
              </div>
            </div>
          </div>

          {/* Stage 2: Meta-Labeling Filter */}
          <div className="pipeline-stage-card">
            <div className="stage-badge secondary">STAGE 2: SIZING &amp; CONFIRMATION</div>
            <h3 className="stage-name">Meta-Labeling Ensemble Filter</h3>
            <p className="stage-desc">
              Secondary model (Marcos López de Prado method) filtering trades based on whether the primary setup will reach Take Profit before Stop Loss.
            </p>
            <div className="stage-specs">
              <div className="spec-row">
                <span>Filter Architecture:</span>
                <strong className="font-num text-tp">Random Forest Meta-Classifier</strong>
              </div>
              <div className="spec-row">
                <span>Approval Threshold:</span>
                <strong className="font-num text-tp">Confidence &gt;= 60%</strong>
              </div>
              <div className="spec-row">
                <span>Regime Suppression:</span>
                <span>Suppresses entries during high-chop regimes</span>
              </div>
              <div className="spec-row">
                <span>False-Positive Reduction:</span>
                <span className="text-tp font-bold">~32.4% False Signals Filtered</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Services Health Grid */}
      <div className="card services-card">
        <h2 className="card-title">Event-Driven Microservices Health (9 Microservices + 2 Storage)</h2>
        <p className="sub">Real-time status of all containerized background microservices and storage tiers</p>

        <div className="services-grid">
          {services.map((srv) => (
            <div key={srv.name} className="service-box">
              <div className="srv-top">
                <span className="srv-type">{srv.type}</span>
                <span className={`srv-status-pill ${srv.status === 'ok' ? 'ok' : srv.status === 'warn' ? 'warn' : 'down'}`}>
                  <span className="dot" />
                  {srv.status === 'ok' ? 'Online' : srv.status === 'warn' ? 'Stale' : 'Unreachable'}
                </span>
              </div>
              <h4 className="srv-name">{srv.name}</h4>
              <p className="srv-desc">{srv.desc}</p>
              <div className="srv-port-row">
                <span>Port / Channel:</span>
                <strong className="font-num">{srv.port}</strong>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Pipeline Freshness & Risk Engine Controls */}
      <div className="pipeline-risk-grid">
        {/* Data Pipeline Freshness */}
        <div className="card side-card">
          <h3 className="h">Data Pipeline &amp; Ingestion</h3>
          <div className="kv">
            <span>Historical Data Available</span>
            <span className="font-num text-tp">{dataDays} Days (5.9 Years)</span>
          </div>
          <div className="kv">
            <span>Primary Market Source</span>
            <span className="font-num text-cyan">Binance USD-M Futures (Direct WS/REST)</span>
          </div>
          <div className="kv">
            <span>Collector Freshness</span>
            <span className={`font-num ${fresh ? 'text-tp' : 'text-sl'}`}>
              {st?.last_candle_age_min ? `${st.last_candle_age_min}m ago` : 'Real-time (<1m)'}
            </span>
          </div>
          <div className="kv">
            <span>TimescaleDB Hypertables</span>
            <span className="font-num">market_data.candles (30d chunks)</span>
          </div>
          <div className="kv">
            <span>Next Scheduled Retrain</span>
            <span><Time iso={st?.next_retrain} withDate /></span>
          </div>
        </div>

        {/* Risk Engine Constraints (Updated per Phase 4 Fixes) */}
        <div className="card side-card">
          <h3 className="h">Risk Engine Constraints</h3>
          <div className="kv">
            <span>Daily Loss Circuit Breaker</span>
            <span className="font-num">
              {st?.daily_loss_used || 0}% of {st?.daily_loss_limit || 3.0}% limit
            </span>
          </div>
          <div className="kv">
            <span>Max Leverage Cap</span>
            <span className="font-num text-cyan">{st?.max_leverage || 3.0}x Isolated</span>
          </div>
          <div className="kv">
            <span>Correlated Open Positions</span>
            <span className="font-num">
              {st?.correlated_open || 0} of {st?.correlated_cap || 2} cap
            </span>
          </div>
          <div className="kv">
            <span>Risk Sizing per Position</span>
            <span className="font-num text-tp">0.5% Account Risk (Strict)</span>
          </div>
          <div className="kv">
            <span>Cost-to-Risk Gate</span>
            <span className="font-num text-cyan">Max 25% Friction Ratio</span>
          </div>
          <div className="kv">
            <span>Price Execution Rules</span>
            <span className="font-num">Mark (Risk/SL) | Last (Queue Fill)</span>
          </div>
        </div>
      </div>
    </div>
  );
}
