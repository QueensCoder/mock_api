# Backend

FastAPI backend with PostgreSQL, Redis Stack, MinIO, Celery, a CDC pipeline powered by Redpanda Connect, and an ETL pipeline using Apache Airflow with DuckDB (local Snowflake substitute).

## Stack

| Layer | Technology |
|---|---|
| API | FastAPI 0.115, Python 3.12 |
| Database | PostgreSQL 16 |
| Search index | Redis Stack (RediSearch + RedisJSON) |
| Object storage | MinIO (S3-compatible) |
| Task queue | Celery 5 + Redis broker |
| CDC pipeline | Redpanda Connect → Redis Streams → Celery |
| ETL orchestration | Apache Airflow 2.10 (CeleryExecutor) |
| Analytics warehouse | DuckDB (local) → Snowflake (production) |
| Auth | Stytch (session token verification) |
| Reverse proxy | Nginx |
| API docs | Scalar (at `/docs`) |
| Package manager | uv |
| Migrations | Alembic (dedicated container) |

## Architecture

```
                         ┌─────────────────────────────────────────────┐
  Frontend               │  Docker Compose (local)                     │
     │                   │                                             │
     └──► nginx :80 ────►│  FastAPI :8000                              │
                         │    │                                        │
                         │    ├── PostgreSQL :5432                     │
                         │    ├── Redis Stack :6379                    │
                         │    └── MinIO :9000                          │
                         │                                             │
                         │  CDC pipeline                               │
                         │    Postgres WAL                             │
                         │      └── Redpanda Connect                   │
                         │            └── Redis Streams                │
                         │                  └── stream_consumer        │
                         │                        └── Celery           │
                         │                              └── Redis Stack (search index)
                         │                                             │
                         │  ETL pipeline (Airflow CeleryExecutor)      │
                         │    Airflow scheduler  :—                    │
                         │    Airflow webserver  :8080                 │
                         │    Airflow worker                           │
                         │      └── PostgreSQL (source)                │
                         │            └── DuckDB analytics.duckdb      │
                         │                  (swap → Snowflake in prod) │
                         │                                             │
                         │  Monitoring                                 │
                         │    Flower        :5555                      │
                         │    RedisInsight  :8001                      │
                         └─────────────────────────────────────────────┘
```

## Quick start

```bash
# 1. Clone and create .env
cp .env.example .env

# 2. Build and start all services
make setup          # build + up + migrate

# 3. Install pre-commit hooks (once per clone)
make pre-commit-install
```

Services start on:

| Service | URL |
|---|---|
| API (via nginx) | http://localhost |
| API docs (Scalar) | http://localhost/docs |
| FastAPI (direct) | http://localhost:8000 |
| Airflow UI | http://localhost:8080 |
| Flower (Celery monitor) | http://localhost:5555 |
| RedisInsight | http://localhost:8001 |
| MinIO console | http://localhost:9001 |

## Common commands

```bash
# Docker
make up-detach          # start all services in background
make down               # stop everything
make logs               # tail all logs
make logs-app           # FastAPI logs only
make logs-cdc           # Redpanda Connect + stream consumer logs
make logs-flower        # Flower logs

# Database migrations (dedicated container)
make migrate                        # apply all pending migrations
make migrate-auto MSG="add column"  # autogenerate migration from model changes
make migrate-down                   # roll back one migration
make migrate-history                # show applied migrations

# Testing
make test               # all tests
make test-cov           # with HTML coverage report
make test-search        # search + CDC pipeline integration tests only

# Code quality (runs on host)
make lint               # ruff check
make format             # ruff format
make pre-commit-run     # run all pre-commit hooks against every file

# Search
make redis-insight      # open RedisInsight in browser
make search-reindex     # drop and recreate RediSearch indexes

# ETL / Airflow
make etl-keygen         # generate a Fernet key for AIRFLOW_FERNET_KEY
make etl-init           # create Airflow metadata DB + admin user (run once)
make etl-up             # start Airflow webserver, scheduler, worker
make etl-down           # stop Airflow services
make etl-logs           # tail Airflow logs
make etl-shell          # shell into the Airflow worker
make airflow-ui         # open Airflow UI at http://localhost:8080
```

