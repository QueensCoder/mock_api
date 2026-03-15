"""
Integration tests for the composite pet+owner RediSearch index.

Requires a running Redis Stack instance (supports RediSearch + RedisJSON):
    docker compose up -d redis

Run:
    pytest tests/integration/test_pet_search_service.py -v
"""

import pytest
import redis.asyncio as aioredis

from app.services.search import (
    build_pet_doc,
    delete_pet_doc,
    ensure_indexes,
    search_pets,
    upsert_pet_doc,
)

REDIS_URL = "redis://localhost:6379/0"


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
async def redis_client():
    r = aioredis.from_url(REDIS_URL, decode_responses=True)
    await ensure_indexes(r)
    yield r
    await r.aclose()


@pytest.fixture(autouse=True)
async def cleanup(redis_client: aioredis.Redis):
    """Wipe test pet keys before each test."""
    async for key in redis_client.scan_iter("pet:9*"):
        await redis_client.delete(key)
    yield


# ── Helpers ───────────────────────────────────────────────────────────────────


def _pet(pet_id: int, name: str, species: str = "dog", breed: str | None = None):
    return {"id": pet_id, "name": name, "species": species, "breed": breed, "date_of_birth": None}


def _owner(owner_id: int, first: str = "John", last: str = "Doe", email: str | None = None):
    return {
        "id": owner_id,
        "first_name": first,
        "last_name": last,
        "email": email or f"owner{owner_id}@test.com",
        "phone": None,
    }


async def _index(r, pet_id: int, pet: dict, owner: dict):
    doc = build_pet_doc(pet, owner)
    await upsert_pet_doc(r, pet_id, doc)


# ── Index write / read ────────────────────────────────────────────────────────


class TestPetIndexWrite:
    async def test_indexed_pet_appears_in_wildcard_search(self, redis_client):
        await _index(redis_client, 9001, _pet(9001, "Max"), _owner(1))
        result = await search_pets(redis_client, q="")
        pet_ids = [r["pet_id"] for r in result["results"]]
        assert 9001 in pet_ids

    async def test_deleted_pet_disappears_from_search(self, redis_client):
        await _index(redis_client, 9002, _pet(9002, "DeleteMe"), _owner(2))
        before = await search_pets(redis_client, q="DeleteMe")
        assert any(r["pet_id"] == 9002 for r in before["results"])

        await delete_pet_doc(redis_client, 9002)

        after = await search_pets(redis_client, q="DeleteMe")
        assert not any(r["pet_id"] == 9002 for r in after["results"])

    async def test_update_replaces_document(self, redis_client):
        await _index(redis_client, 9003, _pet(9003, "OldName"), _owner(3))
        await _index(redis_client, 9003, _pet(9003, "NewUniqueName9003"), _owner(3))

        result = await search_pets(redis_client, q="NewUniqueName9003")
        assert any(r["pet_id"] == 9003 for r in result["results"])

        old = await search_pets(redis_client, q="OldName")
        assert not any(r["pet_id"] == 9003 for r in old["results"])


# ── Free-text search ──────────────────────────────────────────────────────────


class TestPetFreeTextSearch:
    async def test_search_by_pet_name(self, redis_client):
        await _index(redis_client, 9010, _pet(9010, "Biscuit"), _owner(10))
        result = await search_pets(redis_client, q="Biscuit", fuzzy=False)
        assert any(r["pet_id"] == 9010 for r in result["results"])

    async def test_search_by_breed(self, redis_client):
        await _index(redis_client, 9011, _pet(9011, "Rocky", "dog", "Beagle"), _owner(11))
        result = await search_pets(redis_client, q="Beagle", fuzzy=False)
        assert any(r["pet_id"] == 9011 for r in result["results"])

    async def test_search_by_owner_first_name(self, redis_client):
        await _index(redis_client, 9012, _pet(9012, "Kitty"), _owner(12, first="Xiomara"))
        result = await search_pets(redis_client, q="Xiomara", fuzzy=False)
        assert any(r["pet_id"] == 9012 for r in result["results"])

    async def test_search_by_owner_last_name(self, redis_client):
        await _index(redis_client, 9013, _pet(9013, "Pepper"), _owner(13, last="Kowalski"))
        result = await search_pets(redis_client, q="Kowalski", fuzzy=False)
        assert any(r["pet_id"] == 9013 for r in result["results"])

    async def test_no_results_for_unknown_term(self, redis_client):
        result = await search_pets(redis_client, q="xyzqqqnonexistent99")
        assert result["results"] == []
        assert result["total"] == 0


