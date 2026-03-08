import logging
import time
from typing import Any

import httpx
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError

from app.core.config import settings

logger = logging.getLogger(__name__)

# Simple in-memory JWKS cache — refreshed every hour or on unknown kid
_jwks_cache: dict[str, Any] = {"keys": [], "fetched_at": 0.0}
_JWKS_TTL = 3600  # seconds


async def _fetch_jwks(force: bool = False) -> list[dict]:
    now = time.monotonic()
    if not force and _jwks_cache["keys"] and now - _jwks_cache["fetched_at"] < _JWKS_TTL:
        return _jwks_cache["keys"]

    if not settings.CLERK_JWKS_URL:
        raise RuntimeError("CLERK_JWKS_URL is not configured")

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(settings.CLERK_JWKS_URL)
        resp.raise_for_status()
        keys = resp.json().get("keys", [])

    _jwks_cache["keys"] = keys
    _jwks_cache["fetched_at"] = now
    logger.debug("JWKS refreshed — %d key(s) loaded", len(keys))
    return keys


def _find_key(keys: list[dict], kid: str) -> dict | None:
    return next((k for k in keys if k.get("kid") == kid), None)


async def verify_clerk_token(token: str) -> dict:
    """
    Verify a Clerk session JWT and return its decoded payload.

    Raises ValueError on any verification failure so callers can map it
    to an HTTP 401 without leaking internal details.
    """
    try:
        header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise ValueError("Malformed token") from exc

    kid = header.get("kid")
    if not kid:
        raise ValueError("Token header missing kid")

    keys = await _fetch_jwks()
    key = _find_key(keys, kid)

    if key is None:
        # Key not in cache — possible rotation; refresh once and retry
        keys = await _fetch_jwks(force=True)
        key = _find_key(keys, kid)

    if key is None:
        raise ValueError("No matching public key found for token")

    decode_options: dict[str, Any] = {"verify_aud": False}
    issuer = settings.CLERK_ISSUER or None

    try:
        payload: dict = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            options=decode_options,
            issuer=issuer,
        )
    except ExpiredSignatureError as exc:
        raise ValueError("Token has expired") from exc
    except JWTError as exc:
        raise ValueError(f"Token verification failed: {exc}") from exc

    return payload
