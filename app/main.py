from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import settings
from app.services.redis import close_redis, get_redis
from app.services.storage import ensure_bucket_exists


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await get_redis()
    ensure_bucket_exists()
    yield
    # Shutdown
    await close_redis()


app = FastAPI(
    title="Backend API",
    version="0.1.0",
    debug=settings.DEBUG,
    lifespan=lifespan,
)

app.include_router(api_router, prefix="/api/v1")
