"""
Composite pet+owner search index tasks.

Two CDC sources feed into one Redis document per pet:

  pets table  → index_pet_composite(pet_id)
                Fetches pet + owner → writes pet:{id}

  owners table → reindex_owner_pets(owner_id)
                 Finds all live pets for the owner →
                 dispatches index_pet_composite for each

This keeps the search index consistent regardless of which table changed.
"""

import asyncio
import logging

import redis as redis_sync
from sqlalchemy import select

from app.core.config import settings
from app.models.owner import Owner
from app.models.pet import Pet
from app.services.search import build_pet_doc
from worker.celery_app import celery
from worker.db import task_db

logger = logging.getLogger(__name__)

_pool = redis_sync.ConnectionPool.from_url(settings.REDIS_URL, decode_responses=True)


def _redis() -> redis_sync.Redis:
    return redis_sync.Redis(connection_pool=_pool)


# ── index_pet_composite ────────────────────────────────────────────────────────


@celery.task(name="search.index_pet_composite", bind=True, max_retries=3, default_retry_delay=5)
def index_pet_composite(self, pet_id: int) -> None:
    """
    Fetch the pet and its owner from Postgres and write/update the
    composite document in the Redis Stack search index.

    Called when a pet row changes (insert / update / read snapshot).
    """
    try:
        asyncio.run(_do_index_pet(pet_id))
    except Exception as exc:
        logger.exception("index_pet_composite failed for pet_id=%s", pet_id)
        raise self.retry(exc=exc)


async def _do_index_pet(pet_id: int) -> None:
    async with task_db() as db:
        result = await db.execute(
            select(Pet, Owner)
            .join(Owner, Pet.owner_id == Owner.id)
            .where(Pet.id == pet_id, Pet.deleted_at.is_(None))
        )
        row = result.first()

    if row is None:
        # Pet was deleted or owner missing — remove from index
        _redis().delete(f"pet:{pet_id}")
        logger.debug("pet:%s removed from index (not found or deleted)", pet_id)
        return

    pet, owner = row
    doc = build_pet_doc(
        {
            "id": pet.id,
            "name": pet.name,
            "species": pet.species,
            "breed": pet.breed,
            "date_of_birth": pet.date_of_birth,
        },
        {
            "id": owner.id,
            "first_name": owner.first_name,
            "last_name": owner.last_name,
            "email": owner.email,
            "phone": owner.phone,
        },
    )
    _redis().json().set(f"pet:{pet_id}", "$", doc)
    logger.debug("pet:%s indexed (owner:%s)", pet_id, owner.id)


# ── reindex_owner_pets ─────────────────────────────────────────────────────────


@celery.task(name="search.reindex_owner_pets", bind=True, max_retries=3, default_retry_delay=5)
def reindex_owner_pets(self, owner_id: int) -> None:
    """
    Called when an owner row changes.
    Re-indexes all live pets for that owner so their composite documents
    reflect the updated owner data.
    """
    try:
        asyncio.run(_do_reindex_owner_pets(owner_id))
    except Exception as exc:
        logger.exception("reindex_owner_pets failed for owner_id=%s", owner_id)
        raise self.retry(exc=exc)


async def _do_reindex_owner_pets(owner_id: int) -> None:
    async with task_db() as db:
        result = await db.execute(
            select(Pet.id).where(
                Pet.owner_id == owner_id,
                Pet.deleted_at.is_(None),
            )
        )
        pet_ids = result.scalars().all()

    logger.debug("reindex_owner_pets: owner=%s → %d pets", owner_id, len(pet_ids))
    for pet_id in pet_ids:
        index_pet_composite.delay(pet_id)


# ── delete_pet_from_index ──────────────────────────────────────────────────────


@celery.task(name="search.delete_pet_from_index")
def delete_pet_from_index(pet_id: int) -> None:
    """Called when a pet is soft-deleted via CDC."""
    _redis().delete(f"pet:{pet_id}")
    logger.debug("pet:%s deleted from index", pet_id)
