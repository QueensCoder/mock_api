"""
Server-Sent Events (SSE) endpoint.

GET /api/v1/events/{channel_id}

Subscribes to a Redis pub/sub channel derived from the URL parameter,
polls for new messages every second, and streams them to the client as
SSE events.  A keep-alive comment is sent every 15 seconds so proxies
and browsers don't close the connection.

Publishing a message:
    PUBLISH events:42 '{"type": "order_updated", "id": 42}'

The event format on the wire:
    data: {"type": "order_updated", "id": 42}\n\n

Nginx requires proxy_buffering off on this path — see nginx/nginx.conf.
The X-Accel-Buffering: no response header also signals nginx to flush
immediately without requiring a config change per-route.
"""

import asyncio
import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis

from app.services.redis import get_redis

router = APIRouter()
logger = logging.getLogger(__name__)

POLL_INTERVAL: float = 1.0  # seconds between Redis get_message calls
HEARTBEAT_EVERY: int = 15  # send ": heartbeat" every N ticks (15 s)


@router.get(
    "/events/{channel_id}",
    summary="Stream events for a channel",
    description=(
        "Opens a long-lived SSE connection. "
        "Events are published to Redis via `PUBLISH events:{channel_id} <json>`."
    ),
    response_class=StreamingResponse,
    tags=["events"],
)
async def stream_events(channel_id: str, redis: Redis = Depends(get_redis)) -> StreamingResponse:
    return StreamingResponse(
        _generate(redis, channel_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx proxy buffering for this response
        },
    )


async def _generate(redis, channel_id: str) -> AsyncGenerator[str, None]:
    """
    Core generator — subscribes to events:{channel_id}, polls once per second,
    and yields SSE-formatted strings.

    Separated from the route handler so it can be unit-tested directly.
    """
    channel = f"events:{channel_id}"
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)
    logger.info("SSE: client connected, channel=%r", channel)

    ticks_without_heartbeat = 0
    try:
        while True:
            # Non-blocking check — returns None immediately if no message is queued.
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0)

            if message and message["type"] == "message":
                yield f"data: {message['data']}\n\n"
                ticks_without_heartbeat = 0
            else:
                ticks_without_heartbeat += 1
                if ticks_without_heartbeat >= HEARTBEAT_EVERY:
                    # SSE comment — keeps the connection alive through proxies / load balancers
                    yield ": heartbeat\n\n"
                    ticks_without_heartbeat = 0

            await asyncio.sleep(POLL_INTERVAL)

    except asyncio.CancelledError:
        # Client disconnected — exit cleanly.
        pass
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
        logger.info("SSE: client disconnected, channel=%r", channel)
