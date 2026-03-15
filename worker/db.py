"""
Disposable async DB session for use inside synchronous Celery tasks.

Uses NullPool so each task gets its own connection that is closed when
the context exits — no shared pool between tasks or with the FastAPI app.
"""

from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings


@asynccontextmanager
async def task_db():
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    try:
        async with AsyncSession(engine) as session:
            yield session
    finally:
        await engine.dispose()
