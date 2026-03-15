from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.repositories.medicine import medicine_repo
from app.schemas.medicine import MedicineCreate, MedicineResponse, MedicineUpdate

router = APIRouter()


@router.get("", response_model=list[MedicineResponse])
async def list_medicines(skip: int = 0, limit: int = 20, db: AsyncSession = Depends(get_db)):
    return await medicine_repo.list(db, skip=skip, limit=limit)


@router.post("", response_model=MedicineResponse, status_code=status.HTTP_201_CREATED)
async def create_medicine(body: MedicineCreate, db: AsyncSession = Depends(get_db)):
    return await medicine_repo.create(db, obj_in=body)


@router.get("/{medicine_id}", response_model=MedicineResponse)
async def get_medicine(medicine_id: int, db: AsyncSession = Depends(get_db)):
    return await medicine_repo.get_or_404(db, medicine_id)


@router.patch("/{medicine_id}", response_model=MedicineResponse)
async def update_medicine(
    medicine_id: int, body: MedicineUpdate, db: AsyncSession = Depends(get_db)
):
    medicine = await medicine_repo.get_or_404(db, medicine_id)
    return await medicine_repo.update(db, db_obj=medicine, obj_in=body)


@router.delete("/{medicine_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_medicine(medicine_id: int, db: AsyncSession = Depends(get_db)):
    await medicine_repo.soft_delete(db, id=medicine_id)
