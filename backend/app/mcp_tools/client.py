"""
MCP Client — loads HR tools from the FastMCP server and adapts them
for LangChain / LangGraph tool binding.

In production the MCP server runs as a sibling Docker service.
In testing the tools are imported directly (in-process).
"""
from __future__ import annotations

import functools
from typing import Any

from langchain_core.tools import StructuredTool
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def get_mcp_tools() -> list[StructuredTool]:
    """
    Return LangChain-compatible tool objects wrapping each MCP tool.
    Tries HTTP transport first; falls back to direct import for testing.
    """
    try:
        return _load_via_http()
    except Exception as exc:
        logger.warning("MCP HTTP transport failed, using direct import", error=str(exc))
        return _load_direct()


def _load_via_http() -> list[StructuredTool]:
    """
    Load tools via MCP HTTP/SSE transport.
    Uses langchain-mcp-adapters if available.
    """
    from langchain_mcp_adapters.client import MultiServerMCPClient

    client = MultiServerMCPClient(
        {
            "hr_tools": {
                "url": f"{settings.MCP_SERVER_URL}/sse",
                "transport": "sse",
            }
        }
    )
    tools = client.get_tools()
    logger.info("Loaded MCP tools via HTTP", count=len(tools))
    return tools


def _load_direct() -> list[StructuredTool]:
    """
    Load tools by directly importing the FastMCP app.
    Used in unit tests and when the MCP server is co-located.
    """
    from app.mcp_tools.server import (
        get_leave_balance,
        get_payslips,
        get_org_chart,
        get_employee_profile,
        submit_leave_request,
        search_policies,
        get_benefits_summary,
        get_attendance_records,
        get_overtime_hours,
        log_overtime,
    )

    tool_fns = [
        get_leave_balance,
        get_payslips,
        get_org_chart,
        get_employee_profile,
        submit_leave_request,
        search_policies,
        get_benefits_summary,
        get_attendance_records,
        get_overtime_hours,
        log_overtime,
    ]

    tools = []
    for fn in tool_fns:
        tool = StructuredTool.from_function(
            coroutine=fn,
            name=fn.__name__,
            description=fn.__doc__ or fn.__name__,
        )
        tools.append(tool)

    logger.info("Loaded MCP tools via direct import", count=len(tools))
    return tools
