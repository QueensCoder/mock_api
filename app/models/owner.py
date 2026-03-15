from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuditMixin, Base, PrimaryKeyMixin, TimestampMixin


class Owner(Base, PrimaryKeyMixin, TimestampMixin, AuditMixin):
    __tablename__ = "owners"

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    pets: Mapped[list["Pet"]] = relationship(  # noqa: F821
        "Pet", back_populates="owner", lazy="select"
    )
