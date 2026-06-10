"""
HR Assistant — FastAPI Application Entry Point
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.session import init_db
from app.rag.indexer import RAGIndexer

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    configure_logging()
    logger.info("🚀 Starting HR Assistant Backend", version=settings.VERSION)

    # Initialize database connection pool
    await init_db()
    logger.info("✅ Database connection established")

    # Build / verify RAG index
    indexer = RAGIndexer()
    await indexer.ensure_indexed()
    logger.info("✅ RAG index ready")

    logger.info("✅ API server ready", host="0.0.0.0", port=8000)
    yield

    logger.info("⏹️  Shutting down HR Assistant Backend")


app = FastAPI(
    title="HR Assistant API",
    description="Arabic-first agentic HR assistant with RAG and MCP tools",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Middleware ────────────────────────────────────────────────────────────────
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(api_router, prefix="/api")


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/health/detailed", tags=["Health"])
async def health_detailed():
    from app.core.health import check_all_services
    return await check_all_services()
