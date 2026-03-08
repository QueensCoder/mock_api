from pydantic import BaseModel, ConfigDict, Field


class ClerkUser(BaseModel):
    """
    Decoded claims from a Clerk session JWT.

    Standard claims: https://clerk.com/docs/backend-requests/handling/manual-jwt
    """

    model_config = ConfigDict(populate_by_name=True)

    # Clerk user ID (format: user_xxxxxxxxxxxxxxxx)
    sub: str

    # Session ID (format: sess_xxxxxxxxxxxxxxxx)
    session_id: str | None = Field(None, alias="sid")

    # OAuth / profile fields — present when Clerk includes them in the token
    email: str | None = None
    email_verified: bool | None = None
    first_name: str | None = None
    last_name: str | None = None
    image_url: str | None = None
    username: str | None = None

    # Org-level claims (present when using Clerk Organizations)
    org_id: str | None = None
    org_role: str | None = None
    org_slug: str | None = None

    @property
    def user_id(self) -> str:
        """Alias for sub — the Clerk user ID."""
        return self.sub

    @property
    def full_name(self) -> str | None:
        parts = filter(None, [self.first_name, self.last_name])
        return " ".join(parts) or None
