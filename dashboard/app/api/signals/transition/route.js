import { NextResponse } from 'next/server';

const API = process.env.API_URL || 'http://api:8000';

export async function POST(req) {
  try {
    const body = await req.json();
    if (!body || !body.signal_id) {
      return NextResponse.json({ error: 'Missing signal_id' }, { status: 400 });
    }

    try {
      const res = await fetch(`${API}/signals/transition`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(3000),
      });

      if (res.ok) {
        const data = await res.json();
        return NextResponse.json(data);
      }
    } catch {
      // Backend API might be booting or unconfigured; acknowledge safely
    }

    return NextResponse.json({
      status: 'acknowledged_local',
      signal_id: body.signal_id,
      lifecycle_status: body.status,
    });
  } catch (err) {
    return NextResponse.json({ error: err.message || 'Internal error' }, { status: 500 });
  }
}
