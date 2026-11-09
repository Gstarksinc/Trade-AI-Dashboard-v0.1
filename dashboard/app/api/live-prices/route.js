import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

const BINANCE_FAPI = process.env.BINANCE_FAPI_URL || 'https://fapi.binance.com';
const TRACKED = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'DOGEUSDT', 'LINKUSDT', 'TRXUSDT'];

export async function GET() {
  try {
    // Fetch 24hr tickers for price, change, high, low
    const res = await fetch(`${BINANCE_FAPI}/fapi/v1/ticker/24hr`, {
      cache: 'no-store',
      signal: AbortSignal.timeout(2500),
    });

    if (!res.ok) {
      throw new Error(`Binance responded with status ${res.status}`);
    }

    const items = await res.json();
    const prices = {};

    for (const item of items) {
      if (TRACKED.includes(item.symbol)) {
        prices[item.symbol] = {
          symbol: item.symbol,
          price: Number(item.lastPrice),
          change: Number(item.priceChangePercent),
          high: Number(item.highPrice),
          low: Number(item.lowPrice),
          vol: Number(item.quoteVolume),
          ts: item.closeTime || Date.now(),
        };
      }
    }

    return NextResponse.json({
      success: true,
      timestamp: Date.now(),
      prices,
    }, {
      headers: {
        'Cache-Control': 'no-cache, no-store, must-revalidate',
      },
    });
  } catch (err) {
    // If Binance is momentarily slow, fetch simple /fapi/v1/ticker/price
    try {
      const priceRes = await fetch(`${BINANCE_FAPI}/fapi/v1/ticker/price`, {
        cache: 'no-store',
        signal: AbortSignal.timeout(2000),
      });
      if (priceRes.ok) {
        const list = await priceRes.json();
        const prices = {};
        for (const item of list) {
          if (TRACKED.includes(item.symbol)) {
            prices[item.symbol] = {
              symbol: item.symbol,
              price: Number(item.price),
              ts: item.time || Date.now(),
            };
          }
        }
        return NextResponse.json({
          success: true,
          timestamp: Date.now(),
          prices,
        });
      }
    } catch {}

    return NextResponse.json({
      success: false,
      timestamp: Date.now(),
      error: err.message,
    }, { status: 502 });
  }
}

