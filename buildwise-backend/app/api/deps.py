"""Shared API dependencies."""

from __future__ import annotations

import logging
import time
import uuid

import httpx
from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.models.user import User

logger = logging.getLogger(__name__)

# JWKS cache with TTL (1 hour)
_jwks_cache: dict | None = None
_jwks_fetched_at: float = 0.0
_JWKS_TTL_SECONDS = 3600


async def _get_jwks(force_refresh: bool = False) -> dict:
    """Fetch and cache Auth0 JWKS (JSON Web Key Set) with TTL."""
    global _jwks_cache, _jwks_fetched_at
    now = time.monotonic()
    if _jwks_cache is not None and not force_refresh and (now - _jwks_fetched_at) < _JWKS_TTL_SECONDS:
        return _jwks_cache

    jwks_url = f"https://{settings.auth0_domain}/.well-known/jwks.json"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(jwks_url)
        resp.raise_for_status()
        _jwks_cache = resp.json()
        _jwks_fetched_at = now
    return _jwks_cache


def _find_rsa_key(jwks: dict, token: str) -> dict | None:
    """Find the RSA key matching the token's kid header."""
    unverified_header = jwt.get_unverified_header(token)
    kid = unverified_header.get("kid")
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return {
                "kty": key["kty"],
                "kid": key["kid"],
                "use": key["use"],
                "n": key["n"],
                "e": key["e"],
            }
    return None


async def _verify_jwt(token: str) -> dict:
    """Verify Auth0 JWT and return payload claims.

    Raises HTTPException on any verification failure.
    """
    try:
        jwks = await _get_jwks()
    except httpx.HTTPError as exc:
        logger.error("Failed to fetch Auth0 JWKS: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth service unavailable",
        )

    rsa_key = _find_rsa_key(jwks, token)

    # Key miss: force refresh JWKS once (Auth0 may have rotated keys)
    if rsa_key is None:
        try:
            jwks = await _get_jwks(force_refresh=True)
            rsa_key = _find_rsa_key(jwks, token)
        except httpx.HTTPError:
            pass

    if rsa_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token signing key",
        )

    try:
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=settings.auth0_algorithms,
            audience=settings.auth0_api_audience,
            issuer=f"https://{settings.auth0_domain}/",
        )
        return payload
    except JWTError as exc:
        logger.warning("JWT verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


async def _get_or_create_user(
    db: AsyncSession,
    auth0_sub: str,
    email: str | None,
    name: str | None,
) -> User:
    """Find user by auth0_sub, or create on first login."""
    result = await db.execute(select(User).where(User.auth0_sub == auth0_sub))
    user = result.scalar_one_or_none()

    if user is not None:
        return user

    # Auto-create user on first Auth0 login
    user = User(
        auth0_sub=auth0_sub,
        email=email or f"{auth0_sub}@auth0.user",
        name=name,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    logger.info("Auto-created user: sub=%s email=%s", auth0_sub, email)
    return user


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate authentication, return the User row.

    Supports two modes:
    1. Auth0 JWT: Authorization: Bearer <token> header
    2. Dev mode: X-User-Id header (only when AUTH0_DOMAIN is not configured)
    """
    auth_header = request.headers.get("Authorization", "")

    # --- Mode 1: Auth0 JWT ---
    if auth_header.startswith("Bearer "):
        if not settings.auth0_domain:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Auth0 not configured on server",
            )

        token = auth_header[7:]  # Strip "Bearer "
        payload = await _verify_jwt(token)

        sub = payload.get("sub")
        if not sub:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing 'sub' claim",
            )

        # Extract email/name from token claims (Auth0 includes these in ID tokens)
        email = payload.get("email") or payload.get(f"https://{settings.auth0_domain}/email")
        name = payload.get("name") or payload.get(f"https://{settings.auth0_domain}/name")

        user = await _get_or_create_user(db, sub, email, name)
        return user

    # --- Mode 2: Dev fallback (X-User-Id header) ---
    # Only available when BOTH auth0 is unconfigured AND debug mode is on
    if not settings.auth0_domain and settings.debug:
        user_id_header = request.headers.get("X-User-Id")
        if not user_id_header:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authentication",
            )

        try:
            user_id = uuid.UUID(user_id_header)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user id",
            )

        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )
        return user

    # No valid auth provided
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing or invalid Authorization header",
    )
