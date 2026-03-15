"""
Unit tests for worker/tasks/composite_index.py and stream_consumer routing.

No real Redis or Postgres required — all external calls are mocked.
"""

from unittest.mock import patch

import pytest

from app.services.search import build_pet_doc
from worker.stream_consumer import handle_event

# ── build_pet_doc ─────────────────────────────────────────────────────────────


class TestBuildPetDoc:
    def test_full_document_structure(self):
        pet = {
            "id": 1,
            "name": "Max",
            "species": "dog",
            "breed": "Labrador",
            "date_of_birth": "2020-03-15",
        }
        owner = {
            "id": 5,
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
            "phone": "555-1234",
        }

        doc = build_pet_doc(pet, owner)

        assert doc["pet_id"] == 1
        assert doc["name"] == "Max"
        assert doc["species"] == "dog"
        assert doc["breed"] == "Labrador"
        assert doc["owner_id"] == "5"  # stored as string for TagField
        assert doc["owner_first_name"] == "John"
        assert doc["owner_last_name"] == "Doe"
        assert doc["owner_email"] == "john@example.com"
        assert doc["owner_phone"] == "555-1234"

    def test_full_text_joins_name_species_breed_and_owner(self):
        pet = {
            "id": 1,
            "name": "Bella",
            "species": "cat",
            "breed": "Siamese",
            "date_of_birth": None,
        }
        owner = {
            "id": 2,
            "first_name": "Alice",
            "last_name": "Smith",
            "email": "a@b.com",
            "phone": None,
        }

        doc = build_pet_doc(pet, owner)

        assert "Bella" in doc["full_text"]
        assert "cat" in doc["full_text"]
        assert "Siamese" in doc["full_text"]
        assert "Alice" in doc["full_text"]
        assert "Smith" in doc["full_text"]

    def test_none_breed_becomes_empty_string(self):
        pet = {"id": 2, "name": "Luna", "species": "rabbit", "breed": None, "date_of_birth": None}
        owner = {
            "id": 3,
            "first_name": "Bob",
            "last_name": "Jones",
            "email": "b@c.com",
            "phone": None,
        }

        doc = build_pet_doc(pet, owner)

        assert doc["breed"] == ""

    def test_missing_date_of_birth_is_none(self):
        pet = {"id": 3, "name": "Rex", "species": "dog", "breed": "Poodle", "date_of_birth": None}
        owner = {"id": 1, "first_name": "Eve", "last_name": "Lee", "email": "e@f.com", "phone": ""}

        doc = build_pet_doc(pet, owner)

        assert doc["date_of_birth"] is None

    def test_date_of_birth_serialised_as_string(self):
        from datetime import date

        pet = {
            "id": 4,
            "name": "Coco",
            "species": "dog",
            "breed": None,
            "date_of_birth": date(2021, 6, 1),
        }
        owner = {"id": 1, "first_name": "Dan", "last_name": "Ho", "email": "d@h.com", "phone": None}

        doc = build_pet_doc(pet, owner)

        assert doc["date_of_birth"] == "2021-06-01"

    def test_full_text_skips_none_fields(self):
        """None values must not appear as the string 'None' in full_text."""
        pet = {"id": 5, "name": "Spot", "species": "dog", "breed": None, "date_of_birth": None}
        owner = {
            "id": 1,
            "first_name": "Sam",
            "last_name": "Green",
            "email": "s@g.com",
            "phone": None,
        }

        doc = build_pet_doc(pet, owner)

        assert "None" not in doc["full_text"]


# ── stream_consumer handle_event routing ──────────────────────────────────────


class TestHandleEventRouting:
    """
    Verify that handle_event dispatches to the correct Celery task
    for each table / op combination without hitting real Redis or Celery.
    """

    @pytest.fixture(autouse=True)
    def patch_tasks(self):
        with (
            patch("worker.stream_consumer.index_pet_composite") as m_ipc,
            patch("worker.stream_consumer.reindex_owner_pets") as m_rop,
            patch("worker.stream_consumer.delete_pet_from_index") as m_dpfi,
            patch("worker.stream_consumer.index_document") as m_id,
            patch("worker.stream_consumer.delete_document") as m_dd,
        ):
            self.index_pet_composite = m_ipc
            self.reindex_owner_pets = m_rop
            self.delete_pet_from_index = m_dpfi
            self.index_document = m_id
            self.delete_document = m_dd
            yield

    async def test_pet_insert_routes_to_index_pet_composite(self):
        await handle_event({"op": "insert", "table": "pets", "id": "42", "data": {}})
        self.index_pet_composite.delay.assert_called_once_with(42)

    async def test_pet_update_routes_to_index_pet_composite(self):
        await handle_event({"op": "update", "table": "pets", "id": "7", "data": {}})
        self.index_pet_composite.delay.assert_called_once_with(7)

    async def test_pet_delete_routes_to_delete_pet_from_index(self):
        await handle_event({"op": "delete", "table": "pets", "id": "99", "data": {}})
        self.delete_pet_from_index.delay.assert_called_once_with(99)

    async def test_owner_change_routes_to_reindex_owner_pets(self):
        await handle_event({"op": "update", "table": "owners", "id": "5", "data": {}})
        self.reindex_owner_pets.delay.assert_called_once_with(5)

    async def test_owner_insert_also_routes_to_reindex_owner_pets(self):
        await handle_event({"op": "insert", "table": "owners", "id": "10", "data": {}})
        self.reindex_owner_pets.delay.assert_called_once_with(10)

    async def test_items_insert_routes_to_index_document(self):
        event = {"op": "insert", "table": "items", "id": "abc", "data": {"title": "x"}}
        await handle_event(event)
        self.index_document.delay.assert_called_once_with("items", "abc", {"title": "x"})

    async def test_items_delete_routes_to_delete_document(self):
        await handle_event({"op": "delete", "table": "items", "id": "abc", "data": {}})
        self.delete_document.delay.assert_called_once_with("items", "abc")

    async def test_projects_insert_routes_to_index_document(self):
        event = {"op": "insert", "table": "projects", "id": "proj-1", "data": {"name": "y"}}
        await handle_event(event)
        self.index_document.delay.assert_called_once_with("projects", "proj-1", {"name": "y"})

    async def test_malformed_event_is_skipped(self):
        """Events missing op/table/id must not dispatch any task."""
        await handle_event({"op": "insert", "table": "pets"})  # missing id
        self.index_pet_composite.delay.assert_not_called()
        self.index_document.delay.assert_not_called()

    async def test_pet_composite_tasks_not_called_for_items(self):
        await handle_event({"op": "insert", "table": "items", "id": "1", "data": {}})
        self.index_pet_composite.delay.assert_not_called()
        self.reindex_owner_pets.delay.assert_not_called()
        self.delete_pet_from_index.delay.assert_not_called()