## Project layout

```
backend/
├── app/
│   ├── api/v1/
│   │   └── endpoints/
│   │       ├── auth.py       # POST /auth/verify
│   │       ├── events.py     # GET  /events/{id}  (SSE)
│   │       ├── health.py     # GET  /health
│   │       └── users.py      # GET  /users/me
│   ├── core/
│   │   ├── auth.py           # Stytch session verification
│   │   └── config.py         # pydantic-settings (env vars)
│   ├── db/
│   │   ├── base.py           # PrimaryKeyMixin, TimestampMixin, AuditMixin
│   │   └── session.py        # async engine + connection pool
│   ├── models/
│   │   ├── user.py
│   │   ├── project.py
│   │   └── item.py
│   └── services/
│       ├── redis.py          # async Redis client
│       ├── search.py         # RediSearch index management + queries
│       └── storage.py        # S3/MinIO helpers
├── worker/
│   ├── celery_app.py
│   ├── config.py
│   ├── stream_consumer.py    # Redis Streams → Celery dispatch
│   └── tasks/
│       ├── example.py
│       └── search_index.py   # index_document, delete_document
├── migrations/
│   ├── Dockerfile            # stripped-down image (no FastAPI/Redis/Celery)
│   ├── env.py
│   └── versions/
│       └── 0001_initial_schema.py
├── etl/
│   ├── Dockerfile            # Airflow 2.10 image + duckdb + postgres provider
│   ├── scripts/
│   │   └── airflow_init.sh   # one-shot: create DB, migrate, seed admin user
│   ├── dags/
│   │   ├── users_snapshot.py      # nightly users → analytics.users_snapshot
│   │   └── visits_daily_rollup.py # daily visits aggregate → analytics.visits_daily_rollup
│   └── plugins/              # custom Airflow operators/hooks (empty, extend here)
├── redpanda/
│   └── pipeline.yaml         # CDC pipeline: Postgres WAL → Redis Streams
├── nginx/
│   └── nginx.conf
├── tests/
│   ├── unit/
│   │   ├── test_auth.py
│   │   └── test_sse.py
│   └── integration/
│       ├── test_auth_routes.py
│       ├── test_search_service.py
│       └── test_cdc_pipeline.py
├── docs/
│   └── ARCHITECTURE.md       # ADR: CDC options, Redis Search, Snowflake audit log
├── docker-compose.yml
├── Makefile
├── pyproject.toml
└── .pre-commit-config.yaml
```

## ETL pipeline

Apache Airflow orchestrates nightly ETL jobs that extract data from the operational PostgreSQL database and load it into a DuckDB analytics warehouse (a local Snowflake substitute with compatible SQL syntax).

### First-time setup

```bash
# 1. Generate a Fernet key and add it to .env
make etl-keygen          # copy the output into AIRFLOW_FERNET_KEY in .env

# 2. Initialise the Airflow metadata DB + create admin user
make etl-init

# 3. Start the Airflow services
make etl-up

# 4. Open the UI (default credentials: admin / admin)
make airflow-ui
```

### DAGs

| DAG | Schedule | Source → Target |
|---|---|---|
| `users_daily_snapshot` | 02:00 UTC | `users` → `analytics.users_snapshot` (full reload) |
| `visits_daily_rollup` | 03:00 UTC | `visits` → `analytics.visits_daily_rollup` (per-day aggregate) |

### Swapping DuckDB for Snowflake (production)

Each DAG's `_load` function contains a commented-out Snowflake block. To switch:
1. Add `snowflake-connector-python` to `etl/Dockerfile`
2. Set `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`, `SNOWFLAKE_WAREHOUSE` in `.env`
3. Replace the DuckDB write block with the commented Snowflake block in each DAG

### DuckDB analytics schema

```sql
-- Inspect the local analytics warehouse
duckdb /path/to/analytics.duckdb

SELECT * FROM analytics.users_snapshot LIMIT 10;
SELECT * FROM analytics.visits_daily_rollup ORDER BY visit_date DESC;
```

