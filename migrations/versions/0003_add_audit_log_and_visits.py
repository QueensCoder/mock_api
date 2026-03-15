"""add audit_log (monthly) and visits (yearly) partitioned tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-15

Partitioning notes
------------------
Both tables use RANGE partitioning; the partition key must be part of the PK.

audit_log   — partitioned by changed_at (monthly)
              PK: (id, changed_at)
              Pre-created: 2026-01 → 2026-12, 2027-01 → 2027-03
              Add new partitions before the window closes:
                CREATE TABLE audit_log_YYYY_MM PARTITION OF audit_log
                    FOR VALUES FROM ('YYYY-MM-01') TO ('YYYY-MM+1-01');

visits      — partitioned by visited_at (yearly)
              PK: (id, visited_at)
              Pre-created: 2025, 2026, 2027
              Add new partitions before the year turns:
                CREATE TABLE visits_YYYY PARTITION OF visits
                    FOR VALUES FROM ('YYYY-01-01') TO ('YYYY+1-01-01');

Why raw SQL?
Alembic/SQLAlchemy do not emit PARTITION BY clauses via op.create_table().
We use op.execute() so the DDL is explicit and version-controlled.
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


# ── Helpers ────────────────────────────────────────────────────────────────────


def _month_plus_one(year: int, month: int) -> tuple[int, int]:
    return (year, month + 1) if month < 12 else (year + 1, 1)


# ── Upgrade ────────────────────────────────────────────────────────────────────


def upgrade() -> None:
    # ── audit_log parent ───────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE audit_log (
            id          BIGINT GENERATED ALWAYS AS IDENTITY,
            table_name  VARCHAR(100)              NOT NULL,
            row_id      BIGINT                    NOT NULL,
            operation   VARCHAR(10)               NOT NULL
                            CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
            old_data    JSONB,
            new_data    JSONB,
            changed_by  BIGINT,
            changed_at  TIMESTAMPTZ               NOT NULL,
            PRIMARY KEY (id, changed_at)
        ) PARTITION BY RANGE (changed_at)
    """)

    # Indexes on the parent propagate automatically to all partitions (PG 11+).
    op.execute("CREATE INDEX ix_audit_log_table_row ON audit_log (table_name, row_id)")
    op.execute("CREATE INDEX ix_audit_log_changed_at ON audit_log (changed_at)")
    op.execute("CREATE INDEX ix_audit_log_changed_by ON audit_log (changed_by)")

    # Monthly partitions — all of 2026 + Q1 2027
    months = [(2026, m) for m in range(1, 13)] + [(2027, m) for m in range(1, 4)]
    for year, month in months:
        ny, nm = _month_plus_one(year, month)
        op.execute(f"""
            CREATE TABLE audit_log_{year}_{month:02d} PARTITION OF audit_log
                FOR VALUES FROM ('{year}-{month:02d}-01') TO ('{ny}-{nm:02d}-01')
        """)

    # ── visits parent ──────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE visits (
            id          BIGINT GENERATED ALWAYS AS IDENTITY,
            pet_id      BIGINT                    NOT NULL
                            REFERENCES pets(id)    ON DELETE CASCADE,
            owner_id    BIGINT                    NOT NULL
                            REFERENCES owners(id)  ON DELETE RESTRICT,
            visited_at  TIMESTAMPTZ               NOT NULL,
            reason      VARCHAR(500),
            notes       TEXT,
            status      VARCHAR(50)               NOT NULL DEFAULT 'scheduled'
                            CHECK (status IN ('scheduled','completed','cancelled','no_show')),
            created_at  TIMESTAMPTZ               NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ               NOT NULL DEFAULT now(),
            deleted_at  TIMESTAMPTZ,
            created_by  BIGINT,
            updated_by  BIGINT,
            deleted_by  BIGINT,
            PRIMARY KEY (id, visited_at)
        ) PARTITION BY RANGE (visited_at)
    """)

    op.execute("CREATE INDEX ix_visits_pet_id    ON visits (pet_id)")
    op.execute("CREATE INDEX ix_visits_owner_id  ON visits (owner_id)")
    op.execute("CREATE INDEX ix_visits_visited_at ON visits (visited_at)")
    op.execute("CREATE INDEX ix_visits_deleted_at ON visits (deleted_at)")
    op.execute("CREATE INDEX ix_visits_status    ON visits (status)")

    # Yearly partitions — 2025 through 2027
    for year in (2025, 2026, 2027):
        op.execute(f"""
            CREATE TABLE visits_{year} PARTITION OF visits
                FOR VALUES FROM ('{year}-01-01') TO ('{year + 1}-01-01')
        """)


# ── Downgrade ──────────────────────────────────────────────────────────────────


def downgrade() -> None:
    # Drop child partitions first, then the parent.
    for year in (2025, 2026, 2027):
        op.execute(f"DROP TABLE IF EXISTS visits_{year}")
    op.execute("DROP TABLE IF EXISTS visits")

    months = [(2026, m) for m in range(1, 13)] + [(2027, m) for m in range(1, 4)]
    for year, month in months:
        op.execute(f"DROP TABLE IF EXISTS audit_log_{year}_{month:02d}")
    op.execute("DROP TABLE IF EXISTS audit_log")
