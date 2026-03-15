from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, PrimaryKeyMixin, TimestampMixin


class User(Base, PrimaryKeyMixin, TimestampMixin, AuditMixin):
    """
    Application user, linked to a Stytch identity via stytch_user_id.

    Soft-deleted via deleted_at — never hard-delete user rows so audit
    trails (created_by, updated_by, deleted_by on other tables) stay intact.
    """

    __tablename__ = "users"

    stytch_user_id: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
