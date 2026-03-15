"""
RediSearch service — manages JSON indexes for items, projects, and the
composite pet+owner index.

Composite pet index
-------------------
A single Redis document per pet (key: pet:{id}) contains denormalized
data from both the pets and owners tables:

    {
      "pet_id":          1,
      "name":            "Max",
      "species":         "dog",
      "breed":           "Labrador Retriever",
      "date_of_birth":   "2020-03-15",
      "owner_id":        5,
      "owner_first_name": "John",
      "owner_last_name":  "Doe",
      "owner_email":     "john@example.com",
      "owner_phone":     "555-1234",
      "full_text":       "Max dog Labrador John Doe"   ← boosted field
    }

Both CDC tables (pets + owners) update this document via Celery tasks.
Changing an owner re-indexes all their pets automatically.

Search features
---------------
* Full-text BM25 ranking across all text fields
* Fuzzy matching (%term%) for typo tolerance  — configurable distance
* Highlighted snippets with <mark>…</mark> tags
* Tag filters: owner_id, species_tag
* Pagination: skip / limit
"""

import json
import logging

from redis.asyncio import Redis
from redis.commands.search.field import TagField, TextField
from redis.commands.search.indexDefinition import IndexDefinition, IndexType
from redis.commands.search.query import Query

logger = logging.getLogger(__name__)

# ── Index names ────────────────────────────────────────────────────────────────

ITEM_INDEX = "idx:items"
PROJECT_INDEX = "idx:projects"
PET_INDEX = "idx:pets"

_SIMPLE_TABLE_MAP: dict[str, tuple[str, str]] = {
    "items": ("item", ITEM_INDEX),
    "projects": ("project", PROJECT_INDEX),
}


# ── Startup ────────────────────────────────────────────────────────────────────


async def ensure_indexes(r: Redis) -> None:
    await _ensure_item_index(r)
    await _ensure_project_index(r)
    await _ensure_pet_index(r)


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
        logger.info("Created index %s", ITEM_INDEX)


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
        logger.info("Created index %s", PROJECT_INDEX)


async def _ensure_pet_index(r: Redis) -> None:
    """
    Composite pet+owner index.

    Field design:
      full_text  — weight 10  — pre-joined "name species breed owner_first owner_last"
                                single field for fast broad queries
      name       — weight 5   — pet name alone for precise matches
      owner_*    — weight 3   — owner name fields
      species / breed — weight 2
      owner_email — weight 1  — lower relevance, but still searchable
      species_tag — TagField  — exact filter: @species_tag:{dog}
      owner_id    — TagField  — exact filter: @owner_id:{5}
    """
    try:
        await r.ft(PET_INDEX).info()
    except Exception:
        await r.ft(PET_INDEX).create_index(
            [
                # Boosted pre-joined text field — primary FT target
                TextField("$.full_text", as_name="full_text", weight=10.0),
                # Individual fields for precise / weighted matching
                TextField("$.name", as_name="name", weight=5.0),
                TextField("$.owner_first_name", as_name="owner_first_name", weight=3.0),
                TextField("$.owner_last_name", as_name="owner_last_name", weight=3.0),
                TextField("$.species", as_name="species", weight=2.0),
                TextField("$.breed", as_name="breed", weight=2.0),
                TextField("$.owner_email", as_name="owner_email", weight=1.0),
                # Tag fields for exact filters (not stemmed, no ranking)
                TagField("$.species", as_name="species_tag"),
                TagField("$.owner_id", as_name="owner_id"),
            ],
            definition=IndexDefinition(prefix=["pet:"], index_type=IndexType.JSON),
        )
        logger.info("Created composite index %s", PET_INDEX)


# ── Simple table write operations ──────────────────────────────────────────────


async def index_document(r: Redis, table: str, doc_id: str, data: dict) -> None:
    entry = _SIMPLE_TABLE_MAP.get(table)
    if entry is None:
        logger.warning("search.index_document: unknown table %r — skipped", table)
        return
    prefix, _ = entry
    await r.json().set(f"{prefix}:{doc_id}", "$", data)


