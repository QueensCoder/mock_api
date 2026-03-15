.PHONY: help build up up-detach down restart logs logs-app logs-worker logs-cdc logs-flower logs-nginx flower shell \
        worker-shell worker-inspect worker-purge \
        test test-cov test-search \
        migrate migrate-auto migrate-down migrate-history \
        format lint minio-setup setup clean lock sync \
        search-reindex redis-insight

# Default target
help:
	@echo "Available commands:"
	@echo ""
	@echo "  Docker"
	@echo "    make build         Build docker images"
	@echo "    make up            Start all services (foreground)"
	@echo "    make up-detach     Start all services (background)"
	@echo "    make down          Stop and remove containers"
	@echo "    make restart       Restart all services"
	@echo "    make logs          Tail all service logs"
	@echo "    make logs-app      Tail app logs only"
	@echo "    make logs-worker   Tail celery worker logs"
	@echo "    make logs-cdc      Tail Redpanda Connect + stream consumer logs"
	@echo "    make logs-flower   Tail Flower logs"
	@echo "    make logs-nginx    Tail Nginx logs"
	@echo "    make flower        Open Flower UI in browser (port 5555)"
	@echo "    make shell         Open shell in app container"
	@echo "    make worker-shell  Open shell in celery worker container"
	@echo "    make worker-inspect  Inspect active celery tasks"
	@echo "    make worker-purge  Purge all pending celery tasks"
	@echo ""
	@echo "  Dependencies (uv)"
	@echo "    make lock          Generate/update uv.lock"
	@echo "    make sync          Sync venv from lockfile (including dev deps)"
	@echo "    make add PKG=foo   Add a dependency (e.g. make add PKG=httpx)"
	@echo ""
	@echo "  Database"
	@echo "    make migrate       Run alembic upgrade head"
	@echo "    make migrate-auto MSG='desc'  Autogenerate a migration"
	@echo "    make migrate-down  Downgrade last migration"
	@echo "    make migrate-history  Show migration history"
	@echo ""
	@echo "  Testing"
	@echo "    make test          Run tests"
	@echo "    make test-cov      Run tests with HTML coverage report"
	@echo "    make test-search   Run search + CDC pipeline integration tests"
	@echo ""
	@echo "  Code quality"
	@echo "    make format        Format code with ruff"
	@echo "    make lint          Lint code with ruff"
	@echo ""
	@echo "  Search / CDC"
	@echo "    make test-search   Run search + CDC pipeline integration tests"
	@echo "    make redis-insight Open RedisInsight UI in browser (port 8001)"
	@echo "    make search-reindex  Drop + recreate RediSearch indexes"
	@echo "    make logs-cdc      Tail Redpanda Connect + stream consumer logs"
	@echo ""
	@echo "  API docs"
	@echo "    open http://localhost/docs     Scalar API docs (via nginx)"
	@echo "    open http://localhost/openapi.json  Raw OpenAPI schema"
	@echo ""
	@echo "  Misc"
	@echo "    make minio-setup   Create default MinIO bucket"
	@echo "    make setup         First-time setup (env, build, up, migrate)"
	@echo "    make clean         Remove containers, volumes, and local images"

# ── Docker ────────────────────────────────────────────────────────────────────

build:
	docker compose build

up:
	docker compose up

up-detach:
	docker compose up -d

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f

logs-app:
	docker compose logs -f app

logs-worker:
	docker compose logs -f celery_worker

logs-cdc:
	docker compose logs -f redpanda_connect stream_consumer

logs-flower:
	docker compose logs -f flower

logs-nginx:
	docker compose logs -f nginx

flower:
	open http://localhost:5555

shell:
	docker compose exec app /bin/bash

worker-shell:
	docker compose exec celery_worker /bin/bash

worker-inspect:
	docker compose exec celery_worker celery -A worker.celery_app inspect active

worker-purge:
	docker compose exec celery_worker celery -A worker.celery_app purge -f

# ── Dependencies (uv) ─────────────────────────────────────────────────────────

lock:
	uv lock

sync:
	uv sync --all-extras

add:
	@test -n "$(PKG)" || (echo "Error: PKG is required. Usage: make add PKG=package-name" && exit 1)
	uv add $(PKG)

# ── Database ──────────────────────────────────────────────────────────────────

migrate:
	docker compose exec app alembic upgrade head

migrate-auto:
	@test -n "$(MSG)" || (echo "Error: MSG is required. Usage: make migrate-auto MSG='your message'" && exit 1)
	docker compose exec app alembic revision --autogenerate -m "$(MSG)"

migrate-down:
	docker compose exec app alembic downgrade -1

migrate-history:
	docker compose exec app alembic history

# ── Testing ───────────────────────────────────────────────────────────────────

test:
	docker compose exec app uv run pytest tests/ -v

test-cov:
	docker compose exec app uv run pytest tests/ -v --cov=app --cov-report=html

# Run only the search + CDC pipeline integration tests (requires Redis Stack)
test-search:
	docker compose exec app uv run pytest tests/integration/test_search_service.py tests/integration/test_cdc_pipeline.py -v

# ── Code quality ──────────────────────────────────────────────────────────────

format:
	uv run ruff format app/ worker/ tests/

lint:
	uv run ruff check app/ worker/ tests/

# ── Search / CDC ──────────────────────────────────────────────────────────────

# Open RedisInsight UI (Redis Stack visualiser) in the default browser
redis-insight:
	open http://localhost:8001

# Drop and recreate all RediSearch indexes (triggers a fresh snapshot from Redpanda Connect)
search-reindex:
	docker compose exec app uv run python -c "\
	import asyncio; \
	from redis.asyncio import Redis; \
	from app.services.search import ITEM_INDEX, PROJECT_INDEX; \
	async def drop(): \
	    r = Redis.from_url('redis://redis:6379/0', decode_responses=True); \
	    [await r.ft(i).dropindex(delete_documents=False) for i in (ITEM_INDEX, PROJECT_INDEX)]; \
	    print('Indexes dropped — Redpanda Connect will repopulate on next restart'); \
	asyncio.run(drop())"

# ── MinIO ─────────────────────────────────────────────────────────────────────

minio-setup:
	@source .env && docker compose exec minio mc alias set local http://localhost:9000 $$MINIO_ROOT_USER $$MINIO_ROOT_PASSWORD
	@source .env && docker compose exec minio mc mb local/$$S3_BUCKET_NAME --ignore-existing

# ── First-time setup ──────────────────────────────────────────────────────────

setup:
	@test -f .env || (cp .env.example .env && echo ".env created — update values before running in production")
	$(MAKE) build
	$(MAKE) up-detach
	@echo "Waiting for services to be healthy..."
	@sleep 8
	$(MAKE) migrate

# ── Clean ─────────────────────────────────────────────────────────────────────

clean:
	docker compose down -v --rmi local
