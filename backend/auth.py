from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, Request, Response, status
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash

from .config import AUTH_COOKIE_SECURE, AUTH_SECRET, AUTH_TOKEN_TTL_HOURS
from .database import connect

AUTH_COOKIE_NAME = "synergy_session"
AUTH_ALGORITHM = "HS256"
AUTH_ISSUER = "synergy-poc"
AUTH_AUDIENCE = "synergy-web"

password_hash = PasswordHash.recommended()
_DUMMY_HASH = password_hash.hash("synergy-dummy-password-for-timing-protection")


@dataclass(frozen=True)
class AuthenticatedUser:
    id: str
    email: str
    name: str


def validate_auth_configuration() -> None:
    if len(AUTH_SECRET) < 32:
        raise RuntimeError("AUTH_SECRET must contain at least 32 characters.")
    if AUTH_TOKEN_TTL_HOURS <= 0:
        raise RuntimeError("AUTH_TOKEN_TTL_HOURS must be greater than zero.")


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("Passwords must contain at least 12 characters.")
    return password_hash.hash(password)


def authenticate_user(email: str, password: str) -> AuthenticatedUser | None:
    normalized_email = email.strip().casefold()
    with connect() as db:
        row = db.execute(
            "SELECT id, email, name, password_hash, is_active FROM users WHERE email = ? COLLATE NOCASE",
            (normalized_email,),
        ).fetchone()
    if not row:
        password_hash.verify(password, _DUMMY_HASH)
        return None
    if not password_hash.verify(password, row["password_hash"]):
        return None
    if not row["is_active"]:
        return None
    return AuthenticatedUser(id=row["id"], email=row["email"], name=row["name"])


def _create_token(user: AuthenticatedUser) -> str:
    validate_auth_configuration()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user.id,
        "iat": now,
        "exp": now + timedelta(hours=AUTH_TOKEN_TTL_HOURS),
        "iss": AUTH_ISSUER,
        "aud": AUTH_AUDIENCE,
    }
    return jwt.encode(payload, AUTH_SECRET, algorithm=AUTH_ALGORITHM)


def set_session_cookie(response: Response, user: AuthenticatedUser) -> None:
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=_create_token(user),
        max_age=AUTH_TOKEN_TTL_HOURS * 60 * 60,
        path="/api",
        secure=AUTH_COOKIE_SECURE,
        httponly=True,
        samesite="strict",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=AUTH_COOKIE_NAME,
        path="/api",
        secure=AUTH_COOKIE_SECURE,
        httponly=True,
        samesite="strict",
    )


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
    )


def get_current_user(request: Request) -> AuthenticatedUser:
    token = request.cookies.get(AUTH_COOKIE_NAME)
    if not token:
        raise _unauthorized()
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            AUTH_SECRET,
            algorithms=[AUTH_ALGORITHM],
            audience=AUTH_AUDIENCE,
            issuer=AUTH_ISSUER,
        )
        user_id = payload.get("sub")
        if not isinstance(user_id, str) or not user_id:
            raise _unauthorized()
    except (InvalidTokenError, RuntimeError):
        raise _unauthorized() from None

    with connect() as db:
        row = db.execute(
            "SELECT id, email, name FROM users WHERE id = ? AND is_active = 1",
            (user_id,),
        ).fetchone()
    if not row:
        raise _unauthorized()
    return AuthenticatedUser(id=row["id"], email=row["email"], name=row["name"])


def public_user(user: AuthenticatedUser) -> dict[str, str]:
    return {"id": user.id, "email": user.email, "name": user.name}


CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
