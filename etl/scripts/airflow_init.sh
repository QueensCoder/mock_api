#!/usr/bin/env bash
# One-shot Airflow initialisation: create metadata DB, run migrations, create admin user.
set -euo pipefail

echo "→ Ensuring 'airflow' database exists on PostgreSQL..."
python - <<'PYEOF'
import os, psycopg2

conn = psycopg2.connect(
    host=os.environ.get("POSTGRES_HOST", "postgres"),
    port=int(os.environ.get("POSTGRES_PORT", 5432)),
    dbname="postgres",
    user=os.environ.get("POSTGRES_USER", "postgres"),
    password=os.environ.get("POSTGRES_PASSWORD", "postgres"),
)
conn.autocommit = True
cur = conn.cursor()
cur.execute("SELECT 1 FROM pg_database WHERE datname = 'airflow'")
if not cur.fetchone():
    cur.execute("CREATE DATABASE airflow")
    print("  Created 'airflow' database.")
else:
    print("  'airflow' database already exists.")
conn.close()
PYEOF

echo "→ Running Airflow DB migrations..."
airflow db migrate

echo "→ Creating admin user (skipped if already exists)..."
airflow users create \
    --username  "${AIRFLOW_ADMIN_USER:-admin}" \
    --password  "${AIRFLOW_ADMIN_PASSWORD:-admin}" \
    --firstname "Admin" \
    --lastname  "User" \
    --role      Admin \
    --email     "${AIRFLOW_ADMIN_EMAIL:-admin@example.com}" 2>/dev/null || true

echo "✓ Airflow init complete."
