"""
audit_log — immutable row-change history, partitioned by month.

Partition key: changed_at  (RANGE, monthly)
Primary key:   (id, changed_at) — partition key must be part of the PK.

Pre-created partitions (see migration 0003):
  audit_log_2026_01 … audit_log_2026_12
  audit_log_2027_01 … audit_log_2027_03

Add new partitions before the window closes:
  CREATE TABLE audit_log_YYYY_MM PARTITION OF audit_log
      FOR VALUES FROM ('YYYY-MM-01') TO ('YYYY-MM+1-01');

Written by application code; never updated or soft-deleted.
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Identity, PrimaryKeyConstraint, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        # Composite PK required — partition key must be included.
        PrimaryKeyConstraint("id", "changed_at"),
        {"postgresql_partition_by": "RANGE (changed_at)"},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True))
    table_name: Mapped[str] = mapped_column(String(100), nullable=False)
    row_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # INSERT | UPDATE | DELETE
    operation: Mapped[str] = mapped_column(String(10), nullable=False)
    old_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    changed_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