## Database conventions

Every table uses the same set of base mixins:

| Column | Type | Notes |
|---|---|---|
| `id` | `BIGINT` | `GENERATED ALWAYS AS IDENTITY` — SQL standard auto-increment |
| `created_at` | `TIMESTAMPTZ` | Set on insert, never changes |
| `updated_at` | `TIMESTAMPTZ` | Refreshed by SQLAlchemy on every update |
| `deleted_at` | `TIMESTAMPTZ` | `NULL` = live row. Soft-delete pattern — always filter `WHERE deleted_at IS NULL` |
| `created_by` | `BIGINT` | User ID who created the row (application-enforced, no FK) |
| `updated_by` | `BIGINT` | User ID who last updated the row |
| `deleted_by` | `BIGINT` | User ID who soft-deleted the row |

Adding a new model:
1. Create `app/models/your_model.py` using `Base, PrimaryKeyMixin, TimestampMixin, AuditMixin`
2. Import it in `app/models/__init__.py`
3. Run `make migrate-build && make migrate-auto MSG="add your_model table"`
4. Review the generated file in `migrations/versions/`, then `make migrate`

## CDC pipeline

Postgres WAL changes on the `items` and `projects` tables are streamed to the Redis Stack search index in near real-time:

```
Postgres (wal_level=logical)
  └── Redpanda Connect           reads WAL, normalises to {op, table, id, data}
        └── Redis Stream         cdc:events  (consumer group: search_indexer)
              └── stream_consumer  dispatches Celery tasks
                    └── Celery     index_document / delete_document
                          └── Redis Stack  (RediSearch JSON indexes)
```

To add a new table to the CDC pipeline, edit `redpanda/pipeline.yaml` and add the table to the `tables` list — no application code changes needed.

Querying the search index:

```python
from app.services.search import search_items, search_projects
results = await search_items(redis, "mechanical keyboard")
```

Publishing an SSE event:

```bash
# From redis-cli or application code
PUBLISH events:42 '{"type": "item_updated", "id": 42}'
```

## Authentication

The API uses [Stytch](https://stytch.com) session tokens. The client sends:

```
Authorization: Bearer <stytch_session_token>
```

Error codes returned on 401:

| Code | Meaning | Client action |
|---|---|---|
| `TOKEN_EXPIRED` | Session expired but valid | Call `stytch.session.getTokens()` then retry |
| `TOKEN_INVALID` | Session revoked or not found | Redirect to login |

## Environment variables

Copy `.env.example` to `.env` and fill in the Stytch keys. Everything else works with the defaults for local development.

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | postgres://postgres:postgres@postgres:5432/app | |
| `REDIS_URL` | redis://redis:6379/0 | |
| `STYTCH_PROJECT_ID` | — | Required for auth |
| `STYTCH_SECRET` | — | Required for auth |
| `DB_POOL_SIZE` | 10 | Postgres connection pool size per process |
| `DB_MAX_OVERFLOW` | 20 | Extra connections allowed under burst |
| `S3_BUCKET_NAME` | app-bucket | MinIO bucket name |
| `AIRFLOW_FERNET_KEY` | — | Required for Airflow — generate with `make etl-keygen` |
| `AIRFLOW_SECRET_KEY` | changeme-in-prod | Flask secret key for Airflow webserver |
| `AIRFLOW_ADMIN_USER` | admin | Airflow UI login username |
| `AIRFLOW_ADMIN_PASSWORD` | admin | Airflow UI login password |
| `DUCKDB_PATH` | /opt/airflow/duckdb/analytics.duckdb | Path to the DuckDB analytics file |

## Pre-commit hooks

Runs on the host (not in Docker) before every `git commit`:

- **ruff** — lint + auto-fix
- **ruff-format** — formatting
- trailing whitespace, end-of-file, merge conflict markers
- YAML / TOML / JSON syntax check
- large file detection (>500 KB)
- private key detection

```bash
make pre-commit-install   # install once after cloning
make pre-commit-run       # run manually against all files
make pre-commit-update    # bump hook versions
```
