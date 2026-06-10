"""
Repository layer — all raw SQL queries for the API and MCP tools.
All queries are parameterised; no f-strings in SQL (SQL-injection safe).
"""
from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class EmployeeRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Employee lookups ───────────────────────────────────────────────────

    async def get_by_email(self, email: str) -> Any | None:
        """Return one employee row matching email, or None."""
        result = await self.db.execute(
            text(
                """
                SELECT id, email, name_ar, name_en, department, job_title_ar,
                       job_title_en, manager_id, password_hash, is_active,
                       hire_date, role
                FROM   employees
                WHERE  email = :email
                LIMIT  1
                """
            ),
            {"email": email},
        )
        return result.mappings().first()

    async def get_by_id(self, employee_id: str) -> Any | None:
        """Return one employee row by UUID, or None."""
        result = await self.db.execute(
            text(
                """
                SELECT id, email, name_ar, name_en, department, job_title_ar,
                       job_title_en, manager_id, is_active, hire_date,
                       phone, national_id, role, salary
                FROM   employees
                WHERE  id = :id
                LIMIT  1
                """
            ),
            {"id": str(employee_id)},
        )
        return result.mappings().first()

    async def get_org_chart(self, employee_id: str) -> dict[str, Any]:
        """Return employee + manager + direct reports."""
        emp = await self.get_by_id(employee_id)
        if not emp:
            return {}

        manager = None
        if emp["manager_id"]:
            manager = await self.get_by_id(emp["manager_id"])

        reports_result = await self.db.execute(
            text(
                """
                SELECT id, name_ar, name_en, job_title_ar, job_title_en, department
                FROM   employees
                WHERE  manager_id = :id
                  AND  is_active  = TRUE
                ORDER  BY name_ar
                """
            ),
            {"id": str(employee_id)},
        )
        direct_reports = [dict(r) for r in reports_result.mappings().all()]

        return {
            "employee": {
                "id":           str(emp["id"]),
                "name_ar":      emp["name_ar"],
                "name_en":      emp["name_en"],
                "job_title_ar": emp["job_title_ar"],
                "job_title_en": emp["job_title_en"],
                "department":   emp["department"],
            },
            "manager": (
                {
                    "id":           str(manager["id"]),
                    "name_ar":      manager["name_ar"],
                    "name_en":      manager["name_en"],
                    "job_title_ar": manager["job_title_ar"],
                    "job_title_en": manager["job_title_en"],
                }
                if manager
                else None
            ),
            "direct_reports": [
                {**r, "id": str(r["id"])} for r in direct_reports
            ],
        }

    # ── Leave ──────────────────────────────────────────────────────────────

    async def get_leave_balance(
        self,
        employee_id: str,
        leave_type: str | None = None,
        year: int | None = None,
    ) -> dict[str, Any]:
        """Return leave balances for an employee, optionally filtered."""
        where_clauses = ["employee_id = :id", "year = :year"]
        params: dict[str, Any] = {
            "id":   str(employee_id),
            "year": year or datetime.now().year,
        }
        if leave_type:
            where_clauses.append("leave_type = :leave_type")
            params["leave_type"] = leave_type

        result = await self.db.execute(
            text(
                f"""
                SELECT leave_type,
                       total_days,
                       used_days,
                       (total_days - used_days) AS remaining_days,
                       year
                FROM   leave_balances
                WHERE  {" AND ".join(where_clauses)}
                ORDER  BY leave_type
                """
            ),
            params,
        )
        rows = result.mappings().all()
        return {
            "employee_id": str(employee_id),
            "year":        params["year"],
            "balances":    [dict(r) for r in rows],
        }

    async def check_leave_balance_sufficient(
        self,
        employee_id: str,
        leave_type: str,
        days_needed: int,
    ) -> None:
        """Raise ValueError if employee doesn't have enough leave days."""
        result = await self.db.execute(
            text(
                """
                SELECT (total_days - used_days) AS remaining
                FROM   leave_balances
                WHERE  employee_id = :id
                  AND  leave_type  = :type
                  AND  year        = EXTRACT(YEAR FROM CURRENT_DATE)::INT
                """
            ),
            {"id": str(employee_id), "type": leave_type},
        )
        remaining = result.scalar()
        if remaining is None:
            raise ValueError(f"نوع الإجازة '{leave_type}' غير موجود للموظف")
        if days_needed > remaining:
            raise ValueError(
                f"الرصيد المتاح ({remaining} يوم) أقل من الأيام المطلوبة ({days_needed} يوم)"
            )

    async def submit_leave_request(
        self,
        employee_id: str,
        leave_type: str,
        start_date: date,
        end_date: date,
        reason: str | None,
    ) -> dict[str, Any]:
        """Validate balance, insert leave request, return reference details."""
        requested_days = (end_date - start_date).days + 1
        await self.check_leave_balance_sufficient(employee_id, leave_type, requested_days)

        result = await self.db.execute(
            text(
                """
                INSERT INTO leave_requests
                    (employee_id, leave_type, start_date, end_date,
                     requested_days, reason, status, submitted_at)
                VALUES
                    (:emp_id, :leave_type, :start_date, :end_date,
                     :days, :reason, 'pending', NOW())
                RETURNING id, status, submitted_at
                """
            ),
            {
                "emp_id":     str(employee_id),
                "leave_type": leave_type,
                "start_date": start_date,
                "end_date":   end_date,
                "days":       requested_days,
                "reason":     reason,
            },
        )
        await self.db.commit()
        row = result.mappings().first()
        return {
            "success":        True,
            "request_id":     str(row["id"]),
            "reference":      str(row["id"])[:8].upper(),
            "status":         row["status"],
            "submitted_at":   row["submitted_at"].isoformat(),
            "requested_days": requested_days,
            "leave_type":     leave_type,
        }

    async def get_leave_history(
        self, employee_id: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        result = await self.db.execute(
            text(
                """
                SELECT id, leave_type, start_date, end_date,
                       requested_days, status, reason, submitted_at
                FROM   leave_requests
                WHERE  employee_id = :id
                ORDER  BY submitted_at DESC
                LIMIT  :limit
                """
            ),
            {"id": str(employee_id), "limit": limit},
        )
        return [
            {**dict(r), "id": str(r["id"])}
            for r in result.mappings().all()
        ]

    # ── Payslips ───────────────────────────────────────────────────────────

    async def get_payslips(
        self,
        employee_id: str,
        months: int = 3,
        year: int | None = None,
        month: int | None = None,
    ) -> list[dict[str, Any]]:
        where_clauses = ["employee_id = :id"]
        params: dict[str, Any] = {"id": str(employee_id), "months": months}

        if year:
            where_clauses.append("period_year = :year")
            params["year"] = year
        if month:
            where_clauses.append("period_month = :month")
            params["month"] = month

        result = await self.db.execute(
            text(
                f"""
                SELECT id, period_year, period_month,
                       basic_salary, housing_allowance, transport_allowance,
                       other_allowances, deductions, net_salary,
                       currency, payment_date, payment_status, issued_at
                FROM   payslips
                WHERE  {" AND ".join(where_clauses)}
                ORDER  BY period_year DESC, period_month DESC
                LIMIT  :months
                """
            ),
            params,
        )
        return [
            {**dict(r), "id": str(r["id"])}
            for r in result.mappings().all()
        ]

    # ── Benefits ───────────────────────────────────────────────────────────

    async def get_benefits(self, employee_id: str) -> list[dict[str, Any]]:
        result = await self.db.execute(
            text(
                """
                SELECT benefit_type, provider, coverage_details,
                       effective_date, expiry_date, is_active
                FROM   employee_benefits
                WHERE  employee_id = :id
                  AND  is_active   = TRUE
                ORDER  BY benefit_type
                """
            ),
            {"id": str(employee_id)},
        )
        return [dict(r) for r in result.mappings().all()]

    # ── Attendance ─────────────────────────────────────────────────────────

    async def get_attendance_records(
        self,
        employee_id: str,
        days: int = 30,
        month: int | None = None,
        year: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return attendance records for an employee, ordered newest first."""
        where_clauses = ["employee_id = :id"]
        params: dict[str, Any] = {"id": str(employee_id), "days": days}

        if year:
            where_clauses.append("EXTRACT(YEAR FROM work_date)::INT = :year")
            params["year"] = year
        if month:
            where_clauses.append("EXTRACT(MONTH FROM work_date)::INT = :month")
            params["month"] = month
        if not (year or month):
            where_clauses.append("work_date >= CURRENT_DATE - :days")

        result = await self.db.execute(
            text(
                f"""
                SELECT work_date, check_in, check_out, status, notes
                FROM   attendance_records
                WHERE  {" AND ".join(where_clauses)}
                ORDER  BY work_date DESC
                LIMIT  :days
                """
            ),
            params,
        )
        return [dict(r) for r in result.mappings().all()]

    async def get_attendance_summary(
        self,
        employee_id: str,
        month: int | None = None,
        year: int | None = None,
    ) -> dict[str, Any]:
        """Return a count summary by status for the given period."""
        params: dict[str, Any] = {"id": str(employee_id)}
        period_filter = ""
        if year:
            period_filter += " AND EXTRACT(YEAR FROM work_date)::INT = :year"
            params["year"] = year
        if month:
            period_filter += " AND EXTRACT(MONTH FROM work_date)::INT = :month"
            params["month"] = month
        else:
            period_filter += " AND work_date >= DATE_TRUNC('month', CURRENT_DATE)"

        result = await self.db.execute(
            text(
                f"""
                SELECT status, COUNT(*) AS cnt
                FROM   attendance_records
                WHERE  employee_id = :id {period_filter}
                GROUP  BY status
                """
            ),
            params,
        )
        counts = {r["status"]: int(r["cnt"]) for r in result.mappings().all()}
        return {
            "present":  counts.get("present",  0),
            "late":     counts.get("late",     0),
            "absent":   counts.get("absent",   0),
            "remote":   counts.get("remote",   0),
            "half_day": counts.get("half_day", 0),
        }

    # ── Overtime ───────────────────────────────────────────────────────────

    async def get_overtime_records(
        self,
        employee_id: str,
        limit: int = 10,
        month: int | None = None,
        year: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return overtime records for an employee, newest first."""
        where_clauses = ["employee_id = :id"]
        params: dict[str, Any] = {"id": str(employee_id), "limit": limit}

        if year:
            where_clauses.append("EXTRACT(YEAR FROM work_date)::INT = :year")
            params["year"] = year
        if month:
            where_clauses.append("EXTRACT(MONTH FROM work_date)::INT = :month")
            params["month"] = month

        result = await self.db.execute(
            text(
                f"""
                SELECT ot.work_date, ot.hours, ot.reason, ot.status,
                       e.name_ar AS approved_by_name_ar
                FROM   overtime_records ot
                LEFT JOIN employees e ON e.id = ot.approved_by
                WHERE  ot.{" AND ot.".join(where_clauses)}
                ORDER  BY ot.work_date DESC
                LIMIT  :limit
                """
            ),
            params,
        )
        return [dict(r) for r in result.mappings().all()]

    async def get_overtime_total_hours(
        self,
        employee_id: str,
        month: int | None = None,
        year: int | None = None,
    ) -> dict[str, Any]:
        """Return total approved overtime hours for the period."""
        params: dict[str, Any] = {"id": str(employee_id)}
        period_filter = ""
        if year:
            period_filter += " AND EXTRACT(YEAR FROM work_date)::INT = :year"
            params["year"] = year
        if month:
            period_filter += " AND EXTRACT(MONTH FROM work_date)::INT = :month"
            params["month"] = month
        else:
            period_filter += " AND work_date >= DATE_TRUNC('month', CURRENT_DATE)"

        result = await self.db.execute(
            text(
                f"""
                SELECT
                    COALESCE(SUM(CASE WHEN status = 'approved' THEN hours ELSE 0 END), 0) AS approved_hours,
                    COALESCE(SUM(CASE WHEN status = 'pending'  THEN hours ELSE 0 END), 0) AS pending_hours,
                    COUNT(*) AS record_count
                FROM overtime_records
                WHERE employee_id = :id {period_filter}
                """
            ),
            params,
        )
        row = result.mappings().first()
        return {
            "approved_hours": float(row["approved_hours"]),
            "pending_hours":  float(row["pending_hours"]),
            "record_count":   int(row["record_count"]),
        }

    async def log_overtime(
        self,
        employee_id: str,
        work_date: Any,
        hours: float,
        reason: str | None,
    ) -> dict[str, Any]:
        """Insert or update an overtime record. Returns the new/updated record."""
        result = await self.db.execute(
            text(
                """
                INSERT INTO overtime_records (employee_id, work_date, hours, reason, status)
                VALUES (:emp_id, :work_date, :hours, :reason, 'pending')
                ON CONFLICT (employee_id, work_date)
                DO UPDATE SET
                    hours  = EXCLUDED.hours,
                    reason = EXCLUDED.reason,
                    status = 'pending'
                RETURNING id, work_date, hours, reason, status
                """
            ),
            {
                "emp_id":    str(employee_id),
                "work_date": work_date,
                "hours":     hours,
                "reason":    reason,
            },
        )
        await self.db.commit()
        row = result.mappings().first()
        return {
            "id":        str(row["id"]),
            "work_date": str(row["work_date"]),
            "hours":     float(row["hours"]),
            "reason":    row["reason"],
            "status":    row["status"],
        }

    # ── Audit ──────────────────────────────────────────────────────────────

    async def log_audit(
        self,
        employee_id: str,
        action: str,
        resource: str = "general",
        details: dict | None = None,
        resource_owner_id: str | None = None,
    ) -> None:
        try:
            await self.db.execute(
                text(
                    """
                    INSERT INTO audit_logs
                        (employee_id, action, resource, resource_owner_id, details, created_at)
                    VALUES
                        (:emp_id, :action, :resource, :owner_id, :details, NOW())
                    """
                ),
                {
                    "emp_id":   str(employee_id),
                    "action":   action,
                    "resource": resource,
                    "owner_id": str(resource_owner_id) if resource_owner_id else None,
                    "details":  json.dumps(details or {}, ensure_ascii=False),
                },
            )
            await self.db.commit()
        except Exception:
            # Audit failures must never crash the main flow
            await self.db.rollback()
