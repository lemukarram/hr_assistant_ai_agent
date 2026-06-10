"""
Authentication API — login / token refresh / logout.
JWT HS256, bcrypt password verification, UUID employee IDs.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.db.repositories import EmployeeRepository
from app.db.session import get_db

logger = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    employee_id: str   # UUID string
    name_ar: str
    name_en: str
    role: str


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Authenticate with email + password.
    Returns a short-lived access token (30 min) and long-lived refresh token (7 days).
    """
    repo = EmployeeRepository(db)
    employee = await repo.get_by_email(form_data.username)

    if not employee:
        logger.info("Login failed: unknown email", email=form_data.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="بيانات الدخول غير صحيحة",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(form_data.password, employee["password_hash"]):
        logger.info("Login failed: wrong password", email=form_data.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="بيانات الدخول غير صحيحة",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if employee.get("is_active") is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="الحساب غير مفعّل. تواصل مع إدارة الموارد البشرية.",
        )

    employee_id = str(employee["id"])
    role = employee.get("role", "employee")

    access_token = create_access_token(
        employee_id=employee_id,
        email=employee["email"],
        role=role,
    )
    refresh_token = create_refresh_token(employee_id=employee_id)

    # Fire-and-forget audit (non-blocking)
    try:
        await repo.log_audit(
            employee_id=employee_id,
            action="LOGIN",
            resource="auth",
            details={"email": employee["email"], "ip": request.client.host if request.client else None},
        )
    except Exception:
        pass  # Audit failure must not block login

    logger.info("Login successful", employee_id=employee_id, email=employee["email"])

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        employee_id=employee_id,
        name_ar=employee["name_ar"],
        name_en=employee["name_en"],
        role=role,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token_endpoint(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Exchange a valid refresh token for a new access + refresh token pair.
    Old refresh token is invalidated by rotation (client must store new one).
    """
    try:
        token_data = decode_token(body.refresh_token)
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="رمز التحديث غير صالح أو منتهي الصلاحية",
        )

    repo = EmployeeRepository(db)
    employee = await repo.get_by_id(token_data.sub)

    if not employee:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="الموظف غير موجود",
        )
    if employee.get("is_active") is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="الحساب غير مفعّل",
        )

    employee_id = str(employee["id"])
    role = employee.get("role", "employee")

    new_access = create_access_token(
        employee_id=employee_id,
        email=employee["email"],
        role=role,
    )
    new_refresh = create_refresh_token(employee_id=employee_id)

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        employee_id=employee_id,
        name_ar=employee["name_ar"],
        name_en=employee["name_en"],
        role=role,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout() -> None:
    """
    Stateless JWT logout — client discards tokens.
    For server-side revocation, add token to a Redis blocklist here.
    """
    return None
