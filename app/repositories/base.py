"""
Generic async CRUD base class.

Usage:
    class CRUDOwner(CRUDBase[Owner, OwnerCreate, OwnerUpdate]):
        pass

    owner_repo = CRUDOwner(Owner)

All read operations filter deleted_at IS NULL (soft-delete aware).
"""

from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)
CreateT = TypeVar("CreateT")
UpdateT = TypeVar("UpdateT")


class CRUDBase(Generic[ModelT, CreateT, UpdateT]):
    def __init__(self, model: type[ModelT]) -> None:
        self.model = model

    async def get(self, db: AsyncSession, id: int) -> ModelT | None:
        result = await db.execute(
            select(self.model).where(
                self.model.id == id,
                self.model.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_or_404(self, db: AsyncSession, id: int) -> ModelT:
        from fastapi import HTTPException

        obj = await self.get(db, id)
        if obj is None:
            raise HTTPException(status_code=404, detail=f"{self.model.__name__} not found")
        return obj

    async def list(self, db: AsyncSession, *, skip: int = 0, limit: int = 20) -> list[ModelT]:
        result = await db.execute(
            select(self.model)
            .where(self.model.deleted_at.is_(None))
            .order_by(self.model.id)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars())

    async def create(self, db: AsyncSession, *, obj_in: CreateT, **extra: Any) -> ModelT:
        data = obj_in.model_dump()
        data.update(extra)
        db_obj = self.model(**data)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update(
        self, db: AsyncSession, *, db_obj: ModelT, obj_in: UpdateT | dict[str, Any]
    ) -> ModelT:
        data = obj_in.model_dump(exclude_unset=True) if hasattr(obj_in, "model_dump") else obj_in
        for field, value in data.items():
            setattr(db_obj, field, value)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def soft_delete(self, db: AsyncSession, *, id: int) -> ModelT | None:
        db_obj = await self.get(db, id)
        if db_obj is None:
            return None
        db_obj.deleted_at = datetime.now(UTC)
        await db.commit()
        return db_obj
