"""add clinic tables — owners, pets, patients, medicines

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-15

Tables
------
* owners   — pet owner contact info
* pets     — pet profile, FK → owners
* patients — vet visit record, FK → pets
* medicines — drug/treatment catalogue
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _audit_cols() -> list:
    """Shared audit + timestamp columns added to every table."""
    return [
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
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("deleted_by", sa.BigInteger(), nullable=True),
    ]


def upgrade() -> None:
    # ── owners ─────────────────────────────────────────────────────────────────
    op.create_table(
        "owners",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(50), nullable=True),
        *_audit_cols(),
    )
    op.create_index("ix_owners_email", "owners", ["email"], unique=True)
    op.create_index("ix_owners_deleted_at", "owners", ["deleted_at"])

    # ── pets ───────────────────────────────────────────────────────────────────
    op.create_table(
        "pets",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column(
            "owner_id",
            sa.BigInteger(),
            sa.ForeignKey("owners.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("species", sa.String(50), nullable=False),
        sa.Column("breed", sa.String(100), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        *_audit_cols(),
    )
    op.create_index("ix_pets_owner_id", "pets", ["owner_id"])
    op.create_index("ix_pets_deleted_at", "pets", ["deleted_at"])

    # ── patients ───────────────────────────────────────────────────────────────
    op.create_table(
        "patients",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column(
            "pet_id",
            sa.BigInteger(),
            sa.ForeignKey("pets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("condition", sa.String(500), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("visited_at", sa.DateTime(timezone=True), nullable=False),
        *_audit_cols(),
    )
    op.create_index("ix_patients_pet_id", "patients", ["pet_id"])
    op.create_index("ix_patients_deleted_at", "patients", ["deleted_at"])

    # ── medicines ──────────────────────────────────────────────────────────────
    op.create_table(
        "medicines",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("dosage", sa.String(100), nullable=True),
        sa.Column("unit", sa.String(50), nullable=True),
        *_audit_cols(),
    )
    op.create_index("ix_medicines_name", "medicines", ["name"], unique=True)
    op.create_index("ix_medicines_deleted_at", "medicines", ["deleted_at"])


def downgrade() -> None:
    op.drop_table("patients")
    op.drop_table("pets")
    op.drop_table("owners")
    op.drop_table("medicines")
