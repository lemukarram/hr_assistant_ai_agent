"""
MCP Tool Server — FastMCP exposing 7 HR capability tools.

Security model:
  Every tool that touches personal data calls verify_employee_access() which
  compares the tool's employee_id argument against the auth context injected
  from the JWT before each tool invocation.  This check runs in Python and
  CANNOT be bypassed by prompt manipulation.

Transport: HTTP/SSE (standard MCP transport)
"""
from __future__ import annotations

import contextvars
from datetime import date
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.core.security import AccessDeniedError, verify_employee_access
from app.db.session import get_db_session
from app.mcp_tools import queries

logger = get_logger(__name__)

# ── Auth context (set by agent before each tool call) ─────────────────────────
# Using contextvars ensures thread/coroutine safety without shared state.
_auth_context_var: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "mcp_auth_context", default=None
)


def set_auth_context(employee_id: str, role: str = "employee") -> None:
    """
    Set the auth context for the current coroutine.
    Called by the agent immediately before invoking MCP tools.
    """
    _auth_context_var.set({"employee_id": str(employee_id), "role": role})


def _require_auth() -> dict:
    """
    Retrieve the current auth context.
    Raises RuntimeError if called outside an authenticated agent session.
    """
    ctx = _auth_context_var.get()
    if ctx is None:
        raise RuntimeError(
            "MCP auth context not set — tool called outside an authenticated agent session"
        )
    return ctx


def _check_access(target_employee_id: str) -> None:
    """
    Enforce row-level isolation: the calling employee may only access their own data
    (unless they are a manager or hr_admin).
    Raises AccessDeniedError on violation.
    """
    ctx = _require_auth()
    verify_employee_access(
        requesting_id=ctx["employee_id"],
        target_id=str(target_employee_id),
        role=ctx.get("role", "employee"),
    )


# ── FastMCP app ───────────────────────────────────────────────────────────────

mcp = FastMCP(
    name="HR Assistant MCP Server",
    instructions="Ten HR capability tools for the agentic HR assistant",
    version="1.0.0",
)


# ── Response models ───────────────────────────────────────────────────────────

class LeaveTypeBalance(BaseModel):
    leave_type: str
    total_days: int
    used_days: int
    remaining_days: int
    year: int


class LeaveBalanceResult(BaseModel):
    employee_id: str
    year: int
    balances: list[LeaveTypeBalance]


class PayslipEntry(BaseModel):
    period: str                    # "2025-04"
    basic_salary: float
    housing_allowance: float
    transport_allowance: float
    deductions: float
    net_salary: float
    currency: str
    payment_status: str
    issued_at: str


class OrgNode(BaseModel):
    employee_id: str
    name_ar: str
    name_en: str
    job_title_ar: str | None
    job_title_en: str | None
    department: str | None


class OrgChartResult(BaseModel):
    employee: dict
    manager: dict | None
    direct_reports: list[dict]


class EmployeeProfile(BaseModel):
    employee_id: str
    name_ar: str
    name_en: str
    email: str
    department: str | None
    job_title_ar: str | None
    job_title_en: str | None
    hire_date: str | None
    role: str


class LeaveRequestResult(BaseModel):
    reference_number: str
    status: str
    leave_type: str
    start_date: str
    end_date: str
    days_requested: int
    message_ar: str
    message_en: str


class PolicyChunk(BaseModel):
    text: str
    section: str
    page: int
    score: float
    source_doc: str


class PolicySearchResult(BaseModel):
    query: str
    chunks: list[PolicyChunk]
    citation_hint: str


class BenefitItem(BaseModel):
    benefit_type: str
    provider: str | None
    coverage_details: dict | None
    effective_date: str
    is_active: bool


class BenefitsSummary(BaseModel):
    employee_id: str
    benefits: list[BenefitItem]


# ── Tool: get_leave_balance ───────────────────────────────────────────────────

@mcp.tool()
async def get_leave_balance(
    employee_id: Annotated[str, Field(description="Employee UUID (must match authenticated user)")],
    leave_type: Annotated[
        Literal["annual", "sick", "emergency", "maternity", "hajj"] | None,
        Field(description="Optional leave type filter. Returns all types if omitted."),
    ] = None,
    year: Annotated[int | None, Field(description="Year (defaults to current year)")] = None,
) -> LeaveBalanceResult:
    """
    Get remaining leave balance for an employee.
    Returns balances by leave type with used / remaining / total breakdown.

    Use when the employee asks about leave days, vacation balance, or sick days remaining.
    """
    _check_access(employee_id)

    async with get_db_session() as db:
        data = await queries.get_leave_balances(db, employee_id, leave_type, year)

    logger.info("Tool: get_leave_balance", employee_id=employee_id)
    balances = [
        LeaveTypeBalance(
            leave_type=b["leave_type"],
            total_days=b["total_days"],
            used_days=b["used_days"],
            remaining_days=b["remaining_days"],
            year=b["year"],
        )
        for b in data.get("balances", [])
    ]
    return LeaveBalanceResult(
        employee_id=employee_id,
        year=data.get("year", 0),
        balances=balances,
    )


