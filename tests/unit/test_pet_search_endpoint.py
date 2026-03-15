"""
Unit tests for GET /api/v1/search/pets.

The Redis dependency and search_pets() function are mocked so no
real Redis or Postgres is required.
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.redis import get_redis

BASE_URL = "http://test"

# One sample document returned by the mocked search_pets()
SAMPLE_DOC = {
    "pet_id": 1,
    "name": "Max",
    "species": "dog",
    "breed": "Labrador",
    "date_of_birth": "2020-03-15",
    "owner_id": "5",
    "owner_first_name": "John",
    "owner_last_name": "Doe",
    "owner_email": "john@example.com",
    "owner_phone": "555-1234",
    "full_text": "Max dog Labrador John Doe",
    "_score": 1.0,
}


@pytest.fixture
def mock_redis():
    return AsyncMock()


@pytest.fixture(autouse=True)
def override_redis(mock_redis):
    app.dependency_overrides[get_redis] = lambda: mock_redis
    yield
    app.dependency_overrides.pop(get_redis, None)


@pytest.fixture
def search_result_one():
    return {"results": [SAMPLE_DOC], "total": 1}


@pytest.fixture
def search_result_empty():
    return {"results": [], "total": 0}


async def _get(path: str, **params):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        return await client.get(path, params=params)


class TestPetSearchEndpoint:
    async def test_returns_200_with_results(self, search_result_one):
        with patch(
            "app.api.v1.endpoints.pet_search.search_pets",
            new=AsyncMock(return_value=search_result_one),
        ):
            resp = await _get("/api/v1/search/pets", q="Max")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["results"][0]["pet_id"] == 1

    async def test_empty_q_returns_all(self, search_result_one):
        with patch(
            "app.api.v1.endpoints.pet_search.search_pets",
            new=AsyncMock(return_value=search_result_one),
        ):
            resp = await _get("/api/v1/search/pets")

        assert resp.status_code == 200

    async def test_no_results_returns_empty_list(self, search_result_empty):
        with patch(
            "app.api.v1.endpoints.pet_search.search_pets",
            new=AsyncMock(return_value=search_result_empty),
        ):
            resp = await _get("/api/v1/search/pets", q="zzzunknown")

        assert resp.status_code == 200
        assert resp.json()["results"] == []
        assert resp.json()["total"] == 0

    async def test_species_filter_forwarded(self, search_result_empty):
        mock = AsyncMock(return_value=search_result_empty)
        with patch("app.api.v1.endpoints.pet_search.search_pets", new=mock):
            await _get("/api/v1/search/pets", q="lab", species="dog")

        _, kwargs = mock.call_args
        assert kwargs["species"] == "dog"

    async def test_owner_id_filter_forwarded(self, search_result_empty):
        mock = AsyncMock(return_value=search_result_empty)
        with patch("app.api.v1.endpoints.pet_search.search_pets", new=mock):
            await _get("/api/v1/search/pets", owner_id=5)

        _, kwargs = mock.call_args
        assert kwargs["owner_id"] == 5

    async def test_fuzzy_defaults_to_true(self, search_result_empty):
        mock = AsyncMock(return_value=search_result_empty)
        with patch("app.api.v1.endpoints.pet_search.search_pets", new=mock):
            await _get("/api/v1/search/pets", q="max")

        _, kwargs = mock.call_args
        assert kwargs["fuzzy"] is True

    async def test_fuzzy_can_be_disabled(self, search_result_empty):
        mock = AsyncMock(return_value=search_result_empty)
        with patch("app.api.v1.endpoints.pet_search.search_pets", new=mock):
            await _get("/api/v1/search/pets", q="max", fuzzy=False)

        _, kwargs = mock.call_args
        assert kwargs["fuzzy"] is False

    async def test_highlight_defaults_to_true(self, search_result_empty):
        mock = AsyncMock(return_value=search_result_empty)
        with patch("app.api.v1.endpoints.pet_search.search_pets", new=mock):
            await _get("/api/v1/search/pets", q="max")

        _, kwargs = mock.call_args
        assert kwargs["highlight"] is True

    async def test_pagination_params_forwarded(self, search_result_empty):
        mock = AsyncMock(return_value=search_result_empty)
        with patch("app.api.v1.endpoints.pet_search.search_pets", new=mock):
            await _get("/api/v1/search/pets", skip=10, limit=5)

        _, kwargs = mock.call_args
        assert kwargs["skip"] == 10
        assert kwargs["limit"] == 5

    async def test_limit_too_large_returns_422(self):
        resp = await _get("/api/v1/search/pets", limit=200)
        assert resp.status_code == 422

    async def test_skip_negative_returns_422(self):
        resp = await _get("/api/v1/search/pets", skip=-1)
        assert resp.status_code == 422
