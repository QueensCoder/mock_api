"""
Shared test fixtures — no DB connections here.
DB fixtures live in tests/integration/conftest.py so unit tests
don't require a running postgres.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from stytch.core.response_base import StytchError, StytchErrorDetails

from app.core.auth import get_stytch_client
from app.main import app


# ── Stytch error factory ──────────────────────────────────────────────────────


def make_stytch_error(status_code: int = 401, error_type: str = "session_expired") -> StytchError:
    """Build a real StytchError that can be raised in tests."""
    details = StytchErrorDetails.model_validate(
        {
            "status_code": status_code,
            "request_id": "test-request-id",
            "error_type": error_type,
            "error_message": f"Test: {error_type}",
        }
    )
    return StytchError(details)


# ── Stytch response factory ───────────────────────────────────────────────────


def make_stytch_response(
    user_id: str = "user-test-id",
    session_id: str = "sess-test-id",
    email: str = "test@example.com",
    first_name: str = "Test",
    last_name: str = "User",
) -> MagicMock:
    """
    Build a MagicMock mirroring a Stytch sessions.authenticate_async() response.

    Uses correct Stytch SDK field names:
        Email.email  (not email_address)
        Name.first_name / Name.last_name
        Session.session_id / Session.expires_at
    """
    email_obj = MagicMock()
    email_obj.email = email

    name_obj = MagicMock()
    name_obj.first_name = first_name
    name_obj.last_name = last_name

    user = MagicMock()
    user.user_id = user_id
    user.emails = [email_obj]
    user.name = name_obj

    session = MagicMock()
    session.session_id = session_id
    session.expires_at = datetime(2030, 1, 1, tzinfo=timezone.utc)

    resp = MagicMock()
    resp.user = user
    resp.session = session
    resp.session_token = "fresh-session-token"
    resp.session_jwt = "fresh.session.jwt"
    return resp


def make_stytch_client(
    response: MagicMock | None = None,
    raise_error: Exception | None = None,
) -> MagicMock:
    """Build a mock Stytch Client with sessions.authenticate_async stubbed out."""
    client = MagicMock()
    if raise_error is not None:
        client.sessions.authenticate_async = AsyncMock(side_effect=raise_error)
    else:
        client.sessions.authenticate_async = AsyncMock(
            return_value=response or make_stytch_response()
        )
    return client


# ── Unauthenticated client (no DB, no Stytch) ────────────────────────────────


@pytest.fixture
def override_stytch():
    """
    Context helper: temporarily override the Stytch client dependency.
    Usage:
        with override_stytch(make_stytch_client(raise_error=...)):
            ...
    """

    class _Override:
        def __enter__(self, mock):
            app.dependency_overrides[get_stytch_client] = lambda: mock
            return mock

        def __exit__(self, *_):
            app.dependency_overrides.pop(get_stytch_client, None)

    return _Override()
