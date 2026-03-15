from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from stytch import Client

from app.core.auth import AuthError, TokenExpiredError, get_stytch_client, verify_stytch_session
from app.schemas.auth import StytchUser

_bearer = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    stytch: Client = Depends(get_stytch_client),
) -> StytchUser:
    """
    Verify the Stytch session token from the Authorization header.

    The TypeScript client sends:
        Authorization: Bearer <stytch_session_token>

    On success — returns a populated StytchUser.

    On failure — returns a structured 401 the client can act on:
        code=TOKEN_EXPIRED  → call stytch.session.getTokens() then retry
        code=TOKEN_INVALID  → session is gone, redirect to login
    """
    try:
        data = await verify_stytch_session(credentials.credentials, stytch)
        return StytchUser(**data)
    except TokenExpiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "TOKEN_EXPIRED", "message": str(exc)},
            headers={"WWW-Authenticate": "Bearer"},
        )
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "TOKEN_INVALID", "message": str(exc)},
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_org_role(*roles: str):
    """
    Factory dependency that gates access by org role.

    Usage:
        @router.delete("/resource", dependencies=[Depends(require_org_role("admin"))])
    """

    async def _check(user: StytchUser = Depends(get_current_user)) -> StytchUser:
        user_role = getattr(user, "org_role", None)
        if user_role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "INSUFFICIENT_ROLE", "message": "Insufficient role"},
            )
        return user

    return _check
