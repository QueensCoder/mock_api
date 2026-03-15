"""
Integration tests for the CDC → search index pipeline.

Tests the full flow from a CDC event arriving in Redis Streams through
to a document appearing in (or disappearing from) the RediSearch index.

The tests simulate what Redpanda Connect publishes to the stream,
then verify the indexing tasks produce the correct result in Redis Stack.

Requirements:
    - Redis Stack running on localhost:6379
    - Celery ALWAYS_EAGER mode (tasks run synchronously in-process)

No Postgres, no Redpanda Connect, no running Celery worker required.
"""

import json
import uuid

import pytest
import redis as redis_sync
import redis.asyncio as aioredis

from app.services.search import (
    ensure_indexes,
    search_items,
    search_projects,
)
from worker.tasks.search_index import delete_document, index_document, process_cdc_event

REDIS_URL = "redis://localhost:6379/0"
STREAM_KEY = "cdc:events"


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
async def redis_client():
    r = aioredis.from_url(REDIS_URL, decode_responses=True)
    await ensure_indexes(r)
    yield r
    await r.aclose()


@pytest.fixture(scope="module")
def redis_sync_client():
    """Sync client for Celery tasks (which are synchronous)."""
    return redis_sync.from_url(REDIS_URL, decode_responses=True)


@pytest.fixture(autouse=True)
async def cleanup(redis_client: aioredis.Redis):
    async for key in redis_client.scan_iter("item:pipe-*"):
        await redis_client.delete(key)
    async for key in redis_client.scan_iter("project:pipe-*"):
        await redis_client.delete(key)
    yield


@pytest.fixture(autouse=True)
def celery_eager(monkeypatch):
    """Run Celery tasks synchronously so tests don't need a running worker."""
    from worker.celery_app import celery

    celery.conf.task_always_eager = True
    celery.conf.task_eager_propagates = True
    yield
    celery.conf.task_always_eager = False


# ── Helpers ───────────────────────────────────────────────────────────────────


def new_id(prefix: str = "pipe") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def cdc_event(op: str, table: str, doc_id: str, data: dict | None = None) -> str:
    """Build the JSON payload that Redpanda Connect writes to the Redis Stream."""
    return json.dumps(
        {
            "op": op,
            "table": table,
            "id": doc_id,
            "data": data or {},
        }
    )


# ── index_document task tests ─────────────────────────────────────────────────


class TestIndexDocumentTask:
    def test_insert_indexes_item(self, redis_client):
        doc_id = new_id()
        data = {"id": doc_id, "title": "Pipeline Widget", "description": "CDC-sourced item"}

        index_document.apply(args=["items", doc_id, data])

        # Verify via async search in the event loop created by pytest-asyncio
        # We use a sync check here via the sync client for simplicity
        r = redis_sync.from_url(REDIS_URL, decode_responses=True)
        raw = r.json().get(f"item:{doc_id}", "$")
        assert raw is not None
        stored = raw[0] if isinstance(raw, list) else raw
        assert stored["title"] == "Pipeline Widget"

    def test_update_overwrites_document(self):
        doc_id = new_id()
        r = redis_sync.from_url(REDIS_URL, decode_responses=True)

        index_document.apply(
            args=["items", doc_id, {"id": doc_id, "title": "Old", "description": None}]
        )
        index_document.apply(
            args=[
                "items",
                doc_id,
                {"id": doc_id, "title": "New Updated Title", "description": None},
            ]
        )

        stored = r.json().get(f"item:{doc_id}", "$")
        assert stored[0]["title"] == "New Updated Title"

    def test_delete_removes_document(self):
        doc_id = new_id()
        r = redis_sync.from_url(REDIS_URL, decode_responses=True)

        index_document.apply(
            args=["items", doc_id, {"id": doc_id, "title": "To Delete", "description": None}]
        )
        assert r.exists(f"item:{doc_id}")

        delete_document.apply(args=["items", doc_id])
        assert not r.exists(f"item:{doc_id}")

    def test_unknown_table_does_not_raise(self):
        # Should log and return without error
        index_document.apply(args=["nonexistent_table", "some-id", {"title": "x"}])

    def test_project_indexing(self):
        doc_id = new_id()
        r = redis_sync.from_url(REDIS_URL, decode_responses=True)

        index_document.apply(
            args=[
                "projects",
                doc_id,
                {"id": doc_id, "name": "Pipeline Project", "description": None},
            ]
        )

        stored = r.json().get(f"project:{doc_id}", "$")
        assert stored[0]["name"] == "Pipeline Project"


# ── process_cdc_event task tests ──────────────────────────────────────────────


