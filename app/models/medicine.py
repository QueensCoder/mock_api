from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, PrimaryKeyMixin, TimestampMixin


class Medicine(Base, PrimaryKeyMixin, TimestampMixin, AuditMixin):
    __tablename__ = "medicines"

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    dosage: Mapped[str | None] = mapped_column(String(100), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
