"""
Unit tests for clinic CRUD endpoints.

Covers create, read, update, and delete for:
  - owners   (GET/POST/GET{id}/PATCH/DELETE)
  - pets     (GET/POST/GET{id}/PATCH/DELETE)
  - patients (GET/POST/GET{id}/PATCH/DELETE)
  - medicines (GET/POST/GET{id}/PATCH/DELETE)

DB and repositories are mocked — no real Postgres required.
"""

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db
from app.main import app

BASE = "http://test"


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def mock_db():
    fake_session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: fake_session
    yield fake_session
    app.dependency_overrides.pop(get_db, None)


def _ts():
    return datetime(2026, 1, 1, tzinfo=UTC).isoformat()


def make_owner(owner_id: int = 1, **kwargs):
    m = MagicMock()
    m.id = owner_id
    m.first_name = kwargs.get("first_name", "John")
    m.last_name = kwargs.get("last_name", "Doe")
    m.email = kwargs.get("email", f"owner{owner_id}@test.com")
    m.phone = kwargs.get("phone", None)
    m.created_at = _ts()
    m.updated_at = _ts()
    m.deleted_at = None
    m.created_by = None
    m.updated_by = None
    m.deleted_by = None
    return m


def make_pet(pet_id: int = 1, owner_id: int = 1, **kwargs):
    m = MagicMock()
    m.id = pet_id
    m.owner_id = owner_id
    m.name = kwargs.get("name", "Max")
    m.species = kwargs.get("species", "dog")
    m.breed = kwargs.get("breed", None)
    m.date_of_birth = kwargs.get("date_of_birth", None)
    m.created_at = _ts()
    m.updated_at = _ts()
    m.deleted_at = None
    m.created_by = None
    m.updated_by = None
    m.deleted_by = None
    return m


def make_medicine(med_id: int = 1, **kwargs):
    m = MagicMock()
    m.id = med_id
    m.name = kwargs.get("name", "Amoxicillin")
    m.description = kwargs.get("description", None)
    m.dosage = kwargs.get("dosage", "10mg")
    m.unit = kwargs.get("unit", "tablet")
    m.created_at = _ts()
    m.updated_at = _ts()
    m.deleted_at = None
    m.created_by = None
    m.updated_by = None
    m.deleted_by = None
    return m


def make_patient(patient_id: int = 1, pet_id: int = 1, **kwargs):
    m = MagicMock()
    m.id = patient_id
    m.pet_id = pet_id
    m.condition = kwargs.get("condition", "Flu")
    m.notes = kwargs.get("notes", None)
    m.visited_at = _ts()
    m.created_at = _ts()
    m.updated_at = _ts()
    m.deleted_at = None
    m.created_by = None
    m.updated_by = None
    m.deleted_by = None
    return m


async def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url=BASE)


# ── Owner endpoints ───────────────────────────────────────────────────────────


class TestOwnerEndpoints:
    async def test_list_owners_returns_200(self):
        with patch("app.repositories.owner.owner_repo.list", new=AsyncMock(return_value=[])):
            async with await _client() as c:
                resp = await c.get("/api/v1/owners")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_create_owner_returns_201(self):
        owner = make_owner(first_name="Alice", last_name="Smith", email="alice@test.com")
        with patch("app.repositories.owner.owner_repo.create", new=AsyncMock(return_value=owner)):
            async with await _client() as c:
                resp = await c.post(
                    "/api/v1/owners",
                    json={"first_name": "Alice", "last_name": "Smith", "email": "alice@test.com"},
                )
        assert resp.status_code == 201
        assert resp.json()["first_name"] == "Alice"

    async def test_create_owner_invalid_email_returns_422(self):
        async with await _client() as c:
            resp = await c.post(
                "/api/v1/owners",
                json={"first_name": "Bob", "last_name": "Jones", "email": "not-an-email"},
            )
        assert resp.status_code == 422

    async def test_get_owner_returns_200(self):
        owner = make_owner(1)
        with patch(
            "app.repositories.owner.owner_repo.get_or_404", new=AsyncMock(return_value=owner)
        ):
            async with await _client() as c:
                resp = await c.get("/api/v1/owners/1")
        assert resp.status_code == 200
        assert resp.json()["id"] == 1

    async def test_update_owner_returns_200(self):
        owner = make_owner(1, last_name="Updated")
        with (
            patch(
                "app.repositories.owner.owner_repo.get_or_404", new=AsyncMock(return_value=owner)
            ),
            patch("app.repositories.owner.owner_repo.update", new=AsyncMock(return_value=owner)),
        ):
            async with await _client() as c:
                resp = await c.patch("/api/v1/owners/1", json={"last_name": "Updated"})
        assert resp.status_code == 200
        assert resp.json()["last_name"] == "Updated"

    async def test_delete_owner_returns_204(self):
        with patch(
            "app.repositories.owner.owner_repo.soft_delete", new=AsyncMock(return_value=None)
        ):
            async with await _client() as c:
                resp = await c.delete("/api/v1/owners/1")
        assert resp.status_code == 204

    async def test_list_owners_returns_multiple(self):
        owners = [make_owner(i, email=f"o{i}@test.com") for i in range(1, 4)]
        with patch("app.repositories.owner.owner_repo.list", new=AsyncMock(return_value=owners)):
            async with await _client() as c:
                resp = await c.get("/api/v1/owners")
        assert len(resp.json()) == 3


