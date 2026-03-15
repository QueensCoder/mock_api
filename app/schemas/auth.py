from datetime import datetime

from pydantic import BaseModel


class StytchUser(BaseModel):
    """
    Normalised user model built from a Stytch session authenticate response.
    """

    user_id: str
    session_id: str
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    session_expires_at: datetime | None = None

    # Refreshed tokens returned by Stytch on every authenticate call
    session_token: str | None = None
    session_jwt: str | None = None

    @property
    def full_name(self) -> str | None:
        parts = filter(None, [self.first_name, self.last_name])
        return " ".join(parts) or None
