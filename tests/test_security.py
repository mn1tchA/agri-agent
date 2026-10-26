"""
Security module tests — JWT authentication and role-based access control.

Tests cover:
- Token creation and decoding
- Password hashing and verification
- authenticate_user (valid + invalid credentials)
- Role enforcement (require_viewer, require_operator)
- Expired token handling
- Tampered token rejection

Run with:
    pytest tests/ -v
"""

from datetime import timedelta

import pytest

# ===========================================================================
# Helpers
# ===========================================================================


def _mock_settings():
    """Return mock settings for tests without touching .env."""
    from unittest.mock import MagicMock

    s = MagicMock()
    s.jwt_secret_key = "test-secret-key-for-ci-only-not-for-production"
    s.access_token_expire_minutes = 60
    s.admin_username = "admin"
    s.admin_password = "testpassword123"
    s.viewer_username = "viewer"
    s.viewer_password = "viewerpass123"
    return s


# ===========================================================================
# Password hashing
# ===========================================================================


class TestPasswordHashing:
    """Tests for bcrypt password hashing utilities."""

    def test_verify_correct_password(self):
        from security import _hash_password, verify_password

        hashed = _hash_password("mysecretpassword")
        assert verify_password("mysecretpassword", hashed) is True

    def test_reject_wrong_password(self):
        from security import _hash_password, verify_password

        hashed = _hash_password("correctpassword")
        assert verify_password("wrongpassword", hashed) is False

    def test_different_hashes_same_password(self):
        """bcrypt generates a unique salt each time — same password → different hash."""
        from security import _hash_password

        h1 = _hash_password("password")
        h2 = _hash_password("password")
        assert h1 != h2  # Different salts

    def test_verify_rejects_garbage_hash(self):
        """verify_password returns False (not an exception) for invalid hashes."""
        from security import verify_password

        assert verify_password("password", b"not-a-valid-bcrypt-hash") is False


# ===========================================================================
# JWT Token creation
# ===========================================================================


class TestTokenCreation:
    """Tests for JWT creation and decoding."""

    def test_create_and_decode_token(self):
        from jose import jwt

        from config import settings
        from security import create_access_token

        token = create_access_token({"sub": "testuser", "role": "operator"})
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
        assert payload["sub"] == "testuser"
        assert payload["role"] == "operator"
        assert "exp" in payload

    def test_custom_expiry(self):
        import time

        from jose import jwt

        from config import settings
        from security import create_access_token

        expires = timedelta(seconds=5)
        token = create_access_token({"sub": "user", "role": "viewer"}, expires_delta=expires)
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
        # exp should be approximately now + 5 seconds
        assert payload["exp"] > time.time()
        assert payload["exp"] < time.time() + 10  # within 10 seconds of now

    def test_expired_token_raises(self):
        """A token that expired 1 second ago should be rejected."""
        from jose import JWTError, jwt

        from config import settings
        from security import create_access_token

        # Create a token that expired 1 second ago
        token = create_access_token(
            {"sub": "user", "role": "viewer"},
            expires_delta=timedelta(seconds=-1),
        )
        with pytest.raises(JWTError):
            jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])

    def test_tampered_token_raises(self):
        """Modifying the token payload should invalidate the signature."""
        import base64
        import json

        from jose import JWTError, jwt

        from config import settings
        from security import create_access_token

        token = create_access_token({"sub": "user", "role": "viewer"})
        # Split and tamper with the payload segment
        header, payload_b64, sig = token.split(".")
        # Decode → modify → re-encode without re-signing
        padding = 4 - len(payload_b64) % 4
        decoded = json.loads(base64.urlsafe_b64decode(payload_b64 + "=" * padding))
        decoded["role"] = "operator"  # Attempt privilege escalation
        tampered_payload = (
            base64.urlsafe_b64encode(json.dumps(decoded).encode()).rstrip(b"=").decode()
        )
        tampered_token = f"{header}.{tampered_payload}.{sig}"

        with pytest.raises(JWTError):
            jwt.decode(tampered_token, settings.jwt_secret_key, algorithms=["HS256"])


# ===========================================================================
# authenticate_user
# ===========================================================================


class TestAuthenticateUser:
    """Tests for the authenticate_user credential validation function."""

    def test_valid_admin_credentials(self):
        from config import settings
        from security import authenticate_user

        result = authenticate_user(settings.admin_username, settings.admin_password)
        assert result is not None
        assert result.username == settings.admin_username
        assert result.role == "operator"

    def test_valid_viewer_credentials(self):
        from config import settings
        from security import authenticate_user

        result = authenticate_user(settings.viewer_username, settings.viewer_password)
        assert result is not None
        assert result.role == "viewer"

    def test_wrong_password_returns_none(self):
        from config import settings
        from security import authenticate_user

        result = authenticate_user(settings.admin_username, "wrongpassword")
        assert result is None

    def test_unknown_username_returns_none(self):
        from security import authenticate_user

        result = authenticate_user("nonexistentuser", "anypassword")
        assert result is None

    def test_empty_credentials_returns_none(self):
        from security import authenticate_user

        assert authenticate_user("", "") is None
        assert authenticate_user("admin", "") is None


# ===========================================================================
# FastAPI dependency enforcement
# ===========================================================================


class TestAuthDependencies:
    """Tests for require_viewer and require_operator FastAPI dependencies."""

    @pytest.mark.asyncio
    async def test_require_viewer_allows_viewer(self):
        from security import TokenData, require_viewer

        user = TokenData(username="viewer", role="viewer")
        result = await require_viewer(user)
        assert result.username == "viewer"

    @pytest.mark.asyncio
    async def test_require_viewer_allows_operator(self):
        """Operators have at least viewer privileges."""
        from security import TokenData, require_viewer

        user = TokenData(username="admin", role="operator")
        result = await require_viewer(user)
        assert result.role == "operator"

    @pytest.mark.asyncio
    async def test_require_operator_allows_operator(self):
        from security import TokenData, require_operator

        user = TokenData(username="admin", role="operator")
        result = await require_operator(user)
        assert result.username == "admin"

    @pytest.mark.asyncio
    async def test_require_operator_rejects_viewer(self):
        """A viewer attempting an operator action should get HTTP 403."""
        from fastapi import HTTPException

        from security import TokenData, require_operator

        user = TokenData(username="viewer", role="viewer")
        with pytest.raises(HTTPException) as exc_info:
            await require_operator(user)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_get_current_user_rejects_invalid_token(self):
        """A garbage token should raise 401."""
        from fastapi import HTTPException

        from security import get_current_user

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user("this.is.not.a.valid.jwt")
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_rejects_missing_claims(self):
        """A JWT signed with the right key but missing sub/role claims → 401."""
        from fastapi import HTTPException

        from security import create_access_token, get_current_user

        # Token with no 'sub' or 'role' field
        token = create_access_token({"data": "incomplete"})
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token)
        assert exc_info.value.status_code == 401
