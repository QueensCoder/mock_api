from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.schemas.auth import ClerkUser

router = APIRouter()


@router.get("/me")
async def get_me(user: ClerkUser = Depends(get_current_user)) -> dict:
    """Return the authenticated user's profile from their Clerk session token."""
    return {
        "user_id": user.user_id,
        "email": user.email,
        "full_name": user.full_name,
        "username": user.username,
        "org_id": user.org_id,
        "org_role": user.org_role,
    }