# ── Tool: get_payslips ────────────────────────────────────────────────────────

@mcp.tool()
async def get_payslips(
    employee_id: Annotated[str, Field(description="Employee UUID")],
    limit: Annotated[int, Field(description="Number of recent payslips (1–12)", ge=1, le=12)] = 3,
    year: Annotated[int | None, Field(description="Filter by year")] = None,
    month: Annotated[int | None, Field(description="Filter by month (1–12)")] = None,
) -> list[PayslipEntry]:
    """
    Get payslip history — basic salary, allowances, deductions, and net pay.

    Use when the employee asks about their salary, paycheck, or monthly pay.
    """
    _check_access(employee_id)

    async with get_db_session() as db:
        rows = await queries.get_payslips(db, employee_id, limit=limit, year=year, month=month)

    logger.info("Tool: get_payslips", employee_id=employee_id, count=len(rows))
    entries: list[PayslipEntry] = []
    for r in rows:
        period = f"{r.get('period_year')}-{str(r.get('period_month', 0)).zfill(2)}"
        entries.append(
            PayslipEntry(
                period=period,
                basic_salary=float(r.get("basic_salary", 0)),
                housing_allowance=float(r.get("housing_allowance", 0)),
                transport_allowance=float(r.get("transport_allowance", 0)),
                deductions=float(r.get("deductions", 0)),
                net_salary=float(r.get("net_salary", 0)),
                currency=r.get("currency", "SAR"),
                payment_status=r.get("payment_status", "paid"),
                issued_at=str(r.get("issued_at", "")),
            )
        )
    return entries


# ── Tool: get_org_chart ───────────────────────────────────────────────────────

@mcp.tool()
async def get_org_chart(
    employee_id: Annotated[str, Field(description="Employee UUID to center the chart on")],
) -> OrgChartResult:
    """
    Get the organisational chart — employee's manager and direct reports.
    Org structure is not confidential; no ownership check required.

    Use when the employee asks who their manager is, who reports to them,
    or about their team structure.
    """
    async with get_db_session() as db:
        data = await queries.get_org_chart(db, employee_id)

    logger.info("Tool: get_org_chart", employee_id=employee_id)
    return OrgChartResult(
        employee=data.get("employee", {}),
        manager=data.get("manager"),
        direct_reports=data.get("direct_reports", []),
    )


# ── Tool: get_employee_profile ────────────────────────────────────────────────

@mcp.tool()
async def get_employee_profile(
    employee_id: Annotated[str, Field(description="Employee UUID")],
) -> EmployeeProfile:
    """
    Get employee profile — name, department, job title, hire date.

    Use when the employee asks about their own profile or personal information.
    """
    _check_access(employee_id)

    async with get_db_session() as db:
        data = await queries.get_employee_profile(db, employee_id)

    if not data:
        raise ValueError(f"Employee {employee_id} not found")

    logger.info("Tool: get_employee_profile", employee_id=employee_id)
    return EmployeeProfile(**data)


# ── Tool: submit_leave_request ────────────────────────────────────────────────

