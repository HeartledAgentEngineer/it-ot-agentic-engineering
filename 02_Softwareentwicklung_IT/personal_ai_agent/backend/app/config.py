"""Configuration management using pydantic-settings."""

from pydantic_settings import BaseSettings
from typing import Optional


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
    chroma_persist_dir: str = "./chroma_data"
    chroma_collection_name: str = "agent_memories"

    # Embedding
    embedding_model: str = "all-MiniLM-L6-v2"

    # System Prompt
    system_prompt_file: str = "./system_prompt.md"

    # Logging
    log_level: str = "INFO"

    # Security
    api_key: Optional[str] = None
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24h

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()