async def delete_document(r: Redis, table: str, doc_id: str) -> None:
    entry = _SIMPLE_TABLE_MAP.get(table)
    if entry is None:
        return
    prefix, _ = entry
    await r.delete(f"{prefix}:{doc_id}")


# ── Composite pet document ─────────────────────────────────────────────────────


def build_pet_doc(pet_data: dict, owner_data: dict) -> dict:
    """
    Build the denormalized document that gets stored at pet:{id}.
    Called from both the async search service and the sync Celery task.
    """
    full_text = " ".join(
        filter(
            None,
            [
                pet_data.get("name"),
                pet_data.get("species"),
                pet_data.get("breed"),
                owner_data.get("first_name"),
                owner_data.get("last_name"),
            ],
        )
    )
    return {
        "pet_id": pet_data["id"],
        "name": pet_data.get("name", ""),
        "species": pet_data.get("species", ""),
        "breed": pet_data.get("breed") or "",
        "date_of_birth": str(pet_data["date_of_birth"]) if pet_data.get("date_of_birth") else None,
        "owner_id": str(owner_data["id"]),  # stored as string for TagField
        "owner_first_name": owner_data.get("first_name", ""),
        "owner_last_name": owner_data.get("last_name", ""),
        "owner_email": owner_data.get("email", ""),
        "owner_phone": owner_data.get("phone") or "",
        "full_text": full_text,
    }


async def upsert_pet_doc(r: Redis, pet_id: int, doc: dict) -> None:
    await r.json().set(f"pet:{pet_id}", "$", doc)


async def delete_pet_doc(r: Redis, pet_id: int) -> None:
    await r.delete(f"pet:{pet_id}")


# ── Search ─────────────────────────────────────────────────────────────────────


async def search_items(r: Redis, query: str, limit: int = 20) -> list[dict]:
    return await _search(r, ITEM_INDEX, query, limit)


async def search_projects(r: Redis, query: str, limit: int = 20) -> list[dict]:
    return await _search(r, PROJECT_INDEX, query, limit)


async def search_pets(
    r: Redis,
    *,
    q: str = "",
    species: str = "",
    owner_id: int | None = None,
    fuzzy: bool = True,
    highlight: bool = True,
    skip: int = 0,
    limit: int = 20,
) -> dict:
    """
    Search the composite pet+owner index.

    q        — free text (fuzzy when fuzzy=True, %-wrapped, Levenshtein distance 1)
    species  — exact species filter (tag)
    owner_id — exact owner filter (tag)
    highlight — wrap matched terms in <mark>…</mark>
    Returns:  {"results": [...], "total": N}
    """
    parts: list[str] = []

    if q:
        if fuzzy:
            # RediSearch fuzzy: %term% = Levenshtein distance 1
            # Use full_text as the primary target for speed, then fan out
            fuzzy_terms = " ".join(f"%{t}%" for t in q.split())
            parts.append(fuzzy_terms)
        else:
            parts.append(q)

    if species:
        # Tag field exact match — case-insensitive in Redis
        parts.append(f"@species_tag:{{{species}}}")

    if owner_id is not None:
        parts.append(f"@owner_id:{{{owner_id}}}")

    query_str = " ".join(parts) if parts else "*"

    try:
        q_obj = Query(query_str).paging(skip, limit).with_scores()

        if highlight:
            q_obj = q_obj.highlight(
                fields=["name", "breed", "species", "owner_first_name", "owner_last_name"],
                tags=("<mark>", "</mark>"),
            )

        results = await r.ft(PET_INDEX).search(q_obj)
        docs = []
        for doc in results.docs:
            raw = json.loads(doc.json) if hasattr(doc, "json") else {}
            raw["_score"] = getattr(doc, "score", None)
            docs.append(raw)

        return {"results": docs, "total": results.total}

    except Exception:
        logger.exception("pet search error — query=%r", query_str)
        return {"results": [], "total": 0}


async def _search(r: Redis, index: str, query: str, limit: int) -> list[dict]:
    try:
        results = await r.ft(index).search(Query(query).paging(0, limit))
        return [json.loads(doc.json) for doc in results.docs]
    except Exception:
        logger.exception("search error on %s query=%r", index, query)
        return []
