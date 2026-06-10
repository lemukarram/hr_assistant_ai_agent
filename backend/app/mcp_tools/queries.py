"""
MCP query helpers — thin wrappers over EmployeeRepository.
Called exclusively from mcp_tools/server.py tool handlers.
Each function accepts an AsyncSession and returns JSON-serialisable data.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import EmployeeRepository


# ── Leave ─────────────────────────────────────────────────────────────────────

async def get_leave_balances(
    db: AsyncSession,
    employee_id: str,
    leave_type: str | None = None,
    year: int | None = None,
) -> dict[str, Any]:
    return await EmployeeRepository(db).get_leave_balance(employee_id, leave_type, year)


async def check_leave_balance_sufficient(
    db: AsyncSession,
    employee_id: str,
    leave_type: str,
    days_needed: int,
) -> None:
    """Raises ValueError if balance is insufficient."""
    await EmployeeRepository(db).check_leave_balance_sufficient(employee_id, leave_type, days_needed)


async def create_leave_request(
    db: AsyncSession,
    employee_id: str,
    leave_type: str,
    start_date: date,
    end_date: date,
    reason: str | None,
) -> str:
    """Submit a leave request, return its reference number."""
    result = await EmployeeRepository(db).submit_leave_request(
        employee_id, leave_type, start_date, end_date, reason
    )
    return result["reference"]


# ── Payslips ──────────────────────────────────────────────────────────────────

async def get_payslips(
    db: AsyncSession,
    employee_id: str,
    limit: int = 3,
    year: int | None = None,
    month: int | None = None,
) -> list[dict[str, Any]]:
    return await EmployeeRepository(db).get_payslips(employee_id, months=limit, year=year, month=month)


# ── Org chart ─────────────────────────────────────────────────────────────────

async def get_org_chart(db: AsyncSession, employee_id: str) -> dict[str, Any]:
    return await EmployeeRepository(db).get_org_chart(employee_id)


# ── Profile ───────────────────────────────────────────────────────────────────

async def get_employee_profile(db: AsyncSession, employee_id: str) -> dict[str, Any]:
    emp = await EmployeeRepository(db).get_by_id(employee_id)
    if not emp:
        return {}
    return {
        "employee_id":   str(emp["id"]),
        "name_ar":       emp["name_ar"],
        "name_en":       emp["name_en"],
        "email":         emp["email"],
        "department":    emp["department"],
        "job_title_ar":  emp["job_title_ar"],
        "job_title_en":  emp["job_title_en"],
        "hire_date":     str(emp["hire_date"]) if emp["hire_date"] else None,
        "role":          emp["role"],
    }


# ── Benefits ──────────────────────────────────────────────────────────────────

async def get_employee_benefits(db: AsyncSession, employee_id: str) -> list[dict[str, Any]]:
    return await EmployeeRepository(db).get_benefits(employee_id)


# ── Attendance ────────────────────────────────────────────────────────────────

async def get_attendance_records(
    db: AsyncSession,
    employee_id: str,
    days: int = 30,
    month: int | None = None,
    year: int | None = None,
) -> list[dict[str, Any]]:
    return await EmployeeRepository(db).get_attendance_records(employee_id, days, month, year)


async def get_attendance_summary(
    db: AsyncSession,
    employee_id: str,
    month: int | None = None,
    year: int | None = None,
) -> dict[str, Any]:
    return await EmployeeRepository(db).get_attendance_summary(employee_id, month, year)


# ── Overtime ──────────────────────────────────────────────────────────────────

async def get_overtime_records(
    db: AsyncSession,
    employee_id: str,
    limit: int = 10,
    month: int | None = None,
    year: int | None = None,
) -> list[dict[str, Any]]:
    return await EmployeeRepository(db).get_overtime_records(employee_id, limit, month, year)


async def get_overtime_total_hours(
    db: AsyncSession,
    employee_id: str,
    month: int | None = None,
    year: int | None = None,
) -> dict[str, Any]:
    return await EmployeeRepository(db).get_overtime_total_hours(employee_id, month, year)


async def log_overtime_entry(
    db: AsyncSession,
    employee_id: str,
    work_date: Any,
    hours: float,
    reason: str | None,
) -> dict[str, Any]:
    return await EmployeeRepository(db).log_overtime(employee_id, work_date, hours, reason)
