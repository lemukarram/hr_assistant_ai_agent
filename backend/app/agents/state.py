"""
LangGraph agent state schema.

Single source of truth for the state dictionary that flows through
every node in the HR Assistant graph.  TypedDict with total=False
means every field is optional — nodes only need to return the keys
they changed.
"""
from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    # ── Conversation ──────────────────────────────────────────────────────
    messages: list[Any]           # LangChain BaseMessage objects
    employee_id: str              # UUID string — ALWAYS from JWT, never user input
    session_id: str | None

    # ── Intent classification ─────────────────────────────────────────────
    intent: str | None
    # leave_balance | leave_action | payslip | policy | benefits | org_chart | profile | general
    language: str                 # "ar" | "en" | "mixed"

    # ── RAG ───────────────────────────────────────────────────────────────
    retrieved_context: list[dict[str, Any]]   # Handbook chunks with score + metadata

    # ── Security ──────────────────────────────────────────────────────────
    security_passed: bool         # True = safe; False = blocked
    block_reason: str | None      # Populated when security_passed=False

    # ── Output ────────────────────────────────────────────────────────────
    response: str | None          # Final text for non-streaming path
    sources: list[dict]           # Citations to surface in the UI


def make_initial_state(
    employee_id: str,
    session_id: str | None = None,
    language: str = "ar",
) -> AgentState:
    """
    Factory for a clean initial AgentState.
    Always pass employee_id from the validated JWT — never from user input.
    """
    return AgentState(
        messages=[],
        employee_id=str(employee_id),
        session_id=session_id,
        intent=None,
        language=language,
        retrieved_context=[],
        security_passed=False,
        block_reason=None,
        response=None,
        sources=[],
    )
