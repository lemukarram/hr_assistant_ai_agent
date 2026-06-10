"""
Security — JWT auth, bcrypt, employee access control.
This module is the SOLE source of truth for authentication and authorization.
100% unit test coverage required.
"""
import re
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import bcrypt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

bearer_scheme = HTTPBearer(auto_error=True)

# ── Prompt Injection Detection ────────────────────────────────────────────────

INJECTION_PATTERNS: list[re.Pattern] = [
    # English patterns
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)?\s*(all\s+)?instructions?", re.I),
    re.compile(r"you\s+are\s+now\s+", re.I),
    re.compile(r"(new|change|update)\s+system\s+prompt", re.I),
    re.compile(r"reveal\s+(the\s+)?system\s+prompt", re.I),
    re.compile(r"show\s+(me\s+)?(the\s+)?system\s+prompt", re.I),
    re.compile(r"forget\s+(your|all)\s+(rules?|instructions?|guidelines?)", re.I),
    re.compile(r"act\s+as\s+(an?\s+)?(admin|root|superuser|DAN)", re.I),
    re.compile(r"jailbreak", re.I),
    re.compile(r"prompt\s+injection", re.I),
    re.compile(r"(disregard|override|bypass)\s+(all\s+)?(previous\s+)?(instructions?|rules?|guidelines?)", re.I),
    # Arabic patterns
    re.compile(r"تجاهل\s+(جميع\s+)?التعليمات", re.U),
    re.compile(r"أنت\s+الآن\s+", re.U),
    re.compile(r"نظام\s+جديد\s+", re.U),
    re.compile(r"صلاحيات\s+(المسؤول|الإدارية)", re.U),
    re.compile(r"تجاوز\s+(القواعد|الأنظمة)", re.U),
]


class InjectionCheckResult(BaseModel):
    is_injection: bool
    risk_level: str  # "NONE" | "LOW" | "HIGH" | "CRITICAL"
    matched_pattern: str | None = None


def check_injection(text: str) -> InjectionCheckResult:
    """
    Check user input for prompt injection patterns.
    Called in SecurityGuard LangGraph node BEFORE any LLM call.
    """
    for pattern in INJECTION_PATTERNS:
        if pattern.search(text):
            logger.warning("Injection pattern detected", pattern=pattern.pattern)
            return InjectionCheckResult(
                is_injection=True,
                risk_level="CRITICAL",
                matched_pattern=pattern.pattern,
            )
    return InjectionCheckResult(is_injection=False, risk_level="NONE")


# ── JWT ───────────────────────────────────────────────────────────────────────

class TokenData(BaseModel):
    sub: str           # employee_id
    email: str = ""
    role: str = "employee"   # "employee" | "manager" | "hr_admin"
    exp: datetime


class CurrentUser(BaseModel):
    employee_id: str
    email: str
    role: str


def create_access_token(
    employee_id: str,
    email: str,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload: dict[str, Any] = {
        "sub": employee_id,
        "email": email,
        "role": role,
        "exp": expire,
        "iat": datetime.now(UTC),
        "type": "access",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(employee_id: str) -> str:
    expire = datetime.now(UTC) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": employee_id,
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return TokenData(
            sub=payload["sub"],
            email=payload.get("email", ""),
            role=payload.get("role", "employee"),
            exp=datetime.fromtimestamp(payload["exp"], UTC),
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Security(bearer_scheme)],
) -> CurrentUser:
    """FastAPI dependency — injects CurrentUser into route handlers."""
    token_data = decode_token(credentials.credentials)
    return CurrentUser(
        employee_id=token_data.sub,
        email=token_data.email,
        role=token_data.role,
    )


# ── Access Control ─────────────────────────────────────────────────────────────

class AccessDeniedError(Exception):
    """Raised when an employee attempts to access another employee's data."""


def verify_employee_access(
    requesting_id: str,
    target_id: str,
    role: str = "employee",
    manager_report_ids: list[str] | None = None,
) -> None:
    """
    Enforce row-level data isolation.
    
    Rules:
    - employee: can only access own data (requesting_id == target_id)
    - manager: can access own + direct reports' data
    - hr_admin: can access all employee data
    
    This function is the PRIMARY security control for data isolation.
    It runs in Python — it cannot be bypassed by prompt injection.
    """
    if role == "hr_admin":
        return  # HR admins have full access

    if requesting_id == target_id:
        return  # Always allowed to access own data

    if role == "manager" and manager_report_ids and target_id in manager_report_ids:
        return  # Managers can see direct reports

    raise AccessDeniedError(
        f"Employee {requesting_id} is not authorized to access data for {target_id}"
    )


# ── Password Hashing ──────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── Convenience wrappers for tests ──────────────────────────────────────────

def detect_prompt_injection(text: str) -> bool:
    """Return True if text appears to be a prompt injection attempt."""
    return check_injection(text).is_injection


def can_access_employee_data(requestor_id: int | str, resource_owner_id: int | str) -> bool:
    """
    Boolean access check: returns True only if requestor and target are the same.
    Use in unit tests and simple guard clauses; use verify_employee_access() in
    MCP tool handlers where you need to raise on failure.
    """
    try:
        rid = int(requestor_id)
        oid = int(resource_owner_id)
    except (TypeError, ValueError):
        return False
    if rid <= 0 or oid <= 0:
        return False
    return rid == oid
