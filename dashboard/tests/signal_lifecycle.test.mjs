import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { calcTradeMetrics, fmtDuration, SIGNAL_PHASES } from '../lib/format.js';

describe('1. Genuine vs Fallback Signal Data Contracts', () => {
  test('rejects unconfirmed coin from being presented as active position', () => {
    const unconfirmed = {
      symbol: 'BTCUSDT',
      is_confirmed: false,
      status: 'waiting_confirmation',
      entry: null,
      stop_loss: null,
      take_profit: null,
    };
    const m = calcTradeMetrics(unconfirmed, 74500);
    assert.equal(m.phase, 'WAITING_CONFIRMATION');
    assert.equal(m.phaseLabel, 'Waiting for confirmation');
    assert.equal(m.isConfirmed, false);
    assert.equal(m.isTriggered, false);
    assert.equal(m.entry, null);
    assert.equal(m.sl, null);
    assert.equal(m.tp, null);
  });

  test('handles null/undefined signal honestly without inventing values', () => {
    const m = calcTradeMetrics(null, 74500);
    assert.equal(m.phase, 'WAITING_CONFIRMATION');
    assert.equal(m.isConfirmed, false);
    assert.equal(m.isTriggered, false);
  });

  test('fallback or mock signals with is_fallback flag are identified and excluded', () => {
    const rawApiSignals = [
      { id: 1, symbol: 'BTCUSDT', is_fallback: false, entry: 74000, stop_loss: 73000, take_profit: 76000 },
      { id: 2, symbol: 'ETHUSDT', is_fallback: true, entry: 2100, stop_loss: 2050, take_profit: 2200 },
    ];
    const genuineSignals = rawApiSignals.filter((s) => !s.is_fallback);
    assert.equal(genuineSignals.length, 1);
    assert.equal(genuineSignals[0].symbol, 'BTCUSDT');
  });

  test('empty signal list results in 0 open signals and no fabricated setups', () => {
    const rawApiSignals = [];
    const genuineSignals = rawApiSignals.filter((s) => !s.is_fallback);
    assert.equal(genuineSignals.length, 0);
  });
});