@mcp.tool()
async def submit_leave_request(
    employee_id: Annotated[str, Field(description="Employee UUID submitting the request")],
    leave_type: Annotated[
        Literal["annual", "sick", "emergency", "maternity", "hajj"],
        Field(description="Type of leave"),
    ],
    start_date: Annotated[str, Field(description="Start date YYYY-MM-DD")],
    end_date: Annotated[str, Field(description="End date YYYY-MM-DD")],
    reason: Annotated[str | None, Field(description="Reason for leave (optional)")] = None,
) -> LeaveRequestResult:
    """
    Submit a leave request on behalf of an employee.
    Validates balance availability before submission.

    IMPORTANT: Always confirm dates with the employee before calling this tool.
    Use when the employee explicitly asks to request, apply for, or submit leave.
    """
    _check_access(employee_id)

    try:
        start = date.fromisoformat(start_date)
        end   = date.fromisoformat(end_date)
    except ValueError as exc:
        raise ValueError(f"Invalid date format (use YYYY-MM-DD): {exc}") from exc

    if end < start:
        raise ValueError("تاريخ النهاية يجب أن يكون بعد تاريخ البداية / End date must be after start date")

    days = (end - start).days + 1

    async with get_db_session() as db:
        reference = await queries.create_leave_request(
            db,
            employee_id=employee_id,
            leave_type=leave_type,
            start_date=start,
            end_date=end,
            reason=reason,
        )

    logger.info("Tool: submit_leave_request", employee_id=employee_id, reference=reference)
    return LeaveRequestResult(
        reference_number=reference,
        status="pending",
        leave_type=leave_type,
        start_date=start_date,
        end_date=end_date,
        days_requested=days,
        message_ar=f"تم تقديم طلب الإجازة بنجاح. الرقم المرجعي: {reference}. سيتم مراجعته من قبل مديرك.",
        message_en=f"Leave request submitted successfully. Reference: {reference}. It will be reviewed by your manager.",
    )


# ── Tool: search_policies ─────────────────────────────────────────────────────

@mcp.tool()
async def search_policies(
    query: Annotated[str, Field(description="Policy question in Arabic or English")],
    domain: Annotated[
        Literal["leave", "compensation", "conduct", "remote_work", "recruitment", "general"] | None,
        Field(description="Optional domain filter"),
    ] = None,
) -> PolicySearchResult:
    """
    Search the company HR handbook and return relevant policy sections with citations.

    Use this for ANY question about company policies, rules, procedures, or regulations.
    ALWAYS cite the source section and page number in your final response.
    Does not require ownership check — all employees may read all policies.
    """
    from app.rag.retriever import HybridRetriever

    retriever = HybridRetriever()
    chunks = await retriever.retrieve(query, top_k=3, domain_filter=domain)

    logger.info("Tool: search_policies", query_preview=query[:60], chunks=len(chunks))
    return PolicySearchResult(
        query=query,
        chunks=[
            PolicyChunk(
                text=c["text"],
                section=c.get("metadata", {}).get("section", ""),
                page=int(c.get("metadata", {}).get("page", 0)),
                score=float(c.get("rerank_score", c.get("score", 0.0))),
                source_doc=c.get("metadata", {}).get("source", "HR Handbook"),
            )
            for c in chunks
        ],
        citation_hint="أضف في نهاية كل إجابة عن السياسات: [المصدر: {section}، صفحة {page}]",
    )


# ── Tool: get_benefits_summary ────────────────────────────────────────────────

@mcp.tool()
async def get_benefits_summary(
    employee_id: Annotated[str, Field(description="Employee UUID")],
) -> BenefitsSummary:
    """
    Get employee benefits enrollment — health insurance, life insurance, etc.

    Use when the employee asks about their benefits, insurance coverage, or entitlements.
    """
    _check_access(employee_id)

    async with get_db_session() as db:
        rows = await queries.get_employee_benefits(db, employee_id)

    logger.info("Tool: get_benefits_summary", employee_id=employee_id)
    benefits = [
        BenefitItem(
            benefit_type=r.get("benefit_type", ""),
            provider=r.get("provider"),
            coverage_details=r.get("coverage_details"),
            effective_date=str(r.get("effective_date", "")),
            is_active=bool(r.get("is_active", True)),
        )
        for r in rows
    ]
    return BenefitsSummary(employee_id=employee_id, benefits=benefits)


# ── Tool: get_attendance_records ─────────────────────────────────────────────

class AttendanceEntry(BaseModel):
    work_date: str
    check_in: str | None
    check_out: str | None
    status: str
    notes: str | None


class AttendanceSummary(BaseModel):
    present: int
    late: int
    absent: int
    remote: int
    half_day: int


class AttendanceResult(BaseModel):
    employee_id: str
    records: list[AttendanceEntry]
    summary: AttendanceSummary
    period_days: int


