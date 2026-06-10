"""
Unit tests for MCP tool schemas, response models, and access control integration.
No DB or LLM required — validates tool definitions and Pydantic models.
Run: pytest backend/tests/unit/test_mcp_tools.py -v
"""
import pytest


class TestMCPToolSchemas:
    """Validate that all 10 MCP tools are defined with proper metadata."""

    def test_all_tools_registered_in_direct_import(self) -> None:
        from app.mcp_tools.client import _load_direct

        tools = _load_direct()
        tool_names = {t.name for t in tools}
        expected = {
            "get_leave_balance",
            "get_payslips",
            "get_org_chart",
            "get_employee_profile",
            "submit_leave_request",
            "search_policies",
            "get_benefits_summary",
            "get_attendance_records",
            "get_overtime_hours",
            "log_overtime",
        }
        assert expected == tool_names, f"Missing tools: {expected - tool_names}"

    def test_tools_have_descriptions(self) -> None:
        from app.mcp_tools.client import _load_direct

        for tool in _load_direct():
            assert tool.description, f"Tool '{tool.name}' has no description"
            assert len(tool.description) > 10, f"Tool '{tool.name}' description too short"


class TestMCPResponseModels:
    """Validate Pydantic response models for type correctness."""

    def test_leave_type_balance_model(self) -> None:
        from app.mcp_tools.server import LeaveTypeBalance

        b = LeaveTypeBalance(
            leave_type="annual",
            total_days=21,
            used_days=7,
            remaining_days=14,
            year=2026,
        )
        assert b.remaining_days == 14

    def test_payslip_entry_model(self) -> None:
        from app.mcp_tools.server import PayslipEntry

        entry = PayslipEntry(
            period="2026-05",
            basic_salary=15000.0,
            housing_allowance=3750.0,
            transport_allowance=1500.0,
            deductions=750.0,
            net_salary=19500.0,
            currency="SAR",
            payment_status="paid",
            issued_at="2026-05-31T00:00:00",
        )
        assert entry.currency == "SAR"

    def test_leave_request_result_model(self) -> None:
        from app.mcp_tools.server import LeaveRequestResult

        result = LeaveRequestResult(
            reference_number="ABC12345",
            status="pending",
            leave_type="annual",
            start_date="2026-07-01",
            end_date="2026-07-05",
            days_requested=5,
            message_ar="تم تقديم الطلب",
            message_en="Request submitted",
        )
        assert result.days_requested == 5

    def test_attendance_result_model(self) -> None:
        from app.mcp_tools.server import AttendanceResult, AttendanceSummary

        result = AttendanceResult(
            employee_id="emp-001",
            records=[],
            summary=AttendanceSummary(present=20, late=2, absent=0, remote=1, half_day=0),
            period_days=30,
        )
        assert result.summary.present == 20

    def test_overtime_result_model(self) -> None:
        from app.mcp_tools.server import OvertimeResult

        result = OvertimeResult(
            employee_id="emp-001",
            entries=[],
            total_approved_hours=5.5,
            total_pending_hours=1.5,
        )
        assert result.total_approved_hours == 5.5

    def test_log_overtime_result_model(self) -> None:
        from app.mcp_tools.server import LogOvertimeResult

        result = LogOvertimeResult(
            reference_id="uuid-001",
            work_date="2026-06-05",
            hours=2.0,
            reason="مراجعة",
            status="pending",
            message_ar="تم التسجيل",
            message_en="Logged",
        )
        assert result.hours == 2.0


class TestAuthContextManagement:
    """Tests for the MCP server's contextvars-based auth context."""

    def test_set_and_require_auth_context(self) -> None:
        from app.mcp_tools.server import set_auth_context, _require_auth

        set_auth_context(employee_id="emp-001", role="employee")
        ctx = _require_auth()
        assert ctx["employee_id"] == "emp-001"
        assert ctx["role"] == "employee"

    def test_require_auth_without_context_raises(self) -> None:
        import contextvars
        from app.mcp_tools.server import _auth_context_var

        # Clear context
        token = _auth_context_var.set(None)
        try:
            from app.mcp_tools.server import _require_auth
            with pytest.raises(RuntimeError, match="MCP auth context not set"):
                _require_auth()
        finally:
            _auth_context_var.reset(token)

    def test_check_access_raises_for_different_ids(self) -> None:
        from app.mcp_tools.server import set_auth_context, _check_access
        from app.core.security import AccessDeniedError

        set_auth_context(employee_id="emp-001", role="employee")
        with pytest.raises(AccessDeniedError):
            _check_access("emp-002")

    def test_check_access_passes_for_same_id(self) -> None:
        from app.mcp_tools.server import set_auth_context, _check_access

        set_auth_context(employee_id="emp-001", role="employee")
        _check_access("emp-001")  # Should not raise

    def test_check_access_passes_for_hr_admin(self) -> None:
        from app.mcp_tools.server import set_auth_context, _check_access

        set_auth_context(employee_id="admin-001", role="hr_admin")
        _check_access("emp-any")  # HR admin can access anyone
