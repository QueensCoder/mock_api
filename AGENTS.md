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
| Cache | Redis 7 |
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
make shell          # open shell inside the app container
```
