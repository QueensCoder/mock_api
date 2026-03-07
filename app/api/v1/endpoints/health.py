from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.redis import get_redis

router = APIRouter()


@router.get("")
async def health_check(db: AsyncSession = Depends(get_db)):
    await db.execute(text("SELECT 1"))
    redis = await get_redis()
    await redis.ping()
    return {"status": "ok", "database": "ok", "redis": "ok"}
