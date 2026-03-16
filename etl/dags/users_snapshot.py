"""
DAG: users_daily_snapshot
=========================
Nightly full snapshot of the operational `users` table into
DuckDB (analytics.users_snapshot).

Schedule  : 02:00 UTC daily
Strategy  : TRUNCATE + full reload (table is small; incremental adds complexity
            without meaningful benefit at this scale).
Temp file : extracted rows are written to a JSON file on disk so we avoid
            XCom size limits. The file is cleaned up by the load task.

Production swap to Snowflake
----------------------------
Replace the `_load` function body with:

    import snowflake.connector
    from snowflake.connector.pandas_tools import write_pandas
    import pandas as pd

    df = pd.read_json(file_path)
    with snowflake.connector.connect(
        account   = os.environ["SNOWFLAKE_ACCOUNT"],
        user      = os.environ["SNOWFLAKE_USER"],
        password  = os.environ["SNOWFLAKE_PASSWORD"],
        database  = "ANALYTICS",
        schema    = "PUBLIC",
        warehouse = os.environ["SNOWFLAKE_WAREHOUSE"],
    ) as sf:
        sf.cursor().execute("TRUNCATE TABLE users_snapshot")
        write_pandas(sf, df, "USERS_SNAPSHOT")
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


def _extract(**context) -> str:
    """Pull all non-deleted users from PostgreSQL; write to a temp JSON file."""
    with psycopg2.connect(**_PG) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    id,
                    stytch_user_id,
                    email,
                    first_name,
                    last_name,
                    is_active,
                    created_at,
                    updated_at
                FROM users
                WHERE deleted_at IS NULL
                ORDER BY id
                """
            )
            rows = [dict(r) for r in cur.fetchall()]

    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", prefix="users_snapshot_", delete=False
    )
    json.dump(rows, tmp, default=str)
    tmp.close()
    print(f"Extracted {len(rows)} users → {tmp.name}")
    return tmp.name


def _load(**context) -> None:
    """Load extracted users into DuckDB analytics.users_snapshot."""
    file_path: str = context["ti"].xcom_pull(task_ids="extract")

    with open(file_path) as f:
        rows = json.load(f)

    os.unlink(file_path)

    with duckdb.connect(DUCKDB_PATH) as conn:
        conn.execute("CREATE SCHEMA IF NOT EXISTS analytics")
        conn.execute(
            """
            CREATE OR REPLACE TABLE analytics.users_snapshot (
                id              BIGINT,
                stytch_user_id  VARCHAR,
                email           VARCHAR,
                first_name      VARCHAR,
                last_name       VARCHAR,
                is_active       BOOLEAN,
                created_at      TIMESTAMPTZ,
                updated_at      TIMESTAMPTZ,
                snapshotted_at  TIMESTAMPTZ DEFAULT now()
            )
            """
        )
        if rows:
            conn.executemany(
                """
                INSERT INTO analytics.users_snapshot
                    (id, stytch_user_id, email, first_name, last_name,
                     is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        r["id"],
                        r["stytch_user_id"],
                        r["email"],
                        r["first_name"],
                        r["last_name"],
                        r["is_active"],
                        r["created_at"],
                        r["updated_at"],
                    )
                    for r in rows
                ],
            )
        total = conn.execute("SELECT COUNT(*) FROM analytics.users_snapshot").fetchone()[0]
        print(f"Loaded {len(rows)} rows → analytics.users_snapshot (total: {total})")


with DAG(
    dag_id="users_daily_snapshot",
    description="Nightly full snapshot of the users table into DuckDB analytics",
    schedule="0 2 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args=_DEFAULT_ARGS,
    tags=["etl", "users", "snapshot"],
) as dag:
    t_extract = PythonOperator(task_id="extract", python_callable=_extract)
    t_load = PythonOperator(task_id="load", python_callable=_load)

    t_extract >> t_load
