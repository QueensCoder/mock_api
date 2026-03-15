from pydantic import BaseModel


class UserProfile(BaseModel):
    user_id: str
    email: str | None = None
    full_name: str | None = None
    first_name: str | None = None
    last_name: str | None = None


class VerifyResponse(BaseModel):
    valid: bool
    user_id: str
    session_id: str
    email: str | None = None
    full_name: str | None = None
    session_expires_at: str | None = None