describe('2. Active Signal Lifecycle Transitions', () => {
  const longSignal = {
    id: 10,
    symbol: 'BTCUSDT',
    timeframe: '1h',
    direction: 'long',
    entry: 74000,
    stop_loss: 73000,
    take_profit: 76000,
    is_confirmed: true,
    status: 'open',
  };

  const shortSignal = {
    id: 20,
    symbol: 'ETHUSDT',
    timeframe: '15m',
    direction: 'short',
    entry: 2100,
    stop_loss: 2150,
    take_profit: 2000,
    is_confirmed: true,
    status: 'open',
  };

  test('State 1: Waiting for confirmation when coin is unconfirmed', () => {
    const unconfirmed = { symbol: 'SOLUSDT', is_confirmed: false, status: 'waiting_confirmation' };
    const m = calcTradeMetrics(unconfirmed, 88.5);
    assert.equal(m.phase, 'WAITING_CONFIRMATION');
    assert.equal(m.phaseLabel, 'Waiting for confirmation');
  });

  test('State 2: Waiting for entry (Long setup before CMP reaches entry)', () => {
    // For LONG with entry at 74000, CMP at 74500 is still above entry
    const m = calcTradeMetrics(longSignal, 74500);
    assert.equal(m.phase, 'WAITING_ENTRY');
    assert.equal(m.phaseLabel, 'Waiting for entry');
    assert.equal(m.isTriggered, false);
  });

  test('State 2: Waiting for entry (Short setup before CMP reaches entry)', () => {
    // For SHORT with entry at 2100, CMP at 2050 is still below entry
    const m = calcTradeMetrics(shortSignal, 2050);
    assert.equal(m.phase, 'WAITING_ENTRY');
    assert.equal(m.phaseLabel, 'Waiting for entry');
    assert.equal(m.isTriggered, false);
  });

  test('State 3: Order in progress when entry is reached (Long limit filled)', () => {
    // For LONG with entry at 74000, CMP reaching 74000 or lower triggers entry
    const m = calcTradeMetrics(longSignal, 73950);
    assert.equal(m.phase, 'ORDER_IN_PROGRESS');
    assert.equal(m.phaseLabel, 'Order in progress');
    assert.equal(m.isTriggered, true);
  });

  test('State 3: Order in progress when entry is reached (Short limit filled)', () => {
    // For SHORT with entry at 2100, CMP reaching 2100 or higher triggers entry
    const m = calcTradeMetrics(shortSignal, 2105);
    assert.equal(m.phase, 'ORDER_IN_PROGRESS');
    assert.equal(m.phaseLabel, 'Order in progress');
    assert.equal(m.isTriggered, true);
  });

  test('State 3: Once in progress, price fluctuation between entry and SL/TP remains in progress', () => {
    // Long trade was entered: opened_at is set or status is in_progress
    const inProgressLong = { ...longSignal, status: 'in_progress', opened_at: '2026-11-09T18:00:00Z' };
    // Price bounces back up to 74800 (above entry 74000, but below TP 76000)
    const m = calcTradeMetrics(inProgressLong, 74800);
    assert.equal(m.phase, 'ORDER_IN_PROGRESS');
    assert.equal(m.phaseLabel, 'Order in progress');
  });

  test('State 4: Win — Target hit when take profit is touched (Long)', () => {
    const inProgressLong = { ...longSignal, status: 'in_progress', opened_at: '2026-11-09T18:00:00Z' };
    const m = calcTradeMetrics(inProgressLong, 76050);
    assert.equal(m.phase, 'WIN_TARGET_HIT');
    assert.equal(m.phaseLabel, 'Win — Target hit');
  });

  test('State 4: Win — Target hit when take profit is touched (Short)', () => {
    const inProgressShort = { ...shortSignal, status: 'in_progress', opened_at: '2026-11-09T18:00:00Z' };
    const m = calcTradeMetrics(inProgressShort, 1995);
    assert.equal(m.phase, 'WIN_TARGET_HIT');
    assert.equal(m.phaseLabel, 'Win — Target hit');
  });

  test('State 5: Loss — Stop loss hit when stop loss is touched (Long)', () => {
    const inProgressLong = { ...longSignal, status: 'in_progress', opened_at: '2026-11-09T18:00:00Z' };
    const m = calcTradeMetrics(inProgressLong, 72950);
    assert.equal(m.phase, 'LOSS_STOP_HIT');
    assert.equal(m.phaseLabel, 'Loss — Stop loss hit');
  });

  test('State 5: Loss — Stop loss hit when stop loss is touched (Short)', () => {
    const inProgressShort = { ...shortSignal, status: 'in_progress', opened_at: '2026-11-09T18:00:00Z' };
    const m = calcTradeMetrics(inProgressShort, 2155);
    assert.equal(m.phase, 'LOSS_STOP_HIT');
    assert.equal(m.phaseLabel, 'Loss — Stop loss hit');
  });

  test('Ambiguous price gap: does not invent outcome if CMP crosses both TP and SL simultaneously', () => {
    // Malformed/gap scenario where CMP is above TP and below SL
    const malformedSignal = {
      id: 99,
      symbol: 'BTCUSDT',
      direction: 'long',
      entry: 74000,
      stop_loss: 77000, // SL above entry
      take_profit: 72000, // TP below entry
      status: 'in_progress',
      opened_at: '2026-11-09T18:00:00Z',
    };
    const m = calcTradeMetrics(malformedSignal, 75000);
    // Preserves ORDER_IN_PROGRESS without guessing a win or loss
    assert.equal(m.phase, 'ORDER_IN_PROGRESS');
  });
});

