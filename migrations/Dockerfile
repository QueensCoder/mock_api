FROM python:3.12-slim

WORKDIR /app

# PostgreSQL client tools (pg_dump, psql, pg_restore) + tmux for interactive sessions.
# postgresql-client installs the PG 15 clients — compatible with PG 16 servers.
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    tmux \
    curl \
 && rm -rf /var/lib/apt/lists/*

# MinIO client (mc) — used to stream dumps directly to/from MinIO.
# Single static binary, no extra deps.
RUN curl -sSL https://dl.min.io/client/mc/release/linux-amd64/mc \
      -o /usr/local/bin/mc \
 && chmod +x /usr/local/bin/mc

# Only the packages Alembic needs to connect to Postgres and read models.
# No FastAPI, no Redis, no Celery, no Stytch — keeps the image small and fast.
RUN pip install --no-cache-dir \
    alembic==1.13.3 \
    sqlalchemy==2.0.35 \
    asyncpg==0.29.0 \
    psycopg2-binary==2.9.9 \
    pydantic==2.9.2 \
    pydantic-settings==2.5.2

# Alembic config
COPY alembic.ini .

# Migration files
COPY migrations/env.py        migrations/env.py
COPY migrations/versions/     migrations/versions/

# Only the app modules that migrations/env.py actually imports:
#   app.core.config  — DATABASE_URL from environment
#   app.db.base      — Base, mixins
#   app.models.*     — all ORM models (needed for autogenerate)
COPY app/__init__.py           app/__init__.py
COPY app/core/__init__.py      app/core/__init__.py
COPY app/core/config.py        app/core/config.py
COPY app/db/__init__.py        app/db/__init__.py
COPY app/db/base.py            app/db/base.py
COPY app/models/               app/models/

CMD ["alembic", "upgrade", "head"]
