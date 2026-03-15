"""
Celery tasks for writing CDC events into the Redis Stack search index.

Uses a sync Redis client (redis.Redis) because Celery tasks are synchronous.
The RedisJSON and RediSearch commands are available on Redis Stack.
"""

import json
import logging

import redis as redis_sync

from app.core.config import settings
from worker.celery_app import celery

logger = logging.getLogger(__name__)

_TABLE_PREFIX: dict[str, str] = {
    "items": "item",
    "projects": "project",
}


def _redis() -> redis_sync.Redis:
    return redis_sync.from_url(settings.REDIS_URL, decode_responses=True)


@celery.task(name="search.index_document", bind=True, max_retries=3, default_retry_delay=5)
def index_document(self, table: str, doc_id: str, data: dict) -> None:
    """Upsert a JSON document into the Redis Stack search index."""
    prefix = _TABLE_PREFIX.get(table)
    if prefix is None:
        logger.warning("index_document: unknown table %r — skipped", table)
        return
    try:
        r = _redis()
        r.json().set(f"{prefix}:{doc_id}", "$", data)
        logger.debug("Indexed %s:%s", prefix, doc_id)
    except Exception as exc:
        logger.exception("index_document failed for %s:%s", table, doc_id)
        raise self.retry(exc=exc)


@celery.task(name="search.delete_document", bind=True, max_retries=3, default_retry_delay=5)
def delete_document(self, table: str, doc_id: str) -> None:
    """Remove a document from the Redis Stack search index."""
    prefix = _TABLE_PREFIX.get(table)
    if prefix is None:
        return
    try:
        r = _redis()
        r.delete(f"{prefix}:{doc_id}")
        logger.debug("Deleted %s:%s from index", prefix, doc_id)
    except Exception as exc:
        logger.exception("delete_document failed for %s:%s", table, doc_id)
        raise self.retry(exc=exc)


@celery.task(name="search.process_cdc_event")
def process_cdc_event(payload_json: str) -> None:
    """
    Parse a raw CDC event payload (from Redis Streams) and dispatch the
    appropriate index or delete task.

    Separated from the stream consumer so it can be called directly in tests.
    """
    try:
        event = json.loads(payload_json)
    except json.JSONDecodeError:
        logger.error("process_cdc_event: invalid JSON payload: %r", payload_json)
        return

    op = event.get("op")
    table = event.get("table")
    doc_id = event.get("id")

    if not all([op, table, doc_id]):
        logger.warning("process_cdc_event: incomplete event %r — skipped", event)
        return

    if op == "delete":
        delete_document.delay(table, doc_id)
    else:
        index_document.delay(table, doc_id, event.get("data", {}))
