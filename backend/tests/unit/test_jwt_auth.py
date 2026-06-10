"""
Unit tests for JWT token creation, validation, and expiry.
No external services required.
Run: pytest backend/tests/unit/test_jwt_auth.py -v
"""
import os
from datetime import UTC, datetime, timedelta

import pytest

os.environ.setdefault("SECRET_KEY", "test_secret_key_for_jwt_tests_minimum_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/testdb")


class TestTokenCreation:
    def test_create_access_token_returns_string(self) -> None:
        from app.core.security import create_access_token

        token = create_access_token(employee_id="emp-001", email="test@company.sa", role="employee")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_encodes_claims(self) -> None:
        from app.core.security import create_access_token, decode_token

        token = create_access_token(employee_id="emp-001", email="test@company.sa", role="manager")
        data = decode_token(token)
        assert data.sub == "emp-001"
        assert data.email == "test@company.sa"
        assert data.role == "manager"

    def test_create_access_token_respects_custom_expiry(self) -> None:
        from app.core.security import create_access_token, decode_token

        delta = timedelta(minutes=5)
        token = create_access_token(
            employee_id="emp-001",
            email="test@company.sa",
            role="employee",
            expires_delta=delta,
        )
        data = decode_token(token)
        now = datetime.now(UTC)
        # Expiry should be roughly now + 5 minutes (allow 10-second tolerance)
        assert abs((data.exp - now).total_seconds() - 300) < 10

    def test_create_refresh_token_returns_string(self) -> None:
        from app.core.security import create_refresh_token

        token = create_refresh_token(employee_id="emp-001")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_refresh_token_encodes_employee_id(self) -> None:
        from app.core.security import create_refresh_token, decode_token

        token = create_refresh_token(employee_id="emp-abc")
        data = decode_token(token)
        assert data.sub == "emp-abc"


class TestTokenDecoding:
    def test_decode_valid_token(self) -> None:
        from app.core.security import create_access_token, decode_token

        token = create_access_token(employee_id="emp-001", email="a@b.sa", role="hr_admin")
        data = decode_token(token)
        assert data.sub == "emp-001"
        assert data.role == "hr_admin"

    def test_decode_expired_token_raises(self) -> None:
        from fastapi import HTTPException
        from app.core.security import create_access_token, decode_token

        token = create_access_token(
            employee_id="emp-001",
            email="a@b.sa",
            role="employee",
            expires_delta=timedelta(seconds=-1),  # Already expired
        )
        with pytest.raises(HTTPException) as exc_info:
            decode_token(token)
        assert exc_info.value.status_code == 401

    def test_decode_tampered_token_raises(self) -> None:
        from fastapi import HTTPException
        from app.core.security import decode_token

        with pytest.raises(HTTPException) as exc_info:
            decode_token("this.is.not.a.valid.jwt.token")
        assert exc_info.value.status_code == 401

    def test_decode_empty_token_raises(self) -> None:
        from fastapi import HTTPException
        from app.core.security import decode_token

        with pytest.raises(HTTPException):
            decode_token("")


class TestPasswordHashing:
    def test_hash_password_returns_non_empty_string(self) -> None:
        from app.core.security import hash_password

        hashed = hash_password("demo1234")
        assert isinstance(hashed, str)
        assert len(hashed) > 0
        assert hashed != "demo1234"

    def test_verify_password_correct(self) -> None:
        from app.core.security import hash_password, verify_password

        hashed = hash_password("mySecurePass!")
        assert verify_password("mySecurePass!", hashed) is True

    def test_verify_password_wrong(self) -> None:
        from app.core.security import hash_password, verify_password

        hashed = hash_password("correctPassword")
        assert verify_password("wrongPassword", hashed) is False

    def test_same_password_different_hashes(self) -> None:
        from app.core.security import hash_password

        h1 = hash_password("samePassword")
        h2 = hash_password("samePassword")
        # bcrypt salt ensures different hashes each time
        assert h1 != h2

    def test_hash_is_bcrypt_format(self) -> None:
        from app.core.security import hash_password

        hashed = hash_password("password")
        # Bcrypt hashes start with $2b$
        assert hashed.startswith("$2b$")


class TestCurrentUserExtraction:
    def test_current_user_has_correct_fields(self) -> None:
        from app.core.security import create_access_token, decode_token, CurrentUser

        token = create_access_token(employee_id="emp-999", email="x@y.sa", role="hr_admin")
        data = decode_token(token)
        user = CurrentUser(employee_id=data.sub, email=data.email, role=data.role)
        assert user.employee_id == "emp-999"
        assert user.email == "x@y.sa"
        assert user.role == "hr_admin"
