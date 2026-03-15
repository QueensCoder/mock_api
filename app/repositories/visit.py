"""
Visit repository.

Visits use a composite PK (id, visited_at) because the table is partitioned
by visited_at. The base CRUDBase.get() filters by id alone — Postgres will
scan all partitions, which is fine. Soft-delete and update work as normal
since the full object (with visited_at) is loaded before mutation.
"""

from app.models.visit import Visit
from app.repositories.base import CRUDBase
from app.schemas.visit import VisitCreate, VisitUpdate

visit_repo = CRUDBase[Visit, VisitCreate, VisitUpdate](Visit)
