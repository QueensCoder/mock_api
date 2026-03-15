"""initial schema — users, projects, items

Revision ID: 0001
Revises:
Create Date: 2026-03-15

Conventions
-----------
* Primary keys    — BIGINT GENERATED ALWAYS AS IDENTITY
* Soft deletes    — deleted_at TIMESTAMPTZ NULL  (NULL = live row)
* Audit who       — created_by / updated_by / deleted_by BIGINT NULL
                    (application-level refs to users.id, no FK constraint
                    to avoid circular deps and cascade surprises)
* Timestamps      — all TIMESTAMPTZ (timezone-aware)
* Indexes         — deleted_at on every table (soft-delete filter)
                    email + stytch_user_id on users (lookup)
                    project_id on items (join)
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── users ──────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("stytch_user_id", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=True),
        sa.Column("last_name", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        # timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        # audit who (plain BIGINT — no FK to avoid self-referential circular dep)
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("deleted_by", sa.BigInteger(), nullable=True),
    )
    op.create_index("ix_users_stytch_user_id", "users", ["stytch_user_id"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_deleted_at", "users", ["deleted_at"])

    # ── projects ───────────────────────────────────────────────────────────────
    op.create_table(
        "projects",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        # timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        # audit who
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("deleted_by", sa.BigInteger(), nullable=True),
    )
    op.create_index("ix_projects_deleted_at", "projects", ["deleted_at"])

    # ── items ──────────────────────────────────────────────────────────────────
    op.create_table(
        "items",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column(
            "project_id",
            sa.BigInteger(),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        # timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        # audit who
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("deleted_by", sa.BigInteger(), nullable=True),
    )
    op.create_index("ix_items_project_id", "items", ["project_id"])
    op.create_index("ix_items_deleted_at", "items", ["deleted_at"])


def downgrade() -> None:
    op.drop_table("items")
    op.drop_table("projects")
    op.drop_table("users")
