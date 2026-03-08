from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.auth import verify_clerk_token
from app.schemas.auth import ClerkUser

_bearer = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> ClerkUser:
    """
    Resolve and verify the Clerk session JWT from the Authorization header.

    The TypeScript client should attach the token as:
        Authorization: Bearer <clerk_session_token>

    Raises 401 if the token is missing, expired, or invalid.
    """
    try:
        payload = await verify_clerk_token(credentials.credentials)
        return ClerkUser.model_validate(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_org_role(*roles: str):
    """
    Factory dependency that enforces a minimum Clerk org role.

    Usage:
        @router.get("/admin", dependencies=[Depends(require_org_role("org:admin"))])
    """

    async def _check(user: ClerkUser = Depends(get_current_user)) -> ClerkUser:
        if user.org_role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient organisation role",
            )
        return user

    return _check
