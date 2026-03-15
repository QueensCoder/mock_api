from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from scalar_fastapi import get_scalar_api_reference

from app.api.v1.router import api_router
from app.core.config import settings
from app.services.redis import close_redis, get_redis
from app.services.search import ensure_indexes
from app.services.storage import ensure_bucket_exists


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    redis = await get_redis()
    await ensure_indexes(redis)
    ensure_bucket_exists()
    yield
    # Shutdown
    await close_redis()


app = FastAPI(
    title="Backend API",
    version="0.1.0",
    debug=settings.DEBUG,
    lifespan=lifespan,
    # Disable built-in Swagger UI — Scalar replaces it at /docs
    docs_url=None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/docs", include_in_schema=False)
async def scalar_docs() -> HTMLResponse:
    return get_scalar_api_reference(
        openapi_url="/openapi.json",
        title=app.title,
    )
