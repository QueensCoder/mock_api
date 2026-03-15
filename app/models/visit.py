"""
visits — vet appointment records, partitioned by year.

Partition key: visited_at  (RANGE, yearly)
Primary key:   (id, visited_at) — partition key must be part of the PK.

Pre-created partitions (see migration 0003):
  visits_2025, visits_2026, visits_2027

Add new partitions before the year turns:
  CREATE TABLE visits_YYYY PARTITION OF visits
      FOR VALUES FROM ('YYYY-01-01') TO ('YYYY+1-01-01');

Denormalises owner_id alongside pet_id so queries can filter by either
without joining through pets. Both FKs are non-partitioned tables so the
references work on Postgres 12+.
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Identity,
    PrimaryKeyConstraint,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Visit(Base):
    __tablename__ = "visits"
    __table_args__ = (
        PrimaryKeyConstraint("id", "visited_at"),
        {"postgresql_partition_by": "RANGE (visited_at)"},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True))

    pet_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("pets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("owners.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    visited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # scheduled | completed | cancelled | no_show
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default="scheduled",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    # Audit who
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    deleted_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    pet: Mapped["Pet"] = relationship("Pet")  # noqa: F821
    owner: Mapped["Owner"] = relationship("Owner")  # noqa: F821
