from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.repositories.pet import pet_repo
from app.schemas.pet import PetCreate, PetResponse, PetUpdate

router = APIRouter()


@router.get("", response_model=list[PetResponse])
async def list_pets(skip: int = 0, limit: int = 20, db: AsyncSession = Depends(get_db)):
    return await pet_repo.list(db, skip=skip, limit=limit)


@router.post("", response_model=PetResponse, status_code=status.HTTP_201_CREATED)
async def create_pet(body: PetCreate, db: AsyncSession = Depends(get_db)):
    return await pet_repo.create(db, obj_in=body)


@router.get("/{pet_id}", response_model=PetResponse)
async def get_pet(pet_id: int, db: AsyncSession = Depends(get_db)):
    return await pet_repo.get_or_404(db, pet_id)


@router.patch("/{pet_id}", response_model=PetResponse)
async def update_pet(pet_id: int, body: PetUpdate, db: AsyncSession = Depends(get_db)):
    pet = await pet_repo.get_or_404(db, pet_id)
    return await pet_repo.update(db, db_obj=pet, obj_in=body)


@router.delete("/{pet_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pet(pet_id: int, db: AsyncSession = Depends(get_db)):
    await pet_repo.soft_delete(db, id=pet_id)