class TestProcessCdcEventTask:
    """
    Tests process_cdc_event — the task that parses a raw Redis Stream payload
    and dispatches index_document / delete_document.

    This is the bridge between the stream consumer and the indexing tasks.
    """

    def test_insert_event_indexes_document(self):
        doc_id = new_id()
        payload = cdc_event(
            "insert",
            "items",
            doc_id,
            {"id": doc_id, "title": "CDC Insert Item", "description": None},
        )

        process_cdc_event.apply(args=[payload])

        r = redis_sync.from_url(REDIS_URL, decode_responses=True)
        stored = r.json().get(f"item:{doc_id}", "$")
        assert stored is not None
        assert stored[0]["title"] == "CDC Insert Item"

    def test_update_event_indexes_document(self):
        doc_id = new_id()
        r = redis_sync.from_url(REDIS_URL, decode_responses=True)

        # Initial insert
        process_cdc_event.apply(
            args=[
                cdc_event(
                    "insert",
                    "items",
                    doc_id,
                    {"id": doc_id, "title": "Before", "description": None},
                )
            ]
        )
        # Update
        process_cdc_event.apply(
            args=[
                cdc_event(
                    "update",
                    "items",
                    doc_id,
                    {"id": doc_id, "title": "After Update", "description": None},
                )
            ]
        )

        stored = r.json().get(f"item:{doc_id}", "$")
        assert stored[0]["title"] == "After Update"

    def test_delete_event_removes_document(self):
        doc_id = new_id()
        r = redis_sync.from_url(REDIS_URL, decode_responses=True)

        process_cdc_event.apply(
            args=[
                cdc_event(
                    "insert",
                    "items",
                    doc_id,
                    {"id": doc_id, "title": "Gone Soon", "description": None},
                )
            ]
        )
        assert r.exists(f"item:{doc_id}")

        process_cdc_event.apply(args=[cdc_event("delete", "items", doc_id)])
        assert not r.exists(f"item:{doc_id}")

    def test_initial_snapshot_read_op_indexes_document(self):
        """Redpanda Connect emits op=read for rows captured during the initial snapshot."""
        doc_id = new_id()
        payload = cdc_event(
            "read", "items", doc_id, {"id": doc_id, "title": "Snapshot Item", "description": None}
        )

        process_cdc_event.apply(args=[payload])

        r = redis_sync.from_url(REDIS_URL, decode_responses=True)
        stored = r.json().get(f"item:{doc_id}", "$")
        assert stored is not None
        assert stored[0]["title"] == "Snapshot Item"

    def test_malformed_json_is_ignored(self):
        process_cdc_event.apply(args=["not-valid-json"])

    def test_incomplete_event_is_ignored(self):
        # Missing id — should not raise
        process_cdc_event.apply(args=[json.dumps({"op": "insert", "table": "items"})])


# ── Full pipeline: stream → search ────────────────────────────────────────────


class TestStreamToSearchIndex:
    """
    Verifies that after CDC events are processed, documents are discoverable
    via the RediSearch full-text search.

    Combines the indexing task with a real RediSearch query.
    """

    async def test_inserted_item_is_full_text_searchable(self, redis_client: aioredis.Redis):
        doc_id = new_id()
        payload = cdc_event(
            "insert",
            "items",
            doc_id,
            {"id": doc_id, "title": "Mechanical Keyboard", "description": "Tactile switches"},
        )

        process_cdc_event.apply(args=[payload])

        results = await search_items(redis_client, "Mechanical")
        assert any(d["id"] == doc_id for d in results)

    async def test_deleted_item_disappears_from_search(self, redis_client: aioredis.Redis):
        doc_id = new_id()

        process_cdc_event.apply(
            args=[
                cdc_event(
                    "insert",
                    "items",
                    doc_id,
                    {"id": doc_id, "title": "Temporary Item Xyz", "description": None},
                )
            ]
        )
        before = await search_items(redis_client, "Temporary Item Xyz")
        assert any(d["id"] == doc_id for d in before)

        process_cdc_event.apply(args=[cdc_event("delete", "items", doc_id)])

        after = await search_items(redis_client, "Temporary Item Xyz")
        assert not any(d["id"] == doc_id for d in after)

    async def test_project_cdc_event_searchable(self, redis_client: aioredis.Redis):
        doc_id = new_id()
        payload = cdc_event(
            "insert",
            "projects",
            doc_id,
            {"id": doc_id, "name": "Aurora Initiative", "description": "Northern lights project"},
        )

        process_cdc_event.apply(args=[payload])

        results = await search_projects(redis_client, "Aurora")
        assert any(d["id"] == doc_id for d in results)

    async def test_multiple_cdc_events_all_indexed(self, redis_client: aioredis.Redis):
        ids = [new_id() for _ in range(3)]
        for i, doc_id in enumerate(ids):
            process_cdc_event.apply(
                args=[
                    cdc_event(
                        "insert",
                        "items",
                        doc_id,
                        {"id": doc_id, "title": f"Batch Item UniqueSeq{i}", "description": None},
                    )
                ]
            )

        for i, doc_id in enumerate(ids):
            results = await search_items(redis_client, f"UniqueSeq{i}")
            assert any(d["id"] == doc_id for d in results), f"doc {doc_id} not found"
