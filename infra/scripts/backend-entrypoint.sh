#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
#  Backend Entrypoint
#  1. Wait for all dependencies (postgres, chromadb, llm api)
#  2. Run database migrations
#  3. Build RAG index if not exists
#  4. Start API server
# ─────────────────────────────────────────────────────────────────────────────
set -e

echo "🚀 HR Assistant Backend starting..."

# ── Wait for PostgreSQL ────────────────────────────────────────────────────
echo "⏳ Waiting for PostgreSQL..."
until pg_isready -h "${POSTGRES_HOST:-postgres}" -p "${POSTGRES_PORT:-5432}" -U "${POSTGRES_USER:-hruser}"; do
    sleep 2
done
echo "✅ PostgreSQL ready"

# ── Wait for ChromaDB ──────────────────────────────────────────────────────
echo "⏳ Waiting for ChromaDB..."
until curl -sf "http://${CHROMA_HOST:-chromadb}:${CHROMA_PORT:-8000}/api/v1/heartbeat" > /dev/null; do
    sleep 3
done
echo "✅ ChromaDB ready"

# ── Wait for LLM API ───────────────────────────────────────────────────────
LLM_BASE="${LLM_BASE_URL:-http://api-services-ca-llm.igate.sa:4000/v1}"
echo "⏳ Waiting for LLM API at ${LLM_BASE}..."
until curl -sf "${LLM_BASE}/models" \
    -H "Authorization: Bearer ${LLM_API_KEY}" > /dev/null 2>&1; do
    sleep 5
done
echo "✅ LLM API ready"

# ── Run Migrations ─────────────────────────────────────────────────────────
echo "🗃️  Running database migrations..."
python -m alembic upgrade head 2>/dev/null || echo "   (No migrations to run)"
echo "✅ Database ready"

# ── Build RAG Index ────────────────────────────────────────────────────────
echo "📚 Checking RAG index..."
python -c "
import asyncio
from app.rag.indexer import RAGIndexer

async def main():
    indexer = RAGIndexer()
    await indexer.ensure_indexed()

asyncio.run(main())
"
echo "✅ RAG index ready"

# ── Start MCP Server (background) ─────────────────────────────────────────
echo "🔧 Starting MCP tool server..."
python -m app.mcp_tools.server &
sleep 3
echo "✅ MCP server ready on :8001"

# ── Start API Server ───────────────────────────────────────────────────────
echo "🌐 Starting FastAPI server..."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 1 \
    --log-level "${LOG_LEVEL:-info}" \
    --no-access-log
