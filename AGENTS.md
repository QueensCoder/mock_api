# AGENTS.md

Guidelines for AI coding agents (Claude Code, Copilot, etc.) working in this repository.

## Project Overview

FastAPI backend with PostgreSQL (SQLAlchemy ORM), Redis, and MinIO (S3-compatible storage).
Package management is handled by **uv**.

## Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI |
| ORM | SQLAlchemy 2.x (async) |
| Validation | Pydantic v2 |
| Database | PostgreSQL 16 via asyncpg |
| Auth | Clerk (JWT via JWKS) |
| Cache / broker | Redis 7 |
| Task queue | Celery 5 |
| Object storage | MinIO (S3-compatible, boto3) |
| Migrations | Alembic |
| Package manager | uv |
| Container runtime | Docker Compose |

## Key Directories

```
app/
  core/        # Settings (pydantic-settings), shared utilities
  db/          # SQLAlchemy engine, session factory, Base declarative class
  models/      # ORM model definitions — all must be imported in app/models/__init__.py
  schemas/     # Pydantic request/response schemas
  api/v1/      # FastAPI routers and endpoint functions
    endpoints/ # One file per resource (e.g. users.py, items.py)
  services/    # Business logic, redis client, S3 storage helpers
  utils/       # Pure helper functions with no side effects
migrations/    # Alembic migration scripts
worker/        # Celery worker (separate container, own Dockerfile)
  celery_app.py  # Celery instance — autodiscovers worker/tasks/
  config.py      # Celery broker/backend settings (reads from app.core.config)
  tasks/         # One file per task group (e.g. email.py, reports.py)
  Dockerfile     # Worker image (built from repo root context)
tests/
  unit/        # Pure unit tests — no DB or external services
  integration/ # Tests that require running services (use conftest.py fixtures)
```

## Coding Conventions

- **Python 3.12+** — use modern type hints (`list[str]`, `str | None`, `X | Y`), no `Optional`.
- **Async first** — all DB operations use `AsyncSession`; all endpoints are `async def`.
- **Pydantic v2** — use `model_config = ConfigDict(...)`, not the old inner `class Config`.
- **SQLAlchemy 2.x mapped columns** — use `Mapped[T]` and `mapped_column(...)`, not legacy `Column`.
- **Settings** — always read from `app.core.config.settings`, never hard-code env values.
- **No print statements** — use Python `logging`.
- **Line length** — 100 characters (enforced by ruff).

## Adding a New Resource

1. Create `app/models/your_model.py` with the ORM class extending `Base`, `UUIDMixin`, `TimestampMixin`.
2. Import it in `app/models/__init__.py` so Alembic can detect it.
3. Create `app/schemas/your_model.py` with Pydantic schemas (`Create`, `Update`, `Response`).
4. Create `app/api/v1/endpoints/your_model.py` with an `APIRouter`.
5. Register the router in `app/api/v1/router.py`.
6. Run `make migrate-auto MSG="add your_model table"` to generate the migration.
7. Run `make migrate` to apply it.

## Authentication (Clerk)

Auth is handled externally by Clerk on the TypeScript client. The backend only verifies JWTs.

**Flow:**
1. Client completes OAuth/SSO via Clerk → receives a session token.
2. Client sends `Authorization: Bearer <session_token>` on every API request.
3. Backend fetches Clerk's JWKS (cached 1 hour), verifies the RS256 JWT.

**Key files:**
- `app/core/auth.py` — JWKS fetching + JWT verification logic
- `app/schemas/auth.py` — `ClerkUser` Pydantic model (decoded token claims)
- `app/api/deps.py` — `get_current_user` and `require_org_role` FastAPI dependencies

**Protecting a route:**
```python
from app.api.deps import get_current_user, require_org_role
from app.schemas.auth import ClerkUser

# Require any authenticated user
@router.get("/protected")
async def protected(user: ClerkUser = Depends(get_current_user)):
    ...

# Require a specific org role
@router.delete("/admin-only", dependencies=[Depends(require_org_role("org:admin"))])
async def admin_only():
    ...
```

**Required env vars:**
- `CLERK_JWKS_URL` — from Clerk Dashboard → API Keys → Advanced → JWKS URL
- `CLERK_ISSUER` — your Clerk Frontend API URL (skip issuer check locally by leaving empty)

## Adding a Celery Task

1. Create (or add to) a file in `worker/tasks/` — e.g. `worker/tasks/email.py`.
2. Decorate with `@celery.task(bind=True, name="group.action")`.
3. Celery autodiscovers all modules listed in `celery.autodiscover_tasks(["worker.tasks"])`.
4. Call from the API with `.delay()` or `.apply_async()`:
   ```python
   from worker.tasks.email import send_email
   send_email.delay(to="user@example.com", subject="Hi", body="...")
   ```
5. Monitor via `make worker-inspect` or the Flower UI (add `flower` service if needed).

## Database Migrations

- Autogenerate: `make migrate-auto MSG="descriptive message"`
- Apply: `make migrate`
- Rollback one: `make migrate-down`
- Never edit an already-applied migration — create a new one instead.

## Dependency Management

Use `uv` — do not edit `pyproject.toml` directly for adding packages:

```bash
make add PKG=package-name          # add a runtime dependency
uv add --dev package-name          # add a dev dependency
make lock                          # regenerate uv.lock
```

## Environment

- Copy `.env.example` to `.env` before running locally.
- Never commit `.env`.
- All service connection strings are read from environment variables via `app.core.config.settings`.

## Common Commands

```bash
make setup          # first-time: copies .env, builds images, starts services, runs migrations
make up-detach      # start services in the background
make migrate        # apply pending migrations
make test           # run test suite
make lint           # ruff lint check
make format         # ruff auto-format
make logs-app       # tail app container logs
make logs-worker    # tail celery worker logs
make shell          # open shell inside the app container
make worker-shell   # open shell inside the celery worker container
make worker-inspect # show active celery tasks
make worker-purge   # purge all pending tasks from the queue
```
