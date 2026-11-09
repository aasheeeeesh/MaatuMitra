"""JWT mock issuer + verifier (PyJWT). HS256 pinned; exp/iat/iss/aud verified; sub, role, fid required.

The role used for database access comes ONLY from a verified token (and must also match the
synthetic directory). It is never read from a request body, header or query string.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

import jwt

from .config import Settings
from .directory import APP_ROLES, Directory, DirectoryUser

ALGORITHM = "HS256"  # pinned; never taken from the token header
MAX_TOKEN_LEN = 4096
MAX_TTL_SECONDS = 900
REQUIRED_CLAIMS = ["exp", "iat", "iss", "aud", "sub", "role", "fid"]


class AuthError(Exception):
    """Any authentication failure. The message is never shown to clients."""


@dataclass(frozen=True)
class Principal:
    user_id: uuid.UUID
    role: str
    facility_id: uuid.UUID


def _key(settings: Settings) -> str:
    k = settings.jwt_signing_key
    if not k or k.startswith("REPLACE_ME") or len(k) < 32:
        raise ValueError("JWT_SIGNING_KEY missing or too short (need >= 32 chars, use 64 hex)")
    return k


def issue_token(
    settings: Settings, user: DirectoryUser, now: float | None = None, ttl: int | None = None
) -> str:
    now = time.time() if now is None else now
    ttl = min(ttl or settings.jwt_ttl_seconds, MAX_TTL_SECONDS)
    claims = {
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "sub": str(user.id),
        "role": user.role,
        "fid": str(user.facility_id),
        "iat": int(now),
        "exp": int(now) + ttl,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(claims, _key(settings), algorithm=ALGORITHM)


def verify_token(settings: Settings, token: str, directory: Directory) -> Principal:
    if not isinstance(token, str) or not token or len(token) > MAX_TOKEN_LEN:
        raise AuthError("bad token")
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") != ALGORITHM:  # belt and braces; decode() also pins it
            raise AuthError("alg")
        claims = jwt.decode(
            token,
            _key(settings),
            algorithms=[ALGORITHM],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            leeway=0,
            options={"require": REQUIRED_CLAIMS, "verify_exp": True, "verify_iat": True},
        )
    except AuthError:
        raise
    except (jwt.PyJWTError, ValueError, TypeError) as exc:
        raise AuthError("invalid") from exc
    if claims["exp"] - claims["iat"] > MAX_TTL_SECONDS:
        raise AuthError("ttl")
    role = claims["role"]
    if role not in APP_ROLES:
        raise AuthError("role")
    try:
        sub = uuid.UUID(str(claims["sub"]))
        fid = uuid.UUID(str(claims["fid"]))
    except ValueError as exc:
        raise AuthError("sub/fid") from exc
    user = directory.get(sub)
    if user is None or user.role != role or user.facility_id != fid:
        raise AuthError("directory mismatch")
    return Principal(user_id=sub, role=role, facility_id=fid)
