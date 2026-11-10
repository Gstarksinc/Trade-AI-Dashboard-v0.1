import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, List, Optional
import redis.asyncio as aioredis
from libs.contracts.events import BaseEvent, SystemDLQEvent, SystemDLQPayload

log = logging.getLogger("common.streams")


class RedisStreamManager:
    """Production Redis Streams client with consumer groups, ack/retry, and DLQ."""

    def __init__(self, redis_url: str, service_name: str):
        self.redis_url = redis_url
        self.service_name = service_name
        self.client: Optional[aioredis.Redis] = None
        self._retry_tracker: Dict[str, int] = {}  # event_id -> retry_count

    async def connect(self):
        if not self.client:
            self.client = aioredis.from_url(self.redis_url, decode_responses=True)
            await self.client.ping()
            log.info("Connected to Redis Streams at %s", self.redis_url)

    async def close(self):
        if self.client:
            await self.client.aclose()
            self.client = None

    async def ensure_consumer_group(self, stream: str, group_name: str):
        """Creates consumer group on the stream if it does not already exist."""
        assert self.client is not None, "Client not connected"
        try:
            await self.client.xgroup_create(stream, group_name, id="$", mkstream=True)
            log.info("Created consumer group '%s' on stream '%s'", group_name, stream)
        except aioredis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    async def publish_event(
        self,
        stream: str,
        event: BaseEvent,
        maxlen: Optional[int] = None,
        approximate: bool = True,
    ) -> str:
        """
        Publishes a versioned event to a Redis Stream with trimming.
        If the event is price.tick, also updates 'price:{symbol}' key.
        """
        assert self.client is not None, "Client not connected"
        payload_dict = event.model_dump()
        fields = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "event_version": event.event_version,
            "idempotency_key": event.idempotency_key,
            "timestamp": event.timestamp,
            "producer": event.producer,
            "data": json.dumps(payload_dict["payload"]),
        }

        entry_id = await self.client.xadd(
            name=stream,
            fields=fields,
            maxlen=maxlen,
            approximate=approximate,
        )

        # Optimize latest price cache on tick events
        if event.event_type == "price.tick" and "symbol" in payload_dict["payload"]:
            sym = payload_dict["payload"]["symbol"]
            await self.client.set(f"price:{sym}", json.dumps(payload_dict["payload"]))

        return entry_id

    # Alias for publish_event
    publish = publish_event

    async def get_latest_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Retrieves latest cached price for symbol directly from key."""
        assert self.client is not None, "Client not connected"
        raw = await self.client.get(f"price:{symbol}")
        return json.loads(raw) if raw else None

    async def route_to_dlq(
        self,
        original_stream: str,
        group_name: str,
        entry_id: str,
        fields: Dict[str, str],
        error: Exception,
    ):
        """Sends persistently failing event to system.dlq stream."""
        assert self.client is not None, "Client not connected"
        event_id = fields.get("event_id", entry_id)
        retry_count = self._retry_tracker.get(event_id, 1)

        dlq_event = SystemDLQEvent(
            idempotency_key=f"dlq-{event_id}-{entry_id}",
            producer=self.service_name,
            payload=SystemDLQPayload(
                failed_service=self.service_name,
                original_stream=original_stream,
                consumer_group=group_name,
                error_type=type(error).__name__,
                error_message=str(error),
                raw_payload=json.dumps(fields),
                retry_count=retry_count,
                first_failed_at=datetime.now(timezone.utc).isoformat(),
            ),
        )

        await self.client.xadd(
            name="system.dlq",
            fields={"event": json.dumps(dlq_event.model_dump())},
            maxlen=10000,
        )
        # Ack from original stream to prevent poison-pill blocking
        await self.client.xack(original_stream, group_name, entry_id)
        self._retry_tracker.pop(event_id, None)
        log.error("Routed poisoned message %s from stream %s to system.dlq: %s", entry_id, original_stream, error)

    async def consume_loop(
        self,
        stream: str = "",
        group_name: str = "",
        consumer_name: str = "",
        handler: Callable[[Dict[str, Any]], Coroutine[Any, Any, None]] = None,
        batch_size: int = 10,
        block_ms: int = 2000,
        max_retries: int = 3,
        shutdown_event: Optional[asyncio.Event] = None,
        stream_name: Optional[str] = None,
    ):
        """Standard consumer group loop with acknowledgment, retry handling, and DLQ."""
        target_stream = stream or stream_name
        assert target_stream, "Stream name must be provided"
        stream = target_stream
        assert self.client is not None, "Client not connected"
        await self.ensure_consumer_group(stream, group_name)

        while shutdown_event is None or not shutdown_event.is_set():
            try:
                # 1. Read new events from consumer group
                resp = await self.client.xreadgroup(
                    groupname=group_name,
                    consumername=consumer_name,
                    streams={target_stream: ">"},
                    count=batch_size,
                    block=block_ms,
                )

                if not resp:
                    continue

                for _, entries in resp:
                    for entry_id, fields in entries:
                        event_id = fields.get("event_id", entry_id)
                        try:
                            # Reconstitute typed event
                            event_data = {
                                "event_id": event_id,
                                "event_type": fields.get("event_type"),
                                "event_version": fields.get("event_version"),
                                "idempotency_key": fields.get("idempotency_key"),
                                "timestamp": fields.get("timestamp"),
                                "producer": fields.get("producer"),
                                "payload": json.loads(fields.get("data", "{}")),
                            }

                            await handler(event_data)
                            await self.client.xack(stream, group_name, entry_id)
                            self._retry_tracker.pop(event_id, None)

                        except Exception as e:
                            log.exception("Handler failed for event %s on stream %s: %s", entry_id, stream, e)
                            retries = self._retry_tracker.get(event_id, 0) + 1
                            self._retry_tracker[event_id] = retries

                            if retries >= max_retries:
                                await self.route_to_dlq(stream, group_name, entry_id, fields, e)

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("Error in stream consumer loop %s: %s", stream, e)
                await asyncio.sleep(1.0)

