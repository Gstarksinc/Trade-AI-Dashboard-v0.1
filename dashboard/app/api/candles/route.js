import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

const BINANCE_FAPI = process.env.BINANCE_FAPI_URL || 'https://fapi.binance.com';
const TRACKED = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'DOGEUSDT', 'LINKUSDT', 'TRXUSDT'];

export async function GET(request) {
  const { searchParams } = new URL(request.url);
  const symbol = (searchParams.get('symbol') || 'BTCUSDT').toUpperCase();
  const interval = searchParams.get('interval') || '1h';
  const limit = Math.min(100, Math.max(10, Number(searchParams.get('limit')) || 48));

  if (!TRACKED.includes(symbol)) {
    return NextResponse.json({ error: 'Unsupported symbol' }, { status: 400 });
  }

  try {
    const res = await fetch(
      `${BINANCE_FAPI}/fapi/v1/klines?symbol=${encodeURIComponent(symbol)}&interval=${encodeURIComponent(interval)}&limit=${limit}`,
      {
        cache: 'no-store',
        signal: AbortSignal.timeout(3500),
      }
    );

    if (!res.ok) {
      throw new Error(`Binance responded with status ${res.status}`);
    }

    const rawKlines = await res.json();
    const candles = rawKlines.map((k) => ({
      time: Number(k[0]),
      open: Number(k[1]),
      high: Number(k[2]),
      low: Number(k[3]),
      close: Number(k[4]),
      volume: Number(k[5]),
      closeTime: Number(k[6]),
    }));

    return NextResponse.json({
      success: true,
      symbol,
      interval,
      candles,
    }, {
      headers: {
        'Cache-Control': 'no-cache, no-store, must-revalidate',
      },
    });
  } catch (err) {
    return NextResponse.json({
      success: false,
      symbol,
      interval,
      candles: [],
      error: err.message || 'Failed to fetch candlestick data from Binance Futures',
    }, { status: 502 });
  }
}