# ── Pet endpoints ─────────────────────────────────────────────────────────────


class TestPetEndpoints:
    async def test_list_pets_returns_200(self):
        with patch("app.repositories.pet.pet_repo.list", new=AsyncMock(return_value=[])):
            async with await _client() as c:
                resp = await c.get("/api/v1/pets")
        assert resp.status_code == 200

    async def test_create_pet_returns_201(self):
        pet = make_pet(pet_id=10, owner_id=1, name="Buddy", species="dog")
        with patch("app.repositories.pet.pet_repo.create", new=AsyncMock(return_value=pet)):
            async with await _client() as c:
                resp = await c.post(
                    "/api/v1/pets",
                    json={"owner_id": 1, "name": "Buddy", "species": "dog"},
                )
        assert resp.status_code == 201
        assert resp.json()["name"] == "Buddy"

    async def test_create_pet_missing_required_field_returns_422(self):
        async with await _client() as c:
            # species is required
            resp = await c.post("/api/v1/pets", json={"owner_id": 1, "name": "NoSpecies"})
        assert resp.status_code == 422

    async def test_get_pet_returns_200(self):
        pet = make_pet(pet_id=5)
        with patch("app.repositories.pet.pet_repo.get_or_404", new=AsyncMock(return_value=pet)):
            async with await _client() as c:
                resp = await c.get("/api/v1/pets/5")
        assert resp.status_code == 200
        assert resp.json()["id"] == 5

    async def test_update_pet_breed_returns_200(self):
        pet = make_pet(pet_id=5, breed="Poodle")
        with (
            patch("app.repositories.pet.pet_repo.get_or_404", new=AsyncMock(return_value=pet)),
            patch("app.repositories.pet.pet_repo.update", new=AsyncMock(return_value=pet)),
        ):
            async with await _client() as c:
                resp = await c.patch("/api/v1/pets/5", json={"breed": "Poodle"})
        assert resp.status_code == 200
        assert resp.json()["breed"] == "Poodle"

    async def test_delete_pet_returns_204(self):
        with patch("app.repositories.pet.pet_repo.soft_delete", new=AsyncMock(return_value=None)):
            async with await _client() as c:
                resp = await c.delete("/api/v1/pets/5")
        assert resp.status_code == 204

    async def test_create_pet_with_date_of_birth(self):
        pet = make_pet(pet_id=11, date_of_birth=date(2020, 5, 10))
        with patch("app.repositories.pet.pet_repo.create", new=AsyncMock(return_value=pet)):
            async with await _client() as c:
                resp = await c.post(
                    "/api/v1/pets",
                    json={
                        "owner_id": 1,
                        "name": "Daisy",
                        "species": "cat",
                        "date_of_birth": "2020-05-10",
                    },
                )
        assert resp.status_code == 201


# ── Medicine endpoints ────────────────────────────────────────────────────────


