"""
Redis Streams consumer for CDC events published by Redpanda Connect.

Reads from the "cdc:events" stream and dispatches Celery tasks
to update the Redis Stack search index.

Run as a standalone process:
    python -m worker.stream_consumer

Consumer group semantics give at-least-once delivery. Each message is
acknowledged only after the Celery task has been dispatched successfully.
"""

import asyncio
import json
import logging
import os

import redis.asyncio as aioredis

from worker.tasks.composite_index import (
    delete_pet_from_index,
    index_pet_composite,
    reindex_owner_pets,
)
from worker.tasks.search_index import delete_document, index_document

logger = logging.getLogger(__name__)

STREAM_KEY = "cdc:events"
GROUP_NAME = "search_indexer"
CONSUMER_NAME = "consumer-1"
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")


async def _ensure_group(r: aioredis.Redis) -> None:
    """Create the consumer group if it does not already exist."""
    try:
        # id="0" means we replay from the beginning if the group is new.
        await r.xgroup_create(STREAM_KEY, GROUP_NAME, id="0", mkstream=True)
        logger.info("Consumer group %r created on stream %r", GROUP_NAME, STREAM_KEY)
    except Exception:
        pass  # Group already exists — normal on restart.


async def handle_event(event: dict) -> None:
    """
    Route a single parsed CDC event to the correct Celery task.
    Extracted so tests can call this without the consumer loop.
    """
    op = event.get("op")
    table = event.get("table")
    doc_id = event.get("id")

    if not all([op, table, doc_id]):
        logger.warning("Skipping malformed CDC event: %r", event)
        return

    if table == "pets":
        if op == "delete":
            delete_pet_from_index.delay(int(doc_id))
        else:
            index_pet_composite.delay(int(doc_id))
    elif table == "owners":
        # Owner changed — re-index all their pets so composite docs stay fresh
        reindex_owner_pets.delay(int(doc_id))
    elif op == "delete":
        delete_document.delay(table, doc_id)
    else:
        index_document.delay(table, doc_id, event.get("data", {}))


async def consume() -> None:
    r = aioredis.from_url(REDIS_URL, decode_responses=True)
    await _ensure_group(r)

    logger.info("Stream consumer listening on %r …", STREAM_KEY)

    while True:
        try:
            results = await r.xreadgroup(
                GROUP_NAME,
                CONSUMER_NAME,
                {STREAM_KEY: ">"},
                count=20,
                block=2000,  # ms — yields control if the stream is empty
            )
            if not results:
                continue

            for _stream, messages in results:
                for msg_id, fields in messages:
                    try:
                        raw = fields.get("payload", "{}")
                        event = json.loads(raw)
                        await handle_event(event)
                        await r.xack(STREAM_KEY, GROUP_NAME, msg_id)
                    except Exception:
                        logger.exception("Error processing message %s — leaving unacked", msg_id)

        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Stream consumer error — retrying in 2 s")
            await asyncio.sleep(2)

    await r.aclose()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    asyncio.run(consume())
