"""
DAG: visits_daily_rollup
========================
Aggregates the previous day's vet visit data from PostgreSQL into a
DuckDB rollup table (analytics.visits_daily_rollup).

Aggregation: per-day, per-status counts + unique owner/pet counts.
Run window : [execution_date, execution_date + 1 day)
Strategy   : DELETE + INSERT for the target date so re-runs are idempotent.

Production swap to Snowflake
----------------------------
Replace the `_load` function body with a MERGE INTO statement:

    sf.cursor().execute(
        \"\"\"
        MERGE INTO analytics.visits_daily_rollup t
        USING (SELECT %s AS visit_date, %s AS status, %s AS visit_count,
                      %s AS unique_owners, %s AS unique_pets) s
        ON t.visit_date = s.visit_date AND t.status = s.status
        WHEN MATCHED THEN UPDATE SET ...
        WHEN NOT MATCHED THEN INSERT ...
        \"\"\",
        [...],
    )
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta

import duckdb
import psycopg2
import psycopg2.extras
from airflow import DAG
from airflow.operators.python import PythonOperator

DUCKDB_PATH = os.environ.get("DUCKDB_PATH", "/opt/airflow/duckdb/analytics.duckdb")

_PG = dict(
    host=os.environ.get("POSTGRES_HOST", "postgres"),
    port=int(os.environ.get("POSTGRES_PORT", 5432)),
    dbname=os.environ.get("POSTGRES_DB", "app"),
    user=os.environ.get("POSTGRES_USER", "postgres"),
    password=os.environ.get("POSTGRES_PASSWORD", "postgres"),
)

_DEFAULT_ARGS = {
    "owner": "etl",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
}


def _extract(ds: str, **context) -> str:
    """
    Aggregate yesterday's visits from PostgreSQL.

    `ds` is Airflow's execution date string (YYYY-MM-DD).
    We query [ds, ds + 1 day) so each daily run captures exactly one calendar day.
    """
    start = ds  # e.g. "2026-03-14"
    with psycopg2.connect(**_PG) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    DATE(visited_at AT TIME ZONE 'UTC')  AS visit_date,
                    status,
                    COUNT(*)                             AS visit_count,
                    COUNT(DISTINCT owner_id)             AS unique_owners,
                    COUNT(DISTINCT pet_id)               AS unique_pets
                FROM  visits
                WHERE deleted_at IS NULL
                  AND visited_at >= %(start)s::date
                  AND visited_at <  %(start)s::date + INTERVAL '1 day'
                GROUP BY 1, 2
                ORDER BY 1, 2
                """,
                {"start": start},
            )
            rows = [dict(r) for r in cur.fetchall()]

    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", prefix="visits_rollup_", delete=False
    )
    json.dump(rows, tmp, default=str)
    tmp.close()
    print(f"Aggregated {len(rows)} status buckets for {start} → {tmp.name}")
    return tmp.name


def _load(ds: str, **context) -> None:
    """Upsert aggregated visit rows into DuckDB analytics.visits_daily_rollup."""
    file_path: str = context["ti"].xcom_pull(task_ids="extract")

    with open(file_path) as f:
        rows = json.load(f)

    os.unlink(file_path)

    with duckdb.connect(DUCKDB_PATH) as conn:
        conn.execute("CREATE SCHEMA IF NOT EXISTS analytics")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analytics.visits_daily_rollup (
                visit_date      DATE        NOT NULL,
                status          VARCHAR(50) NOT NULL,
                visit_count     BIGINT      NOT NULL,
                unique_owners   BIGINT      NOT NULL,
                unique_pets     BIGINT      NOT NULL,
                refreshed_at    TIMESTAMPTZ DEFAULT now(),
                PRIMARY KEY (visit_date, status)
            )
            """
        )
        # Idempotent: delete this date's rows before re-inserting
        conn.execute("DELETE FROM analytics.visits_daily_rollup WHERE visit_date = ?", [ds])
        if rows:
            conn.executemany(
                """
                INSERT INTO analytics.visits_daily_rollup
                    (visit_date, status, visit_count, unique_owners, unique_pets)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        r["visit_date"],
                        r["status"],
                        r["visit_count"],
                        r["unique_owners"],
                        r["unique_pets"],
                    )
                    for r in rows
                ],
            )
        print(f"Upserted {len(rows)} rows for {ds} into analytics.visits_daily_rollup")


with DAG(
    dag_id="visits_daily_rollup",
    description="Daily aggregation of vet visits by status into DuckDB analytics",
    schedule="0 3 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args=_DEFAULT_ARGS,
    tags=["etl", "visits", "rollup"],
) as dag:
    t_extract = PythonOperator(task_id="extract", python_callable=_extract)
    t_load = PythonOperator(task_id="load", python_callable=_load)

    t_extract >> t_load
