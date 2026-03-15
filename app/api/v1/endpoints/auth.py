from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.schemas.auth import StytchUser

router = APIRouter()


@router.get("/verify")
async def verify_session(user: StytchUser = Depends(get_current_user)) -> dict:
    """
    Validate the caller's Stytch session token and return session metadata.

    Use this endpoint for proactive token health checks and to drive the
    client-side refresh workflow:

    Token refresh workflow
    ─────────────────────
    1. Any API route returns:
           401 { "code": "TOKEN_EXPIRED" }
    2. Client calls Stytch to refresh:
           const { session_token } = await stytch.sessions.authenticate()
       or for browser SDK:
           await stytch.session.getTokens()
    3. Client retries the original request with the new session_token.
    4. If /auth/verify itself returns:
           401 { "code": "TOKEN_INVALID" }
       the session no longer exists in Stytch — redirect the user to login.

    Returns 200 with session info when valid.
    Returns 401 (via get_current_user) when expired or invalid.
    """
    return {
        "valid": True,
        "user_id": user.user_id,
        "session_id": user.session_id,
        "email": user.email,
        "full_name": user.full_name,
        "session_expires_at": user.session_expires_at.isoformat() if user.session_expires_at else None,
    }
