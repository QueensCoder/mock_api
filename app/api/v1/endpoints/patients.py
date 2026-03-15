from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.repositories.patient import patient_repo
from app.schemas.patient import PatientCreate, PatientResponse, PatientUpdate

router = APIRouter()


@router.get("", response_model=list[PatientResponse])
async def list_patients(skip: int = 0, limit: int = 20, db: AsyncSession = Depends(get_db)):
    return await patient_repo.list(db, skip=skip, limit=limit)


@router.post("", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
async def create_patient(body: PatientCreate, db: AsyncSession = Depends(get_db)):
    return await patient_repo.create(db, obj_in=body)


@router.get("/{patient_id}", response_model=PatientResponse)
async def get_patient(patient_id: int, db: AsyncSession = Depends(get_db)):
    return await patient_repo.get_or_404(db, patient_id)


@router.patch("/{patient_id}", response_model=PatientResponse)
async def update_patient(patient_id: int, body: PatientUpdate, db: AsyncSession = Depends(get_db)):
    patient = await patient_repo.get_or_404(db, patient_id)
    return await patient_repo.update(db, db_obj=patient, obj_in=body)


@router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_patient(patient_id: int, db: AsyncSession = Depends(get_db)):
    await patient_repo.soft_delete(db, id=patient_id)
