"""
Shared pytest fixtures for all test tiers.

Fixtures here are auto-available to all tests in backend/tests/.
External-service fixtures are skipped automatically when services are not running.
"""
from __future__ import annotations

import os
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio


# ── Environment setup ─────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def _set_test_env() -> None:
    """Override settings for the test environment before any imports."""
    os.environ.setdefault("ENVIRONMENT",  "test")
    os.environ.setdefault("SECRET_KEY",   "test_secret_key_min_32_chars_xxxxx")
    os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/testdb")
    os.environ.setdefault("CHROMA_HOST",  "localhost")
    os.environ.setdefault("LLM_BASE_URL", "http://localhost:4000/v1")
    os.environ.setdefault("LLM_API_KEY",  "test-key")
    os.environ.setdefault("LLM_MODEL",    "gemini-3.1-flash-lite")


# ── LLM mock ─────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_llm():
    """Return a mock ChatOpenAI that echoes a canned response."""
    from langchain_core.messages import AIMessage

    mock = MagicMock()
    mock.ainvoke = AsyncMock(return_value=AIMessage(content="رصيد إجازتك السنوية: 14 يوم"))
    mock.bind_tools = MagicMock(return_value=mock)
    return mock


# ── DB mock ───────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_db_session():
    """Return a mock AsyncSession suitable for repository tests."""
    session = MagicMock()
    session.execute   = AsyncMock()
    session.commit    = AsyncMock()
    session.rollback  = AsyncMock()
    session.close     = AsyncMock()
    return session


# ── RAG mock ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_retriever():
    """Return a mock HybridRetriever with a canned chunk response."""
    retriever = MagicMock()
    retriever.retrieve = AsyncMock(
        return_value=[
            {
                "text":         "يحق للموظف الحصول على 21 يوم عمل كإجازة سنوية مدفوعة.",
                "metadata":     {"section": "الإجازة السنوية", "page": 34, "source": "HR Handbook"},
                "score":        0.92,
                "rerank_score": 0.95,
            }
        ]
    )
    return retriever


# ── MCP tools mock ────────────────────────────────────────────────────────────

@pytest.fixture
def mock_mcp_tools():
    """Return an empty list of tools (agent won't call any tools)."""
    return []


# ── Marks for skipping when services are unavailable ─────────────────────────

def _service_available(host: str, port: int) -> bool:
    import socket

    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


requires_db = pytest.mark.skipif(
    not _service_available("localhost", 5432),
    reason="PostgreSQL not running on localhost:5432",
)

requires_llm = pytest.mark.skipif(
    not _service_available("localhost", 4000),
    reason="LLM API not running on localhost:4000",
)

requires_chromadb = pytest.mark.skipif(
    not _service_available("localhost", 8002),
    reason="ChromaDB not running on localhost:8002",
)

requires_full_stack = pytest.mark.skipif(
    not (
        _service_available("localhost", 8000)
        and _service_available("localhost", 5432)
    ),
    reason="Full stack not running (need backend:8000 + postgres:5432)",
)
