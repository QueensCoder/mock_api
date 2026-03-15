"""
Unit tests for GET/POST/PATCH/DELETE /api/v1/visits.

All DB calls are mocked — no real Postgres or partition setup required.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db
from app.main import app

BASE = "http://test"
NOW = "2026-06-15T10:00:00+00:00"


@pytest.fixture(autouse=True)
def mock_db():
    session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: session
    yield session
    app.dependency_overrides.pop(get_db, None)


def make_visit(visit_id: int = 1, pet_id: int = 1, owner_id: int = 1, status: str = "scheduled"):
    m = MagicMock()
    m.id = visit_id
    m.pet_id = pet_id
    m.owner_id = owner_id
    m.visited_at = datetime(2026, 6, 15, 10, tzinfo=UTC)
    m.reason = "Annual checkup"
    m.notes = None
    m.status = status
    m.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    m.updated_at = datetime(2026, 1, 1, tzinfo=UTC)
    m.deleted_at = None
    return m


async def _get(path: str, **params):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        return await c.get(path, params=params)


async def _post(path: str, json: dict):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        return await c.post(path, json=json)


async def _patch(path: str, json: dict):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        return await c.patch(path, json=json)


async def _delete(path: str):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        return await c.delete(path)


class TestVisitList:
    async def test_list_returns_200_empty(self):
        with patch("app.repositories.visit.visit_repo.list", new=AsyncMock(return_value=[])):
            resp = await _get("/api/v1/visits")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_returns_multiple(self):
        visits = [make_visit(i) for i in range(1, 4)]
        with patch("app.repositories.visit.visit_repo.list", new=AsyncMock(return_value=visits)):
            resp = await _get("/api/v1/visits")
        assert len(resp.json()) == 3

    async def test_limit_too_large_returns_422(self):
        resp = await _get("/api/v1/visits", limit=200)
        assert resp.status_code == 422

    async def test_skip_negative_returns_422(self):
        resp = await _get("/api/v1/visits", skip=-1)
        assert resp.status_code == 422


class TestVisitCreate:
    async def test_create_returns_201(self):
        visit = make_visit()
        with patch("app.repositories.visit.visit_repo.create", new=AsyncMock(return_value=visit)):
            resp = await _post(
                "/api/v1/visits",
                {"pet_id": 1, "owner_id": 1, "visited_at": NOW},
            )
        assert resp.status_code == 201
        assert resp.json()["pet_id"] == 1

    async def test_create_with_all_fields(self):
        visit = make_visit(status="completed")
        visit.reason = "Vaccination"
        visit.status = "completed"
        with patch("app.repositories.visit.visit_repo.create", new=AsyncMock(return_value=visit)):
            resp = await _post(
                "/api/v1/visits",
                {
                    "pet_id": 1,
                    "owner_id": 1,
                    "visited_at": NOW,
                    "reason": "Vaccination",
                    "status": "completed",
                },
            )
        assert resp.status_code == 201

    async def test_create_missing_visited_at_returns_422(self):
        resp = await _post("/api/v1/visits", {"pet_id": 1, "owner_id": 1})
        assert resp.status_code == 422

    async def test_create_missing_pet_id_returns_422(self):
        resp = await _post("/api/v1/visits", {"owner_id": 1, "visited_at": NOW})
        assert resp.status_code == 422

    async def test_create_invalid_status_returns_422(self):
        resp = await _post(
            "/api/v1/visits",
            {"pet_id": 1, "owner_id": 1, "visited_at": NOW, "status": "unknown_status"},
        )
        assert resp.status_code == 422

    async def test_all_valid_statuses_accepted(self):
        for s in ("scheduled", "completed", "cancelled", "no_show"):
            visit = make_visit(status=s)
            visit.status = s
            with patch(
                "app.repositories.visit.visit_repo.create", new=AsyncMock(return_value=visit)
            ):
                resp = await _post(
                    "/api/v1/visits",
                    {"pet_id": 1, "owner_id": 1, "visited_at": NOW, "status": s},
                )
            assert resp.status_code == 201, f"failed for status={s}"


class TestVisitGet:
    async def test_get_existing_returns_200(self):
        visit = make_visit(5)
        with patch(
            "app.repositories.visit.visit_repo.get_or_404", new=AsyncMock(return_value=visit)
        ):
            resp = await _get("/api/v1/visits/5")
        assert resp.status_code == 200
        assert resp.json()["id"] == 5

    async def test_get_includes_all_fields(self):
        visit = make_visit(2, pet_id=10, owner_id=20, status="completed")
        with patch(
            "app.repositories.visit.visit_repo.get_or_404", new=AsyncMock(return_value=visit)
        ):
            resp = await _get("/api/v1/visits/2")
        body = resp.json()
        assert body["pet_id"] == 10
        assert body["owner_id"] == 20
        assert body["status"] == "completed"


class TestVisitUpdate:
    async def test_update_status_returns_200(self):
        original = make_visit(3)
        updated = make_visit(3, status="completed")
        updated.status = "completed"
        with (
            patch(
                "app.repositories.visit.visit_repo.get_or_404",
                new=AsyncMock(return_value=original),
            ),
            patch(
                "app.repositories.visit.visit_repo.update",
                new=AsyncMock(return_value=updated),
            ),
        ):
            resp = await _patch("/api/v1/visits/3", {"status": "completed"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    async def test_update_notes_returns_200(self):
        original = make_visit(4)
        updated = make_visit(4)
        updated.notes = "Follow up required"
        with (
            patch(
                "app.repositories.visit.visit_repo.get_or_404",
                new=AsyncMock(return_value=original),
            ),
            patch(
                "app.repositories.visit.visit_repo.update",
                new=AsyncMock(return_value=updated),
            ),
        ):
            resp = await _patch("/api/v1/visits/4", {"notes": "Follow up required"})
        assert resp.status_code == 200

    async def test_update_invalid_status_returns_422(self):
        resp = await _patch("/api/v1/visits/1", {"status": "bad_value"})
        assert resp.status_code == 422


class TestVisitDelete:
    async def test_delete_returns_204(self):
        with patch(
            "app.repositories.visit.visit_repo.soft_delete", new=AsyncMock(return_value=None)
        ):
            resp = await _delete("/api/v1/visits/1")
        assert resp.status_code == 204

    async def test_delete_calls_soft_delete_with_correct_id(self):
        mock = AsyncMock(return_value=None)
        with patch("app.repositories.visit.visit_repo.soft_delete", new=mock):
            await _delete("/api/v1/visits/99")
        mock.assert_called_once()
        _, kwargs = mock.call_args
        assert kwargs["id"] == 99
