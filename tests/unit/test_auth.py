"""Unit tests for app.core.auth — exercises verify_stytch_session directly."""

import pytest

from app.core.auth import TokenExpiredError, TokenInvalidError, verify_stytch_session
from tests.conftest import make_stytch_client, make_stytch_error, make_stytch_response


class TestVerifyStytchSession:
    async def test_valid_token_returns_user_dict(self):
        resp = make_stytch_response(
            user_id="user-abc",
            session_id="sess-abc",
            email="alice@example.com",
            first_name="Alice",
            last_name="Smith",
        )
        client = make_stytch_client(response=resp)

        result = await verify_stytch_session("valid-token", client)

        assert result["user_id"] == "user-abc"
        assert result["session_id"] == "sess-abc"
        assert result["email"] == "alice@example.com"
        assert result["first_name"] == "Alice"
        assert result["last_name"] == "Smith"
        assert result["session_token"] == "fresh-session-token"

    async def test_calls_stytch_with_provided_token(self):
        client = make_stytch_client()

        await verify_stytch_session("my-session-token", client)

        client.sessions.authenticate_async.assert_called_once_with(
            session_token="my-session-token"
        )

    async def test_expired_session_raises_token_expired_error(self):
        error = make_stytch_error(status_code=401, error_type="session_expired")
        client = make_stytch_client(raise_error=error)

        with pytest.raises(TokenExpiredError):
            await verify_stytch_session("expired-token", client)

    async def test_session_not_found_raises_token_invalid_error(self):
        error = make_stytch_error(status_code=401, error_type="session_not_found")
        client = make_stytch_client(raise_error=error)

        with pytest.raises(TokenInvalidError):
            await verify_stytch_session("bad-token", client)

    async def test_revoked_session_raises_token_invalid_error(self):
        error = make_stytch_error(status_code=401, error_type="session_revoked")
        client = make_stytch_client(raise_error=error)

        with pytest.raises(TokenInvalidError):
            await verify_stytch_session("revoked-token", client)

    async def test_invalid_session_token_raises_token_invalid_error(self):
        error = make_stytch_error(status_code=401, error_type="invalid_session_token")
        client = make_stytch_client(raise_error=error)

        with pytest.raises(TokenInvalidError):
            await verify_stytch_session("invalid-token", client)

    async def test_unexpected_error_raises_token_invalid_error(self):
        client = make_stytch_client(raise_error=RuntimeError("network failure"))

        with pytest.raises(TokenInvalidError):
            await verify_stytch_session("any-token", client)

    async def test_user_with_no_emails_returns_none_email(self):
        resp = make_stytch_response()
        resp.user.emails = []
        client = make_stytch_client(response=resp)

        result = await verify_stytch_session("valid-token", client)

        assert result["email"] is None

    async def test_user_with_no_name_returns_none_name_fields(self):
        resp = make_stytch_response()
        resp.user.name = None
        client = make_stytch_client(response=resp)

        result = await verify_stytch_session("valid-token", client)

        assert result["first_name"] is None
        assert result["last_name"] is None

    async def test_user_with_empty_name_strings_returns_none(self):
        resp = make_stytch_response(first_name="", last_name="")
        client = make_stytch_client(response=resp)

        result = await verify_stytch_session("valid-token", client)

        assert result["first_name"] is None
        assert result["last_name"] is None