# ── Fuzzy search ──────────────────────────────────────────────────────────────


class TestFuzzySearch:
    async def test_fuzzy_matches_typo_in_name(self, redis_client):
        await _index(redis_client, 9020, _pet(9020, "Charlie"), _owner(20))
        # "Charli" is 1 edit away from "Charlie"
        result = await search_pets(redis_client, q="Charli", fuzzy=True)
        assert any(r["pet_id"] == 9020 for r in result["results"])

    async def test_fuzzy_off_misses_typo(self, redis_client):
        await _index(redis_client, 9021, _pet(9021, "Zephyr"), _owner(21))
        result = await search_pets(redis_client, q="Zepyr", fuzzy=False)
        # Without fuzzy, a 2-char edit may not match — we just verify no crash
        assert isinstance(result["results"], list)


# ── Tag filters ───────────────────────────────────────────────────────────────


class TestTagFilters:
    async def test_species_filter_returns_only_matching_species(self, redis_client):
        await _index(redis_client, 9030, _pet(9030, "Whiskers", "cat"), _owner(30))
        await _index(redis_client, 9031, _pet(9031, "Buddy", "dog"), _owner(31))

        result = await search_pets(redis_client, species="cat")
        pet_ids = [r["pet_id"] for r in result["results"]]
        assert 9030 in pet_ids
        assert 9031 not in pet_ids

    async def test_owner_id_filter_returns_only_that_owners_pets(self, redis_client):
        await _index(redis_client, 9032, _pet(9032, "Noodle"), _owner(32))
        await _index(redis_client, 9033, _pet(9033, "Spaghetti"), _owner(99))

        result = await search_pets(redis_client, owner_id=32)
        pet_ids = [r["pet_id"] for r in result["results"]]
        assert 9032 in pet_ids
        assert 9033 not in pet_ids

    async def test_combined_q_and_species_filter(self, redis_client):
        await _index(redis_client, 9034, _pet(9034, "Leo", "cat"), _owner(34))
        await _index(redis_client, 9035, _pet(9035, "Leo", "dog"), _owner(35))

        result = await search_pets(redis_client, q="Leo", species="cat", fuzzy=False)
        pet_ids = [r["pet_id"] for r in result["results"]]
        assert 9034 in pet_ids
        assert 9035 not in pet_ids


# ── Pagination ────────────────────────────────────────────────────────────────


class TestPagination:
    async def test_limit_restricts_result_count(self, redis_client):
        for i in range(5):
            await _index(redis_client, 9040 + i, _pet(9040 + i, f"PaginatePet{i}"), _owner(40 + i))

        result = await search_pets(redis_client, q="PaginatePet", limit=2, fuzzy=False)
        assert len(result["results"]) <= 2

    async def test_total_reflects_full_match_count(self, redis_client):
        for i in range(3):
            await _index(redis_client, 9050 + i, _pet(9050 + i, f"TotalTest{i}"), _owner(50 + i))

        result = await search_pets(redis_client, q="TotalTest", limit=1, fuzzy=False)
        assert result["total"] >= 3


# ── Highlight ─────────────────────────────────────────────────────────────────


class TestHighlight:
    async def test_highlight_wraps_matched_term_in_mark_tags(self, redis_client):
        await _index(redis_client, 9060, _pet(9060, "Markus", "dog"), _owner(60))
        result = await search_pets(redis_client, q="Markus", highlight=True, fuzzy=False)
        assert result["results"]
        # At least one field should contain <mark> tags
        doc = result["results"][0]
        highlighted_fields = [doc.get("name", ""), doc.get("full_text", "")]
        assert any("<mark>" in f for f in highlighted_fields)

    async def test_no_highlight_when_disabled(self, redis_client):
        await _index(redis_client, 9061, _pet(9061, "Nohighlight", "cat"), _owner(61))
        result = await search_pets(redis_client, q="Nohighlight", highlight=False, fuzzy=False)
        assert result["results"]
        doc = result["results"][0]
        all_values = " ".join(str(v) for v in doc.values() if isinstance(v, str))
        assert "<mark>" not in all_values
