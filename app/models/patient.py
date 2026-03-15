from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuditMixin, Base, PrimaryKeyMixin, TimestampMixin


class Patient(Base, PrimaryKeyMixin, TimestampMixin, AuditMixin):
    """A veterinary visit / medical record for a pet."""

    __tablename__ = "patients"

    pet_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("pets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    condition: Mapped[str] = mapped_column(String(500), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    visited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    pet: Mapped["Pet"] = relationship("Pet")  # noqa: F821
