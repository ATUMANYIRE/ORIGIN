"""Real-time event broadcaster with Redis pub/sub coordination and local SSE fan-out."""

import asyncio
import contextlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class TelemetryEventBus:
    """Coordinates real-time telemetry and topology notifications for SSE clients."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._redis: Redis | None = None
        self._redis_checked: bool = False

    async def _get_redis(self) -> Redis | None:
        if self._redis_checked:
            return self._redis
        self._redis_checked = True
        settings = get_settings()
        try:
            client: Redis = Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=0.5,
                socket_timeout=0.5,
            )
            await client.ping()
            self._redis = client
        except Exception as exc:
            logger.debug("Redis unavailable, using in-process event bus: %s", exc)
            self._redis = None
        return self._redis

    async def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        """Broadcast an event to all connected SSE subscribers and Redis channel."""
        envelope: dict[str, Any] = {
            "event_type": event_type,
            "timestamp": datetime.now(UTC).isoformat(),
            "payload": payload,
        }
        for queue in list(self._subscribers):
            if queue.full():
                with contextlib.suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
            with contextlib.suppress(asyncio.QueueFull):
                queue.put_nowait(envelope)

        redis_client = await self._get_redis()
        if redis_client is not None:
            try:
                await redis_client.publish("origin:telemetry:events", json.dumps(envelope))
                await redis_client.set(
                    "origin:telemetry:last_event_ts",
                    envelope["timestamp"],
                    ex=3600,
                )
            except Exception as exc:
                logger.debug("Redis publish skipped: %s", exc)

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        """Register a new subscriber queue for SSE streaming."""
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        """Remove a subscriber queue."""
        self._subscribers.discard(queue)

    async def redis_status(self) -> dict[str, Any]:
        """Return current Redis connectivity status."""
        client = await self._get_redis()
        if client is None:
            return {"connected": False, "mode": "in_memory_fallback"}
        try:
            await client.ping()
            return {"connected": True, "mode": "redis_coordinated"}
        except Exception:
            return {"connected": False, "mode": "in_memory_fallback"}


event_bus = TelemetryEventBus()
