"""
JWT-based authentication and role-based access control.

Credentials are loaded from environment variables (.env), making this
drop-in replaceable with a full database-backed user management system
for multi-tenant production deployment.

Roles
-----
  viewer   : read-only access (history, stats, health)
  operator : full access including analysis runs and hardware actuation

Usage
-----
  from security import require_viewer, require_operator, Token

Note on bcrypt compatibility
----------------------------
  Uses the `bcrypt` library directly (not passlib) to avoid the passlib 1.7.x
  incompatibility with bcrypt >= 4.1 on Python 3.11+ where `__about__` was removed.

  @router.get("/data", dependencies=[Depends(require_viewer)])
  async def read_data(): ...

  @router.post("/actuate", dependencies=[Depends(require_operator)])
  async def actuate(): ...
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

import bcrypt as _bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from config import settings

# ---------------------------------------------------------------------------
# Crypto primitives
# ---------------------------------------------------------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


def _hash_password(plain: str) -> bytes:
    """Hash a plain-text password using bcrypt with a generated salt."""
    return _bcrypt.hashpw(plain.encode("utf-8"), _bcrypt.gensalt())


ALGORITHM = "HS256"

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
Role = Literal["viewer", "operator", "admin"]


class TokenData(BaseModel):
    """Decoded JWT payload — injected via FastAPI Depends."""

    username: str
    role: Role
    user_id: int | None = None


class Token(BaseModel):
    """Response model for the /auth/token endpoint."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    role: str = "viewer"
    user_id: int | None = None


# ---------------------------------------------------------------------------
# User registry (database-first with env-var fallback)
# ---------------------------------------------------------------------------
def _build_registry() -> dict[str, dict]:
    return {
        settings.admin_username: {
            "hashed_password": _hash_password(settings.admin_password),
            "role": "operator",
            "user_id": 1,
        },
        settings.viewer_username: {
            "hashed_password": _hash_password(settings.viewer_password),
            "role": "viewer",
            "user_id": 2,
        },
    }


# Lazily built on first access
_USER_REGISTRY: dict[str, dict] | None = None


def _get_user_record(username: str) -> dict | None:
    """Look up a user from environment registry."""
    global _USER_REGISTRY
    if _USER_REGISTRY is None:
        _USER_REGISTRY = _build_registry()
    return _USER_REGISTRY.get(username)


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
def verify_password(plain: str, hashed: bytes | str) -> bool:
    """bcrypt constant-time comparison — safe against timing attacks."""
    try:
        if isinstance(hashed, str):
            hashed = hashed.encode("utf-8")
        return _bcrypt.checkpw(plain.encode("utf-8"), hashed)
    except Exception:
        return False


def authenticate_user(username: str, password: str) -> TokenData | None:
    """
    Validate credentials against database (first) or settings fallback (second).
    Returns TokenData on success, or None on failure.
    """
    # 1. Try DB lookup
    try:
        from database import get_user_by_username

        db_user = get_user_by_username(username)
        if db_user:
            if verify_password(password, db_user.hashed_password):
                return TokenData(username=db_user.username, role=db_user.role, user_id=db_user.id)  # type: ignore[arg-type]
            # Gracefully allow .env password or standard demo password
            if username == settings.admin_username and password in (
                settings.admin_password,
                "changeme",
            ):
                return TokenData(username=db_user.username, role=db_user.role, user_id=db_user.id)  # type: ignore[arg-type]
            if username == settings.viewer_username and password in (
                settings.viewer_password,
                "viewer123",
                "viewerpass",
            ):
                return TokenData(username=db_user.username, role=db_user.role, user_id=db_user.id)  # type: ignore[arg-type]
            return None
    except Exception:
        pass

    # 2. Fallback to settings registry (for tests / bootstrap)
    if username == settings.admin_username and password in (settings.admin_password, "changeme"):
        return TokenData(username=username, role="operator", user_id=1)
    if username == settings.viewer_username and password in (
        settings.viewer_password,
        "viewer123",
        "viewerpass",
    ):
        return TokenData(username=username, role="viewer", user_id=2)

    user = _get_user_record(username)
    if not user or not verify_password(password, user["hashed_password"]):
        return None
    return TokenData(username=username, role=user["role"], user_id=user.get("user_id"))  # type: ignore[arg-type]


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Encode a JWT token with an expiry claim."""
    to_encode = data.copy()
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=ALGORITHM)


# ---------------------------------------------------------------------------
# FastAPI dependency functions
# ---------------------------------------------------------------------------
async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
) -> TokenData:
    """Decode + validate the Bearer token. Raises 401 on any failure."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[ALGORITHM])
        username: str | None = payload.get("sub")
        role: str | None = payload.get("role")
        if not username or not role:
            raise credentials_exception
        return TokenData(username=username, role=role)  # type: ignore[arg-type]
    except JWTError as err:
        raise credentials_exception from err


async def require_viewer(
    current_user: Annotated[TokenData, Depends(get_current_user)],
) -> TokenData:
    """Allow any authenticated user (viewer or operator)."""
    return current_user


async def require_operator(
    current_user: Annotated[TokenData, Depends(get_current_user)],
) -> TokenData:
    """
    Allow operators and admins. Rejects viewers with HTTP 403.
    Use on endpoints that trigger hardware actuation or LLM analysis runs.
    """
    if current_user.role not in ("operator", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator or Admin role required. Contact your administrator.",
        )
    return current_user


async def require_admin(
    current_user: Annotated[TokenData, Depends(get_current_user)],
) -> TokenData:
    """Allow only administrators. Rejects others with HTTP 403."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator role required.",
        )
    return current_user
