"""
GET /api/v1/search/pets

Queries the composite RediSearch index that contains denormalized
pet + owner data in a single document per pet.

Features:
  - Full-text BM25 ranking across name, breed, species, owner name
  - Fuzzy matching for typo tolerance  (fuzzy=true, default on)
  - HTML highlighted snippets  (<mark>term</mark>) in matched fields
  - Exact filters: species, owner_id
  - Pagination: skip / limit

Examples:
  /api/v1/search/pets?q=max
  /api/v1/search/pets?q=labr&species=dog
  /api/v1/search/pets?owner_id=5
  /api/v1/search/pets?q=johnn&fuzzy=true     ← "johnn" matches "john"
  /api/v1/search/pets?q=max&highlight=false
"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from redis.asyncio import Redis

from app.services.redis import get_redis
from app.services.search import search_pets

router = APIRouter()


class PetSearchResult(BaseModel):
    pet_id: int | None = None
    name: str | None = None
    species: str | None = None
    breed: str | None = None
    date_of_birth: str | None = None
    owner_id: str | None = None
    owner_first_name: str | None = None
    owner_last_name: str | None = None
    owner_email: str | None = None
    owner_phone: str | None = None
    _score: float | None = None


class PetSearchResponse(BaseModel):
    results: list[dict]
    total: int


@router.get("/pets", response_model=PetSearchResponse, summary="Search pets and owners")
async def search_pets_endpoint(
    q: str = Query(default="", description="Free-text query (name, breed, species, owner name)"),
    species: str = Query(default="", description="Exact species filter — e.g. dog, cat"),
    owner_id: int | None = Query(default=None, description="Filter by owner ID"),
    fuzzy: bool = Query(default=True, description="Enable fuzzy matching for typo tolerance"),
    highlight: bool = Query(default=True, description="Wrap matched terms in <mark> tags"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    redis: Redis = Depends(get_redis),
) -> PetSearchResponse:
    result = await search_pets(
        redis,
        q=q,
        species=species,
        owner_id=owner_id,
        fuzzy=fuzzy,
        highlight=highlight,
        skip=skip,
        limit=limit,
    )
    return PetSearchResponse(**result)
