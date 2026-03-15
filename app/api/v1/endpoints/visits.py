from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.repositories.visit import visit_repo
from app.schemas.visit import VisitCreate, VisitResponse, VisitUpdate

router = APIRouter()


@router.get("", response_model=list[VisitResponse])
async def list_visits(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await visit_repo.list(db, skip=skip, limit=limit)


@router.post("", response_model=VisitResponse, status_code=status.HTTP_201_CREATED)
async def create_visit(body: VisitCreate, db: AsyncSession = Depends(get_db)):
    return await visit_repo.create(db, obj_in=body)


@router.get("/{visit_id}", response_model=VisitResponse)
async def get_visit(visit_id: int, db: AsyncSession = Depends(get_db)):
    return await visit_repo.get_or_404(db, visit_id)


@router.patch("/{visit_id}", response_model=VisitResponse)
async def update_visit(visit_id: int, body: VisitUpdate, db: AsyncSession = Depends(get_db)):
    visit = await visit_repo.get_or_404(db, visit_id)
    return await visit_repo.update(db, db_obj=visit, obj_in=body)


@router.delete("/{visit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_visit(visit_id: int, db: AsyncSession = Depends(get_db)):
    await visit_repo.soft_delete(db, id=visit_id)
