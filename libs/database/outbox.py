import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import psycopg
from psycopg.rows import dict_row
from libs.contracts.events import BaseEvent

log = logging.getLogger("database.outbox")


class OutboxRepository:
    """Manages transactional outbox events to ensure zero event loss on state transitions."""

    @staticmethod
    def append_event(cur: psycopg.Cursor, stream: str, event: BaseEvent):
        """Atomically commits event to outbox.events within the caller's database transaction."""
        payload_json = json.dumps(event.model_dump())
        cur.execute("""
            INSERT INTO outbox.events (
                event_id, stream, event_type, idempotency_key, payload, created_at, status
            ) VALUES (%s, %s, %s, %s, %s, now(), 'pending')
            ON CONFLICT (idempotency_key) DO NOTHING
        """, (
            event.event_id,
            stream,
            event.event_type,
            event.idempotency_key,
            payload_json,
        ))

    @staticmethod
    def fetch_pending(cur: psycopg.Cursor, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetches pending outbox events for publishing."""
        cur.execute("""
            SELECT id, event_id, stream, event_type, idempotency_key, payload
            FROM outbox.events
            WHERE status = 'pending'
            ORDER BY id ASC
            LIMIT %s
            FOR UPDATE SKIP LOCKED
        """, (limit,))
        return cur.fetchall()

    @staticmethod
    def mark_published(cur: psycopg.Cursor, event_ids: List[int]):
        """Marks successfully published events."""
        if not event_ids:
            return
        cur.execute("""
            UPDATE outbox.events
            SET status = 'published', published_at = now()
            WHERE id = ANY(%s)
        """, (event_ids,))

