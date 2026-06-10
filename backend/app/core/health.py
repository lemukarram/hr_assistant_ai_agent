"""
Detailed health checks for all downstream dependencies.
Called by GET /health/detailed — keeps the liveness probe fast.
"""
from __future__ import annotations

import asyncio
from typing import Any

import chromadb
import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


async def _check_postgres() -> dict[str, Any]:
    try:
        from sqlalchemy import text
        from app.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


async def _check_chromadb() -> dict[str, Any]:
    try:
        client = chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)
        client.heartbeat()
        collection = client.get_or_create_collection(settings.CHROMA_COLLECTION_NAME)
        return {"status": "ok", "chunk_count": collection.count()}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


async def _check_llm() -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{settings.LLM_BASE_URL}/models",
                headers={"Authorization": f"Bearer {settings.LLM_API_KEY}"},
            )
            resp.raise_for_status()
            return {
                "status": "ok",
                "model": settings.LLM_MODEL,
                "base_url": settings.LLM_BASE_URL,
            }
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


async def _check_mcp_server() -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get(f"{settings.MCP_SERVER_URL}/health")
            return {"status": "ok" if resp.is_success else "degraded"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


async def check_all_services() -> dict[str, Any]:
    postgres, chroma, llm, mcp = await asyncio.gather(
        _check_postgres(),
        _check_chromadb(),
        _check_llm(),
        _check_mcp_server(),
        return_exceptions=False,
    )

    all_ok = all(
        s.get("status") == "ok"
        for s in [postgres, chroma, llm, mcp]
    )

    return {
        "status": "ok" if all_ok else "degraded",
        "services": {
            "postgres": postgres,
            "chromadb": chroma,
            "llm": llm,
            "mcp_server": mcp,
        },
    }
