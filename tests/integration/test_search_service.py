"""
Integration tests for the RediSearch service.

These tests require a running Redis Stack instance (redis/redis-stack).
They do NOT require Postgres or the CDC pipeline — they test the
search service layer directly.

Run the stack first:
    docker compose up -d redis

Then run tests:
    pytest tests/integration/test_search_service.py -v
"""

import uuid

import pytest
import redis.asyncio as aioredis

from app.services.search import (
    delete_document,
    ensure_indexes,
    index_document,
    search_items,
    search_projects,
)

REDIS_URL = "redis://localhost:6379/0"


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
async def redis_client():
    """Redis Stack client shared across all tests in this module."""
    r = aioredis.from_url(REDIS_URL, decode_responses=True)
    await ensure_indexes(r)
    yield r
    await r.aclose()


@pytest.fixture(autouse=True)
async def cleanup(redis_client: aioredis.Redis):
    """Delete all indexed documents before each test for a clean slate."""
    # Delete known test key patterns — safe because tests use deterministic IDs.
    async for key in redis_client.scan_iter("item:test-*"):
        await redis_client.delete(key)
    async for key in redis_client.scan_iter("project:test-*"):
        await redis_client.delete(key)
    yield


# ── Helpers ───────────────────────────────────────────────────────────────────


def item_id(suffix: str = "") -> str:
    return f"test-{suffix or uuid.uuid4().hex[:8]}"


def project_id(suffix: str = "") -> str:
    return f"test-{suffix or uuid.uuid4().hex[:8]}"


# ── Item index tests ──────────────────────────────────────────────────────────


class TestItemIndex:
    async def test_indexed_item_is_searchable(self, redis_client: aioredis.Redis):
        doc_id = item_id("widget-001")
        await index_document(
            redis_client,
            "items",
            doc_id,
            {"id": doc_id, "title": "Blue Widget", "description": "A small blue widget"},
        )

        results = await search_items(redis_client, "Blue Widget")

        assert any(d["id"] == doc_id for d in results)

    async def test_search_matches_partial_title(self, redis_client: aioredis.Redis):
        doc_id = item_id("gadget-001")
        await index_document(
            redis_client,
            "items",
            doc_id,
            {"id": doc_id, "title": "Ergonomic Gadget", "description": None},
        )

        results = await search_items(redis_client, "Ergonomic")

        assert any(d["id"] == doc_id for d in results)

    async def test_search_matches_description(self, redis_client: aioredis.Redis):
        doc_id = item_id("desc-001")
        await index_document(
            redis_client,
            "items",
            doc_id,
            {"id": doc_id, "title": "Generic Item", "description": "Made from recycled aluminium"},
        )

        results = await search_items(redis_client, "recycled")

        assert any(d["id"] == doc_id for d in results)

    async def test_update_replaces_document(self, redis_client: aioredis.Redis):
        doc_id = item_id("update-001")
        await index_document(
            redis_client, "items", doc_id, {"id": doc_id, "title": "Old Title", "description": None}
        )
        await index_document(
            redis_client,
            "items",
            doc_id,
            {"id": doc_id, "title": "New Title Updated", "description": None},
        )

        results = await search_items(redis_client, "New Title Updated")
        assert any(d["id"] == doc_id for d in results)

        old_results = await search_items(redis_client, "Old Title")
        assert not any(d["id"] == doc_id for d in old_results)

    async def test_deleted_item_not_searchable(self, redis_client: aioredis.Redis):
        doc_id = item_id("delete-001")
        await index_document(
            redis_client,
            "items",
            doc_id,
            {"id": doc_id, "title": "Delete Me Please", "description": None},
        )
        # Verify it's indexed
        before = await search_items(redis_client, "Delete Me Please")
        assert any(d["id"] == doc_id for d in before)

        await delete_document(redis_client, "items", doc_id)

        after = await search_items(redis_client, "Delete Me Please")
        assert not any(d["id"] == doc_id for d in after)

    async def test_unknown_table_is_ignored(self, redis_client: aioredis.Redis):
        # Should not raise — just log a warning and return
        await index_document(redis_client, "unknown_table", "any-id", {"title": "x"})

    async def test_no_results_for_unknown_query(self, redis_client: aioredis.Redis):
        results = await search_items(redis_client, "xyznonexistentterm12345")
        assert results == []


# ── Project index tests ───────────────────────────────────────────────────────


class TestProjectIndex:
    async def test_indexed_project_is_searchable(self, redis_client: aioredis.Redis):
        doc_id = project_id("alpha-001")
        await index_document(
            redis_client,
            "projects",
            doc_id,
            {"id": doc_id, "name": "Project Alpha", "description": "First project"},
        )

        results = await search_projects(redis_client, "Alpha")

        assert any(d["id"] == doc_id for d in results)

    async def test_deleted_project_not_searchable(self, redis_client: aioredis.Redis):
        doc_id = project_id("beta-del")
        await index_document(
            redis_client,
            "projects",
            doc_id,
            {"id": doc_id, "name": "Project Beta Delete", "description": None},
        )
        await delete_document(redis_client, "projects", doc_id)

        results = await search_projects(redis_client, "Beta Delete")
        assert not any(d["id"] == doc_id for d in results)

    async def test_items_and_projects_indexed_independently(self, redis_client: aioredis.Redis):
        """A term in projects should not appear in item search results."""
        p_id = project_id("xunique")
        await index_document(
            redis_client,
            "projects",
            p_id,
            {"id": p_id, "name": "UniqueTerm9991 Project", "description": None},
        )

        item_results = await search_items(redis_client, "UniqueTerm9991")
        assert item_results == []

        proj_results = await search_projects(redis_client, "UniqueTerm9991")
        assert any(d["id"] == p_id for d in proj_results)