@mcp.tool()
async def get_attendance_records(
    employee_id: Annotated[str, Field(description="Employee UUID")],
    days: Annotated[int, Field(description="Number of recent days to fetch (1–90)", ge=1, le=90)] = 30,
    month: Annotated[int | None, Field(description="Filter by month (1–12)")] = None,
    year: Annotated[int | None, Field(description="Filter by year")] = None,
) -> AttendanceResult:
    """
    Get attendance records — check-in/out times, status (present/late/absent/remote/half_day).

    Use when the employee asks about their attendance, late arrivals, check-in times,
    or number of days they were late this month.
    """
    _check_access(employee_id)

    async with get_db_session() as db:
        records_data = await queries.get_attendance_records(db, employee_id, days, month, year)
        summary_data = await queries.get_attendance_summary(db, employee_id, month, year)

    logger.info("Tool: get_attendance_records", employee_id=employee_id, count=len(records_data))

    records = [
        AttendanceEntry(
            work_date=str(r.get("work_date", "")),
            check_in=str(r["check_in"]) if r.get("check_in") else None,
            check_out=str(r["check_out"]) if r.get("check_out") else None,
            status=r.get("status", ""),
            notes=r.get("notes"),
        )
        for r in records_data
    ]

    return AttendanceResult(
        employee_id=employee_id,
        records=records,
        summary=AttendanceSummary(**summary_data),
        period_days=days,
    )


# ── Tool: get_overtime_hours ──────────────────────────────────────────────────

class OvertimeEntry(BaseModel):
    work_date: str
    hours: float
    reason: str | None
    status: str
    approved_by_name_ar: str | None


class OvertimeResult(BaseModel):
    employee_id: str
    entries: list[OvertimeEntry]
    total_approved_hours: float
    total_pending_hours: float


@mcp.tool()
async def get_overtime_hours(
    employee_id: Annotated[str, Field(description="Employee UUID")],
    month: Annotated[int | None, Field(description="Month filter (1–12)")] = None,
    year: Annotated[int | None, Field(description="Year filter")] = None,
) -> OvertimeResult:
    """
    Get overtime records — hours worked beyond standard schedule per day.

    Use when the employee asks how many overtime hours they have logged,
    or wants to see their overtime history this month.
    """
    _check_access(employee_id)

    async with get_db_session() as db:
        entries_data = await queries.get_overtime_records(db, employee_id, month=month, year=year)
        totals = await queries.get_overtime_total_hours(db, employee_id, month, year)

    logger.info("Tool: get_overtime_hours", employee_id=employee_id, count=len(entries_data))

    entries = [
        OvertimeEntry(
            work_date=str(r.get("work_date", "")),
            hours=float(r.get("hours", 0)),
            reason=r.get("reason"),
            status=r.get("status", ""),
            approved_by_name_ar=r.get("approved_by_name_ar"),
        )
        for r in entries_data
    ]

    return OvertimeResult(
        employee_id=employee_id,
        entries=entries,
        total_approved_hours=totals["approved_hours"],
        total_pending_hours=totals["pending_hours"],
    )


# ── Tool: log_overtime ────────────────────────────────────────────────────────

class LogOvertimeResult(BaseModel):
    reference_id: str
    work_date: str
    hours: float
    reason: str | None
    status: str
    message_ar: str
    message_en: str


@mcp.tool()
async def log_overtime(
    employee_id: Annotated[str, Field(description="Employee UUID")],
    work_date: Annotated[str, Field(description="Date of overtime work YYYY-MM-DD")],
    hours: Annotated[float, Field(description="Number of overtime hours (0.5–12)", ge=0.5, le=12)],
    reason: Annotated[str | None, Field(description="Reason for overtime")] = None,
) -> LogOvertimeResult:
    """
    Log overtime hours for a specific work day. The record is submitted as 'pending' until approved by a manager.

    IMPORTANT: Confirm the date and hours with the employee before calling.
    Use when the employee explicitly asks to log, record, or submit overtime hours.
    """
    _check_access(employee_id)

    try:
        parsed_date = date.fromisoformat(work_date)
    except ValueError as exc:
        raise ValueError(f"Invalid date format (use YYYY-MM-DD): {exc}") from exc

    if parsed_date > date.today():
        raise ValueError("لا يمكن تسجيل عمل إضافي في المستقبل / Cannot log overtime for a future date")

    async with get_db_session() as db:
        result = await queries.log_overtime_entry(db, employee_id, parsed_date, hours, reason)

    logger.info("Tool: log_overtime", employee_id=employee_id, date=work_date, hours=hours)

    return LogOvertimeResult(
        reference_id=result["id"],
        work_date=result["work_date"],
        hours=result["hours"],
        reason=result.get("reason"),
        status=result["status"],
        message_ar=f"تم تسجيل {hours} ساعة عمل إضافي بتاريخ {work_date}. في انتظار موافقة المدير.",
        message_en=f"Logged {hours} overtime hours for {work_date}. Pending manager approval.",
    )


# ── Standalone runner ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    from app.core.config import settings

    uvicorn.run(
        mcp.get_asgi_app(),
        host=settings.MCP_SERVER_HOST,
        port=settings.MCP_SERVER_PORT,
        log_level="info",
    )
