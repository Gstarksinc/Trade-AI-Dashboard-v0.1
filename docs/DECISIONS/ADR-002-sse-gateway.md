# ADR 002: Server-Sent Events (SSE) for Browser Delivery

## Status
Accepted

## Context
The Next.js web dashboard requires real-time price tick updates and signal lifecycle state notifications. Bidirectional WebSockets add complexity (heartbeat ping/pong frames, stateful reconnection logic, custom frame formats, reverse-proxy buffer management). The browser is strictly a consumer and never transmits data to the server over the live stream.

## Decision
Implement a unidirectional **Server-Sent Events (SSE)** endpoint at `GET /events/stream` on `api-gateway`:
1. Uses standard HTTP/1.1 and HTTP/2 chunked transfer encoding (`text/event-stream`).
2. Supports native browser `EventSource` with automated browser-level reconnection.
3. Implements `Last-Event-ID` header to replay missed `signal.state_changed` events upon reconnection.
4. Transmits 15-second comment heartbeats (`: heartbeat\n\n`) to maintain middlebox keep-alive.

## Consequences
- **Positive**: Extremely simple client implementation; native browser reconnects; standard HTTP proxy compatibility.
- **Negative**: Unidirectional only (which perfectly matches our read-only dashboard architectural policy).

