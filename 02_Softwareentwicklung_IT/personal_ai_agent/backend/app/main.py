"""FastAPI application entry point."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db.chroma_client import chroma_client
from app.router import chat, memory, auth, transcribe

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Path to frontend directory (relative to this backend/app/main.py)
FRONTEND_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle: startup and shutdown events."""
    # Startup
    logger.info("=" * 50)
    logger.info("Personal AI Agent – Starting up...")
    logger.info("=" * 50)

    # Initialize memory store
    try:
        chroma_client.connect()
        memory_count = chroma_client.count()
        logger.info("Memory store ready: %d memories", memory_count)
    except Exception as e:
        logger.warning(
            "Memory store initialization failed: %s. "
            "Memory features will be unavailable until restart.",
            e,
        )

    # Check LLM configuration
    from app.services.llm_service import llm_service

    if llm_service.is_configured:
        logger.info(
            "LLM configured: model=%s, base_url=%s",
            settings.llm_model,
            settings.openrouter_base_url,
        )
    else:
        logger.warning(
            "LLM NOT configured! Set OPENROUTER_API_KEY in .env"
        )

    logger.info("Server starting on %s:%s", settings.host, settings.port)

    yield

    # Shutdown
    logger.info("Shutting down Personal AI Agent...")
    logger.info("Goodbye.")


# Create FastAPI app
app = FastAPI(
    title="Personal AI Agent",
    description="Ein datenschutzkonformer, persönlicher KI-Assistent",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS – allow all origins for MVP (runs on same device)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers (they define their own /api prefix)
app.include_router(chat.router)
app.include_router(memory.router)
app.include_router(auth.router)
app.include_router(transcribe.router)

# Serve frontend static files at / (MUST be after API routers)
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
    logger.info("Frontend served from: %s", FRONTEND_DIR)
else:
    logger.warning("Frontend directory not found: %s", FRONTEND_DIR)


@app.get("/api/health", tags=["system"])
async def health_check():
    """Health check endpoint."""
    from app.services.llm_service import llm_service

    return {
        "status": "ok",
        "version": "0.1.0",
        "llm_configured": llm_service.is_configured,
        "memory_count": chroma_client.count(),
    }