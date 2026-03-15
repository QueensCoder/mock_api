import logging
from functools import lru_cache

from stytch import Client
from stytch.core.response_base import StytchError

from app.core.config import settings

logger = logging.getLogger(__name__)


# ── Exceptions ────────────────────────────────────────────────────────────────


class AuthError(Exception):
    """Base authentication error."""


class TokenExpiredError(AuthError):
    """Session has expired — client should call stytch.session.getTokens() and retry."""


class TokenInvalidError(AuthError):
    """Session is invalid or not found — client should redirect to login."""


# ── Stytch client ─────────────────────────────────────────────────────────────

# Stytch error_type values that mean the session is permanently gone (re-login required)
_INVALID_SESSION_TYPES = frozenset(
    {
        "session_not_found",
        "session_revoked",
        "invalid_session_token",
        "unauthorized_credentials",
    }
)


@lru_cache(maxsize=1)
def get_stytch_client() -> Client:
    """
    Singleton Stytch client.  Cached after first call.

    Override via FastAPI dependency_overrides in tests:
        app.dependency_overrides[get_stytch_client] = lambda: mock_client
    """
    return Client(
        project_id=settings.STYTCH_PROJECT_ID,
        secret=settings.STYTCH_SECRET,
        suppress_warnings=True,
    )


# ── Session verification ──────────────────────────────────────────────────────


async def verify_stytch_session(session_token: str, client: Client) -> dict:
    """
    Authenticate a Stytch session token and return a normalised user dict.

    Raises:
        TokenExpiredError:  session is expired — client should refresh and retry.
        TokenInvalidError:  token is invalid / session gone — client must re-login.
    """
    try:
        resp = await client.sessions.authenticate_async(session_token=session_token)
    except StytchError as exc:
        error_type: str = exc.details.error_type or ""
        if error_type in _INVALID_SESSION_TYPES:
            raise TokenInvalidError(f"Session invalid: {error_type}") from exc
        raise TokenExpiredError(f"Session expired: {error_type}") from exc
    except Exception as exc:
        raise TokenInvalidError("Session authentication failed") from exc

    return _map_response(resp)


def _map_response(resp) -> dict:
    """Flatten a Stytch AuthenticateResponse into a plain dict."""
    user = resp.user
    session = resp.session

    emails = user.emails or []
    primary_email = emails[0].email if emails else None

    name = user.name
    first_name = (getattr(name, "first_name", None) or "") or None
    last_name = (getattr(name, "last_name", None) or "") or None

    return {
        "user_id": user.user_id,
        "session_id": session.session_id,
        "email": primary_email,
        "first_name": first_name,
        "last_name": last_name,
        "session_expires_at": session.expires_at,
        "session_token": resp.session_token,
        "session_jwt": resp.session_jwt,
    }