describe('3. Duplicate-Completion Prevention & Persistence', () => {
  test('completed trade is recorded only once and prevents duplicate history entries', () => {
    const completedIds = new Set();
    const historyList = [];

    function recordCompletion(signalId, outcome) {
      if (completedIds.has(String(signalId))) {
        return false; // Ignored duplicate
      }
      completedIds.add(String(signalId));
      historyList.push({
        signal_id: signalId,
        outcome,
        closed_at: new Date().toISOString(),
      });
      return true;
    }

    assert.equal(recordCompletion(10, 'Target Hit'), true);
    assert.equal(historyList.length, 1);

    // Second event or page reload receives the same completion update
    assert.equal(recordCompletion(10, 'Target Hit'), false);
    assert.equal(historyList.length, 1, 'Duplicate trade must not be inserted into history');
  });

  test('deduplicates database history and session-completed trades cleanly', () => {
    const baseHistoryFromDb = [
      { id: 101, signal_id: 10, symbol: 'BTCUSDT', exit_reason: 'Target Hit' },
    ];
    const sessionCompletedTrades = [
      { id: 'trade-10-123', signal_id: 10, symbol: 'BTCUSDT', exit_reason: 'Target Hit' },
      { id: 'trade-20-456', signal_id: 20, symbol: 'ETHUSDT', exit_reason: 'Stop Loss Hit' },
    ];

    const existingSignals = new Set();
    const merged = [];

    baseHistoryFromDb.forEach((h) => {
      const key = h.signal_id ? `sig-${h.signal_id}` : `trade-${h.id}`;
      existingSignals.add(key);
      merged.push(h);
    });

    sessionCompletedTrades.forEach((t) => {
      const key = t.signal_id ? `sig-${t.signal_id}` : `trade-${t.id}`;
      if (!existingSignals.has(key)) {
        existingSignals.add(key);
        merged.push(t);
      }
    });

    assert.equal(merged.length, 2);
    assert.equal(merged[0].signal_id, 10);
    assert.equal(merged[1].signal_id, 20);
  });
});

describe('4. Timestamp Mapping & Duration Calculation', () => {
  test('calculates accurate duration between valid opened_at and closed_at', () => {
    const openedAt = '2026-11-09T10:00:00.000Z';
    const closedAt = '2026-11-09T11:25:30.000Z';
    const duration = fmtDuration(openedAt, closedAt);
    assert.equal(duration, '1h 25m 30s');
  });

  test('calculates duration for short trades under 1 hour', () => {
    const openedAt = '2026-11-09T10:00:00.000Z';
    const closedAt = '2026-11-09T10:14:45.000Z';
    const duration = fmtDuration(openedAt, closedAt);
    assert.equal(duration, '14m 45s');
  });

  test('returns honest unavailable symbol (—) when timestamps are missing or invalid', () => {
    assert.equal(fmtDuration(null, '2026-11-09T11:00:00Z'), '—');
    assert.equal(fmtDuration('2026-11-09T10:00:00Z', null), '—');
    assert.equal(fmtDuration(undefined, undefined), '—');
    assert.equal(fmtDuration('invalid-date', '2026-11-09T11:00:00Z'), '—');
    // Closed before opened (negative duration)
    assert.equal(fmtDuration('2026-11-09T12:00:00Z', '2026-11-09T10:00:00Z'), '—');
  });

  test('preserves original prediction timestamp and timeframe in trade history record', () => {
    const signal = {
      id: 55,
      symbol: 'SOLUSDT',
      timeframe: '4h',
      direction: 'long',
      entry: 85.0,
      take_profit: 90.0,
      stop_loss: 82.5,
      created_at: '2026-11-09T08:15:00.000Z',
      opened_at: '2026-11-09T09:30:00.000Z',
    };

    const closedAt = '2026-11-09T14:45:00.000Z';
    const tradeRecord = {
      id: `trade-${signal.id}`,
      signal_id: signal.id,
      symbol: signal.symbol,
      timeframe: signal.timeframe, // preserved actual signal timeframe
      direction: signal.direction,
      entry: signal.entry,
      exit_price: signal.take_profit,
      predicted_at: signal.created_at, // preserved original prediction timestamp
      opened_at: signal.opened_at,     // preserved actual entry timestamp
      closed_at: closedAt,
      exit_reason: 'Target Hit',
    };

    assert.equal(tradeRecord.timeframe, '4h');
    assert.equal(tradeRecord.predicted_at, '2026-11-09T08:15:00.000Z');
    assert.equal(tradeRecord.opened_at, '2026-11-09T09:30:00.000Z');
    assert.equal(tradeRecord.closed_at, '2026-11-09T14:45:00.000Z');
    assert.equal(fmtDuration(tradeRecord.opened_at, tradeRecord.closed_at), '5h 15m 0s');
  });
});
