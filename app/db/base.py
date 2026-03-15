from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Identity, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class PrimaryKeyMixin:
    """
    BIGINT primary key backed by PostgreSQL GENERATED ALWAYS AS IDENTITY.

    Prefer BIGINT over SERIAL/BIGSERIAL: Identity() is the SQL-standard way,
    works correctly with Alembic, and does not expose a sequence name.
    """

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)


class TimestampMixin:
    """
    Audit timestamps present on every table.

    created_at  — set once on INSERT, never changes.
    updated_at  — mirrors created_at on INSERT; refreshed by SQLAlchemy on UPDATE.
                  Use a DB trigger if you need server-side enforcement.
    deleted_at  — NULL means the row is live; non-NULL means soft-deleted.
                  All queries should filter WHERE deleted_at IS NULL by default.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,  # queries filtering soft-deleted rows are common and should be fast
    )


class AuditMixin:
    """
    User ID references for every mutation.

    Stored as plain BIGINT rather than FK-constrained columns to avoid:
      - Circular dependency (users.created_by → users.id)
      - Cascade delete surprises on user deactivation
    Referential integrity is enforced at the application layer.
    """

    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    deleted_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
