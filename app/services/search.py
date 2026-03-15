"""
RediSearch service — manages JSON indexes for items and projects.

Each table gets:
  - A JSON document stored at  {prefix}:{uuid}
  - A RediSearch index over those documents

Call ensure_indexes() once on startup (idempotent).
"""

import json
import logging

from redis.asyncio import Redis
from redis.commands.search.field import TagField, TextField
from redis.commands.search.indexDefinition import IndexDefinition, IndexType
from redis.commands.search.query import Query

logger = logging.getLogger(__name__)

ITEM_INDEX = "idx:items"
PROJECT_INDEX = "idx:projects"

# Maps table name → (redis key prefix, index name)
_TABLE_MAP: dict[str, tuple[str, str]] = {
    "items": ("item", ITEM_INDEX),
    "projects": ("project", PROJECT_INDEX),
}


# ── Index creation ────────────────────────────────────────────────────────────


async def ensure_indexes(r: Redis) -> None:
    """Create RediSearch indexes if they do not already exist. Safe to call repeatedly."""
    await _ensure_item_index(r)
    await _ensure_project_index(r)


async def _ensure_item_index(r: Redis) -> None:
    try:
        await r.ft(ITEM_INDEX).info()
    except Exception:
        await r.ft(ITEM_INDEX).create_index(
            [
                TagField("$.id", as_name="id"),
                TextField("$.title", as_name="title", weight=5.0),
                TextField("$.description", as_name="description"),
            ],
            definition=IndexDefinition(prefix=["item:"], index_type=IndexType.JSON),
        )
        logger.info("Created RediSearch index %s", ITEM_INDEX)


async def _ensure_project_index(r: Redis) -> None:
    try:
        await r.ft(PROJECT_INDEX).info()
    except Exception:
        await r.ft(PROJECT_INDEX).create_index(
            [
                TagField("$.id", as_name="id"),
                TextField("$.name", as_name="name", weight=5.0),
                TextField("$.description", as_name="description"),
            ],
            definition=IndexDefinition(prefix=["project:"], index_type=IndexType.JSON),
        )
        logger.info("Created RediSearch index %s", PROJECT_INDEX)


# ── Write operations ──────────────────────────────────────────────────────────


async def index_document(r: Redis, table: str, doc_id: str, data: dict) -> None:
    """Upsert a document into the appropriate RediSearch index."""
    entry = _TABLE_MAP.get(table)
    if entry is None:
        logger.warning("search.index_document: unknown table %r — skipped", table)
        return
    prefix, _ = entry
    await r.json().set(f"{prefix}:{doc_id}", "$", data)


async def delete_document(r: Redis, table: str, doc_id: str) -> None:
    """Remove a document from the index."""
    entry = _TABLE_MAP.get(table)
    if entry is None:
        return
    prefix, _ = entry
    await r.delete(f"{prefix}:{doc_id}")


# ── Read operations ───────────────────────────────────────────────────────────


async def search_items(r: Redis, query: str, limit: int = 20) -> list[dict]:
    return await _search(r, ITEM_INDEX, query, limit)


async def search_projects(r: Redis, query: str, limit: int = 20) -> list[dict]:
    return await _search(r, PROJECT_INDEX, query, limit)


async def _search(r: Redis, index: str, query: str, limit: int) -> list[dict]:
    try:
        q = Query(query).paging(0, limit)
        results = await r.ft(index).search(q)
        return [json.loads(doc.json) for doc in results.docs]
    except Exception:
        logger.exception("search error on index %s query %r", index, query)
        return []
