"""Configuration management using pydantic-settings."""

from pathlib import Path

from pydantic_settings import BaseSettings
from typing import Optional

# Pfade werden am Projektordner verankert, nicht am Arbeitsverzeichnis.
# Sonst entscheidet der Ordner, aus dem uvicorn gestartet wurde, darüber,
# ob Schlüssel, Gedächtnis und System-Prompt gefunden werden – und ein
# Fehlstart legt still ein leeres Gedächtnis an, ohne Fehlermeldung.
BASE_DIR = Path(__file__).resolve().parents[2]   # .../personal_ai_agent
BACKEND_DIR = BASE_DIR / "backend"


class Settings(BaseSettings):
    """Application settings loaded from .env or environment variables."""

    # OpenRouter
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    # OpenRouter model name – bei Neuinstallation auf aktuelle Version prüfen!
    # https://openrouter.ai/models?q=deepseek
    llm_model: str = "deepseek/deepseek-chat"

    # Server
    host: str = "0.0.0.0"
    port: int = 8080

    # ChromaDB
    chroma_persist_dir: str = str(BASE_DIR / "chroma_data")
    chroma_collection_name: str = "agent_memories"

    # Embedding
    embedding_model: str = "all-MiniLM-L6-v2"

    # System Prompt (liegt in backend/, nicht im Projektordner)
    system_prompt_file: str = str(BACKEND_DIR / "system_prompt.md")

    # Logging
    log_level: str = "INFO"

    # Security
    api_key: Optional[str] = None
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24h

    class Config:
        # Beide üblichen Ablageorte akzeptieren, damit es egal ist, wo die
        # .env liegt. Der hintere Eintrag gewinnt, falls es beide gibt.
        env_file = (BASE_DIR / ".env", BACKEND_DIR / ".env")
        env_file_encoding = "utf-8"


settings = Settings()