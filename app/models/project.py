from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuditMixin, Base, PrimaryKeyMixin, TimestampMixin


class Project(Base, PrimaryKeyMixin, TimestampMixin, AuditMixin):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    items: Mapped[list["Item"]] = relationship(  # noqa: F821
        "Item", back_populates="project", lazy="select"
    )
