"""
Integration tests for auth-protected routes.

These tests run against the real FastAPI app via ASGI transport.
No database connection is required — auth routes only call Stytch,
which is mocked via dependency_overrides.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import get_stytch_client
from app.main import app
from tests.conftest import make_stytch_client, make_stytch_error, make_stytch_response

# ── fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
async def authed_client() -> AsyncClient:
    stytch_mock = make_stytch_client(response=make_stytch_response())
    app.dependency_overrides[get_stytch_client] = lambda: stytch_mock
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer valid-session-token"},
    ) as c:
        yield c
    app.dependency_overrides.clear()


# ── helpers ───────────────────────────────────────────────────────────────────


def _override(stytch_mock):
    app.dependency_overrides[get_stytch_client] = lambda: stytch_mock


def _clear():
    app.dependency_overrides.pop(get_stytch_client, None)


# ── /api/v1/auth/verify ───────────────────────────────────────────────────────


class TestAuthVerify:
    async def test_valid_token_returns_200(self, authed_client: AsyncClient):
        resp = await authed_client.get("/api/v1/auth/verify")

        assert resp.status_code == 200
        body = resp.json()
        assert body["valid"] is True
        assert body["user_id"] == "user-test-id"
        assert body["session_id"] == "sess-test-id"
        assert body["email"] == "test@example.com"

    async def test_missing_token_returns_403(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/verify")

        assert resp.status_code == 403

    async def test_expired_token_returns_401_token_expired(self, client: AsyncClient):
        error = make_stytch_error(status_code=401, error_type="session_expired")
        _override(make_stytch_client(raise_error=error))

        try:
            resp = await client.get(
                "/api/v1/auth/verify",
                headers={"Authorization": "Bearer expired-token"},
            )
        finally:
            _clear()

        assert resp.status_code == 401
        assert resp.json()["detail"]["code"] == "TOKEN_EXPIRED"

    async def test_invalid_token_returns_401_token_invalid(self, client: AsyncClient):
        error = make_stytch_error(status_code=401, error_type="session_not_found")
        _override(make_stytch_client(raise_error=error))

        try:
            resp = await client.get(
                "/api/v1/auth/verify",
                headers={"Authorization": "Bearer garbage-token"},
            )
        finally:
            _clear()

        assert resp.status_code == 401
        assert resp.json()["detail"]["code"] == "TOKEN_INVALID"

    async def test_verify_includes_session_expiry(self, authed_client: AsyncClient):
        resp = await authed_client.get("/api/v1/auth/verify")

        assert resp.status_code == 200
        assert resp.json()["session_expires_at"] is not None

    async def test_verify_includes_full_name(self, authed_client: AsyncClient):
        resp = await authed_client.get("/api/v1/auth/verify")

        assert resp.status_code == 200
        assert resp.json()["full_name"] == "Test User"


# ── /api/v1/users/me ──────────────────────────────────────────────────────────


class TestUsersMe:
    async def test_returns_user_profile(self, authed_client: AsyncClient):
        resp = await authed_client.get("/api/v1/users/me")

        assert resp.status_code == 200
        body = resp.json()
        assert body["user_id"] == "user-test-id"
        assert body["email"] == "test@example.com"
        assert body["full_name"] == "Test User"
        assert body["first_name"] == "Test"
        assert body["last_name"] == "User"

    async def test_no_token_returns_403(self, client: AsyncClient):
        resp = await client.get("/api/v1/users/me")

        assert resp.status_code == 403

    async def test_expired_token_returns_401_with_code(self, client: AsyncClient):
        error = make_stytch_error(status_code=401, error_type="session_expired")
        _override(make_stytch_client(raise_error=error))

        try:
            resp = await client.get(
                "/api/v1/users/me",
                headers={"Authorization": "Bearer expired"},
            )
        finally:
            _clear()

        assert resp.status_code == 401
        assert resp.json()["detail"]["code"] == "TOKEN_EXPIRED"

    async def test_revoked_session_returns_401_invalid(self, client: AsyncClient):
        error = make_stytch_error(status_code=401, error_type="session_revoked")
        _override(make_stytch_client(raise_error=error))

        try:
            resp = await client.get(
                "/api/v1/users/me",
                headers={"Authorization": "Bearer revoked"},
            )
        finally:
            _clear()

        assert resp.status_code == 401
        assert resp.json()["detail"]["code"] == "TOKEN_INVALID"


# ── Token refresh workflow ────────────────────────────────────────────────────


class TestRefreshWorkflow:
    """
    Simulates the full client-side session refresh cycle:

        expired token  →  401 TOKEN_EXPIRED
        client calls stytch.session.getTokens() to get a fresh token
        retry with fresh token  →  200
    """

    async def test_expired_then_refreshed_succeeds(self, client: AsyncClient):
        # Step 1: expired token → 401 TOKEN_EXPIRED
        _override(make_stytch_client(raise_error=make_stytch_error(error_type="session_expired")))
        first = await client.get(
            "/api/v1/auth/verify", headers={"Authorization": "Bearer old-token"}
        )
        _clear()

        assert first.status_code == 401
        assert first.json()["detail"]["code"] == "TOKEN_EXPIRED"

        # Step 2: client refreshes via Stytch SDK, retries → 200
        _override(make_stytch_client(response=make_stytch_response()))
        second = await client.get(
            "/api/v1/auth/verify", headers={"Authorization": "Bearer fresh-token"}
        )
        _clear()

        assert second.status_code == 200
        assert second.json()["valid"] is True

    async def test_invalid_session_cannot_be_refreshed(self, client: AsyncClient):
        """TOKEN_INVALID means the session is gone — refresh won't help, must re-login."""
        _override(make_stytch_client(raise_error=make_stytch_error(error_type="session_not_found")))

        try:
            resp = await client.get(
                "/api/v1/auth/verify", headers={"Authorization": "Bearer any-token"}
            )
        finally:
            _clear()

        assert resp.status_code == 401
        assert resp.json()["detail"]["code"] == "TOKEN_INVALID"

    async def test_network_error_returns_401_invalid(self, client: AsyncClient):
        """Non-Stytch errors (network, config) surface as TOKEN_INVALID."""
        _override(make_stytch_client(raise_error=RuntimeError("connection refused")))

        try:
            resp = await client.get(
                "/api/v1/auth/verify", headers={"Authorization": "Bearer any-token"}
            )
        finally:
            _clear()

        assert resp.status_code == 401
        assert resp.json()["detail"]["code"] == "TOKEN_INVALID"
