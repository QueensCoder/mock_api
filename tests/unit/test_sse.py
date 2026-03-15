"""
Unit tests for the SSE event generator.

Tests the _generate() coroutine directly with a mocked Redis pub/sub client.
No running Redis or HTTP server required.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.v1.endpoints.events import HEARTBEAT_EVERY, POLL_INTERVAL, _generate

# ── Helpers ───────────────────────────────────────────────────────────────────


def make_pubsub(messages: list[dict | None]) -> MagicMock:
    """
    Build a mock pub/sub object whose get_message() returns items from
    `messages` in order, then raises asyncio.CancelledError to stop the loop.
    """
    pubsub = MagicMock()
    pubsub.subscribe = AsyncMock()
    pubsub.unsubscribe = AsyncMock()
    pubsub.aclose = AsyncMock()

    side_effects = list(messages) + [asyncio.CancelledError()]
    pubsub.get_message = AsyncMock(side_effect=side_effects)
    return pubsub


def make_redis(pubsub: MagicMock) -> MagicMock:
    redis = MagicMock()
    redis.pubsub = MagicMock(return_value=pubsub)
    return redis


async def collect(gen) -> list[str]:
    """Drain an async generator into a list."""
    results = []
    async for chunk in gen:
        results.append(chunk)
    return results


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestSSEGenerator:
    @patch("app.api.v1.endpoints.events.asyncio.sleep", new_callable=AsyncMock)
    async def test_message_yielded_as_sse_data(self, mock_sleep):
        msg = {"type": "message", "data": '{"event":"order_updated","id":42}'}
        pubsub = make_pubsub([msg])
        redis = make_redis(pubsub)

        chunks = await collect(_generate(redis, "42"))

        assert 'data: {"event":"order_updated","id":42}\n\n' in chunks

    @patch("app.api.v1.endpoints.events.asyncio.sleep", new_callable=AsyncMock)
    async def test_subscribes_to_correct_channel(self, mock_sleep):
        pubsub = make_pubsub([])
        redis = make_redis(pubsub)

        await collect(_generate(redis, "99"))

        pubsub.subscribe.assert_awaited_once_with("events:99")

    @patch("app.api.v1.endpoints.events.asyncio.sleep", new_callable=AsyncMock)
    async def test_unsubscribes_on_cancel(self, mock_sleep):
        pubsub = make_pubsub([])
        redis = make_redis(pubsub)

        await collect(_generate(redis, "1"))

        pubsub.unsubscribe.assert_awaited_once_with("events:1")
        pubsub.aclose.assert_awaited_once()

    @patch("app.api.v1.endpoints.events.asyncio.sleep", new_callable=AsyncMock)
    async def test_no_message_yields_nothing_until_heartbeat(self, mock_sleep):
        # None → no message; after HEARTBEAT_EVERY ticks a heartbeat is sent.
        pubsub = make_pubsub([None] * HEARTBEAT_EVERY)
        redis = make_redis(pubsub)

        chunks = await collect(_generate(redis, "1"))

        assert ": heartbeat\n\n" in chunks
        # No data: lines — only the heartbeat comment
        assert not any(c.startswith("data:") for c in chunks)

    @patch("app.api.v1.endpoints.events.asyncio.sleep", new_callable=AsyncMock)
    async def test_heartbeat_resets_after_message(self, mock_sleep):
        """After a real message the tick counter resets, so no early heartbeat."""
        msg = {"type": "message", "data": "{}"}
        # message at tick 0, then HEARTBEAT_EVERY - 1 empty ticks → no heartbeat yet
        pubsub = make_pubsub([msg] + [None] * (HEARTBEAT_EVERY - 1))
        redis = make_redis(pubsub)

        chunks = await collect(_generate(redis, "1"))

        assert "data: {}\n\n" in chunks
        assert ": heartbeat\n\n" not in chunks

    @patch("app.api.v1.endpoints.events.asyncio.sleep", new_callable=AsyncMock)
    async def test_multiple_messages_all_yielded(self, mock_sleep):
        messages = [
            {"type": "message", "data": '{"n":1}'},
            {"type": "message", "data": '{"n":2}'},
            {"type": "message", "data": '{"n":3}'},
        ]
        pubsub = make_pubsub(messages)
        redis = make_redis(pubsub)

        chunks = await collect(_generate(redis, "x"))

        assert chunks == [
            'data: {"n":1}\n\n',
            'data: {"n":2}\n\n',
            'data: {"n":3}\n\n',
        ]

    @patch("app.api.v1.endpoints.events.asyncio.sleep", new_callable=AsyncMock)
    async def test_sleeps_once_per_tick(self, mock_sleep):
        pubsub = make_pubsub([None, None])  # 2 ticks before cancel
        redis = make_redis(pubsub)

        await collect(_generate(redis, "1"))

        assert mock_sleep.await_count == 2
        mock_sleep.assert_awaited_with(POLL_INTERVAL)

    @patch("app.api.v1.endpoints.events.asyncio.sleep", new_callable=AsyncMock)
    async def test_non_message_type_not_yielded(self, mock_sleep):
        """Redis pub/sub emits subscribe/unsubscribe confirmations — ignore them."""
        pubsub = make_pubsub([{"type": "subscribe", "data": 1}])
        redis = make_redis(pubsub)

        chunks = await collect(_generate(redis, "1"))

        assert not any(c.startswith("data:") for c in chunks)


class TestSSERoute:
    """Integration-style tests for the HTTP endpoint via ASGI transport."""

    async def test_returns_200_with_event_stream_content_type(self):
        from httpx import ASGITransport, AsyncClient

        from app.main import app
        from app.services.redis import get_redis

        # A pubsub that immediately cancels so the stream closes cleanly
        pubsub = MagicMock()
        pubsub.subscribe = AsyncMock()
        pubsub.unsubscribe = AsyncMock()
        pubsub.aclose = AsyncMock()
        pubsub.get_message = AsyncMock(side_effect=asyncio.CancelledError())

        mock_redis = MagicMock()
        mock_redis.pubsub = MagicMock(return_value=pubsub)

        # get_redis is used via Depends — override must return the mock directly
        app.dependency_overrides[get_redis] = lambda: mock_redis

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                async with client.stream("GET", "/api/v1/events/42") as resp:
                    assert resp.status_code == 200
                    assert "text/event-stream" in resp.headers["content-type"]
                    assert resp.headers["x-accel-buffering"] == "no"
                    assert resp.headers["cache-control"] == "no-cache"
        finally:
            app.dependency_overrides.clear()
