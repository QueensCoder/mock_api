from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.schemas.auth import StytchUser
from app.schemas.users import UserProfile

router = APIRouter()


@router.get("/me", response_model=UserProfile)
async def get_me(user: StytchUser = Depends(get_current_user)):
    """Return the authenticated user's profile from their Stytch session."""
    return {
        "user_id": user.user_id,
        "email": user.email,
        "full_name": user.full_name,
        "first_name": user.first_name,
        "last_name": user.last_name,
    }
