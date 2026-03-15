from datetime import date

from sqlalchemy import BigInteger, Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuditMixin, Base, PrimaryKeyMixin, TimestampMixin


class Pet(Base, PrimaryKeyMixin, TimestampMixin, AuditMixin):
    __tablename__ = "pets"

    owner_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("owners.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    species: Mapped[str] = mapped_column(String(50), nullable=False)  # dog, cat, bird, …
    breed: Mapped[str | None] = mapped_column(String(100), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)

    owner: Mapped["Owner"] = relationship("Owner", back_populates="pets")  # noqa: F821
