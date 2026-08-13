"""FastAPI application entry point."""

import logging
import os
import socket
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db.chroma_client import chroma_client
from app.router import chat, memory, auth, transcribe, speak, llm_models, archiv

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
app.include_router(speak.router)
app.include_router(llm_models.router)
app.include_router(archiv.router)

def _lan_ip() -> Optional[str]:
    """LAN-Adresse des Geräts ermitteln, ohne Netzwerkverkehr zu erzeugen.

    Der UDP-Socket wird nur nominell "verbunden" – dabei wählt das
    Betriebssystem die Schnittstelle, über die es hinausgehen würde, und
    verrät so die eigene Adresse im Heimnetz.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(0.2)
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except Exception:
        return None


@app.get("/api/health", tags=["system"])
async def health_check():
    """Health check endpoint."""
    from app.services.llm_service import llm_service

    lan_ip = _lan_ip()

    return {
        "status": "ok",
        "version": "0.1.0",
        "llm_configured": llm_service.is_configured,
        "memory_count": chroma_client.count(),
        # Damit man vom PC aus zugreifen kann, ohne den Server zu beenden.
        "lan_ip": lan_ip,
        "lan_url": f"http://{lan_ip}:{settings.port}" if lan_ip else None,
    }


# Serve frontend static files at / – MUSS als Letztes registriert werden.
# Starlette matcht Routen in Registrierungsreihenfolge; dieser Mount fängt
# alles unter / ab und würde jede danach definierte API-Route verdecken.
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
    logger.info("Frontend served from: %s", FRONTEND_DIR)
else:
    logger.warning("Frontend directory not found: %s", FRONTEND_DIR)