class TestMedicineEndpoints:
    async def test_list_medicines_returns_200(self):
        with patch("app.repositories.medicine.medicine_repo.list", new=AsyncMock(return_value=[])):
            async with await _client() as c:
                resp = await c.get("/api/v1/medicines")
        assert resp.status_code == 200

    async def test_create_medicine_returns_201(self):
        med = make_medicine(name="Penicillin", dosage="500mg")
        with patch(
            "app.repositories.medicine.medicine_repo.create", new=AsyncMock(return_value=med)
        ):
            async with await _client() as c:
                resp = await c.post(
                    "/api/v1/medicines", json={"name": "Penicillin", "dosage": "500mg"}
                )
        assert resp.status_code == 201
        assert resp.json()["name"] == "Penicillin"

    async def test_create_medicine_missing_name_returns_422(self):
        async with await _client() as c:
            resp = await c.post("/api/v1/medicines", json={"dosage": "500mg"})
        assert resp.status_code == 422

    async def test_get_medicine_returns_200(self):
        med = make_medicine(3)
        with patch(
            "app.repositories.medicine.medicine_repo.get_or_404", new=AsyncMock(return_value=med)
        ):
            async with await _client() as c:
                resp = await c.get("/api/v1/medicines/3")
        assert resp.status_code == 200
        assert resp.json()["id"] == 3

    async def test_update_medicine_description_returns_200(self):
        med = make_medicine(3, description="Updated description")
        with (
            patch(
                "app.repositories.medicine.medicine_repo.get_or_404",
                new=AsyncMock(return_value=med),
            ),
            patch(
                "app.repositories.medicine.medicine_repo.update", new=AsyncMock(return_value=med)
            ),
        ):
            async with await _client() as c:
                resp = await c.patch(
                    "/api/v1/medicines/3", json={"description": "Updated description"}
                )
        assert resp.status_code == 200

    async def test_delete_medicine_returns_204(self):
        with patch(
            "app.repositories.medicine.medicine_repo.soft_delete", new=AsyncMock(return_value=None)
        ):
            async with await _client() as c:
                resp = await c.delete("/api/v1/medicines/3")
        assert resp.status_code == 204


# ── Patient endpoints ─────────────────────────────────────────────────────────


class TestPatientEndpoints:
    async def test_list_patients_returns_200(self):
        with patch("app.repositories.patient.patient_repo.list", new=AsyncMock(return_value=[])):
            async with await _client() as c:
                resp = await c.get("/api/v1/patients")
        assert resp.status_code == 200

    async def test_create_patient_returns_201(self):
        patient = make_patient(patient_id=1, pet_id=2, condition="Arthritis")
        with patch(
            "app.repositories.patient.patient_repo.create", new=AsyncMock(return_value=patient)
        ):
            async with await _client() as c:
                resp = await c.post(
                    "/api/v1/patients",
                    json={
                        "pet_id": 2,
                        "condition": "Arthritis",
                        "visited_at": "2026-01-01T00:00:00+00:00",
                    },
                )
        assert resp.status_code == 201
        assert resp.json()["condition"] == "Arthritis"

    async def test_create_patient_missing_visited_at_returns_422(self):
        async with await _client() as c:
            resp = await c.post("/api/v1/patients", json={"pet_id": 1, "condition": "Cold"})
        assert resp.status_code == 422

    async def test_get_patient_returns_200(self):
        patient = make_patient(7, 3)
        with patch(
            "app.repositories.patient.patient_repo.get_or_404", new=AsyncMock(return_value=patient)
        ):
            async with await _client() as c:
                resp = await c.get("/api/v1/patients/7")
        assert resp.status_code == 200
        assert resp.json()["id"] == 7

    async def test_update_patient_notes_returns_200(self):
        patient = make_patient(7, 3, notes="Follow up in 2 weeks")
        with (
            patch(
                "app.repositories.patient.patient_repo.get_or_404",
                new=AsyncMock(return_value=patient),
            ),
            patch(
                "app.repositories.patient.patient_repo.update", new=AsyncMock(return_value=patient)
            ),
        ):
            async with await _client() as c:
                resp = await c.patch("/api/v1/patients/7", json={"notes": "Follow up in 2 weeks"})
        assert resp.status_code == 200
        assert resp.json()["notes"] == "Follow up in 2 weeks"

    async def test_delete_patient_returns_204(self):
        with patch(
            "app.repositories.patient.patient_repo.soft_delete", new=AsyncMock(return_value=None)
        ):
            async with await _client() as c:
                resp = await c.delete("/api/v1/patients/7")
        assert resp.status_code == 204
