from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.repositories.owner import owner_repo
from app.schemas.owner import OwnerCreate, OwnerResponse, OwnerUpdate

router = APIRouter()


@router.get("", response_model=list[OwnerResponse])
async def list_owners(skip: int = 0, limit: int = 20, db: AsyncSession = Depends(get_db)):
    return await owner_repo.list(db, skip=skip, limit=limit)


@router.post("", response_model=OwnerResponse, status_code=status.HTTP_201_CREATED)
async def create_owner(body: OwnerCreate, db: AsyncSession = Depends(get_db)):
    return await owner_repo.create(db, obj_in=body)


@router.get("/{owner_id}", response_model=OwnerResponse)
async def get_owner(owner_id: int, db: AsyncSession = Depends(get_db)):
    return await owner_repo.get_or_404(db, owner_id)


@router.patch("/{owner_id}", response_model=OwnerResponse)
async def update_owner(owner_id: int, body: OwnerUpdate, db: AsyncSession = Depends(get_db)):
    owner = await owner_repo.get_or_404(db, owner_id)
    return await owner_repo.update(db, db_obj=owner, obj_in=body)


@router.delete("/{owner_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_owner(owner_id: int, db: AsyncSession = Depends(get_db)):
    await owner_repo.soft_delete(db, id=owner_id)
