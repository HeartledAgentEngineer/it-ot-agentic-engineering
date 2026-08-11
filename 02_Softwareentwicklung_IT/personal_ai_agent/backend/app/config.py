"""Configuration management using pydantic-settings."""

from pathlib import Path

from pydantic_settings import BaseSettings
from typing import List, Optional

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
    # Geprüft am 11.08.2026: deepseek-chat ist mit den Privacy-/Provider-
    # Einstellungen dieses Kontos NICHT routbar und kostet bei der Ausgabe
    # das 3,7-Fache (1,029 statt 0,280 $/Mio). Die Oberfläche behauptete
    # ohnehin schon "V4 Flash" – hier stand nur nie das passende Modell.
    llm_model: str = "deepseek/deepseek-v4-flash"

    # Nur für den Modellkatalog, NIE für Chat-Aufrufe: Über diese Adresse
    # lässt sich abfragen, welche Modelle EU-in-Region bedient würden.
    # Der Chat darüber ist für dieses Konto gesperrt (HTTP 403, Enterprise).
    openrouter_eu_base_url: str = "https://eu.openrouter.ai/api/v1"

    # Anbieter-Whitelist des OpenRouter-Kontos ("Allowed Providers"),
    # kommaseparierte Slugs. Leer bedeutet "unbekannt" – dann werden alle
    # Anbieter weltweit gezählt und die Oberfläche schreibt das auch dazu.
    #
    # Warum das von Hand gepflegt werden muss: OpenRouter gibt die Whitelist
    # über keine Route heraus. `GET /api/v1/key` liefert nur Nutzungsdaten.
    # ACHTUNG: Wird sie im OpenRouter-Konto geändert, muss dieser Wert
    # nachgezogen werden – sonst rechnet die Anzeige mit einem alten Stand.
    #
    # Stand 11.08.2026:
    #   ai21,azure,cohere,google-vertex,nebius,mistral,cloudflare,
    #   digitalocean,amazon-bedrock,black-forest-labs,claude-on-aws
    provider_whitelist: str = ""

    # Modellauswahl – datenschutz-konform.
    # Die erlaubten Modelle werden dynamisch über GET /models/user geladen
    # (OpenRouter respektiert dabei die Privacy-/Provider-Einstellungen des
    # Accounts). Kommt die API nicht an, greift diese Fallback-Liste.
    # Kommagetrennte Modell-IDs.
    allowed_models_fallback: str = "deepseek/deepseek-v4-flash"

    # Schnellauswahl in der Oberfläche, nach Preis gestaffelt. Alle vier am
    # 11.08.2026 gegen /models/user geprüft. Wer hier nicht mehr nutzbar ist,
    # wird ausgegraut statt still entfernt – sonst merkt man Änderungen nicht.
    #   gpt-5-nano          sparsam
    #   deepseek-v4-flash   Alltag, 1 Mio Kontext
    #   deepseek-v4-pro     mehr Substanz
    #   claude-sonnet-5     stark
    # Preise stehen bewusst nicht hier: /models/user liefert die des jeweils
    # routbaren Anbieters, die von den Katalogpreisen abweichen (V4 Flash
    # etwa 0,068/0,168 statt 0,14/0,28 $/Mio). Die Oberfläche zeigt sie live.
    favorite_models: List[str] = [
        "openai/gpt-5-nano",
        "deepseek/deepseek-v4-flash",
        "deepseek/deepseek-v4-pro",
        "anthropic/claude-sonnet-5",
    ]

    # Wie lange die Modell-Liste im Speicher gecacht bleibt (Sekunden).
    # 6 Stunden: Der Katalog ändert sich selten, und jeder Abruf sind drei
    # HTTP-Anfragen. Für einen Test kurzzeitig kleiner setzen.
    models_cache_ttl: int = 21600

    # Server
    host: str = "0.0.0.0"
    port: int = 8080

    # ChromaDB
    chroma_persist_dir: str = str(BASE_DIR / "chroma_data")
    chroma_collection_name: str = "agent_memories"

    # Embedding
    embedding_model: str = "all-MiniLM-L6-v2"

    # Sprachausgabe – Microsoft läuft über Azure (EU-Rechenzentrum).
    # Gültige Stimmen liefert:
    #   GET /api/v1/models?output_modalities=speech → supported_voices
    tts_model: str = "microsoft/mai-voice-2-flash"
    tts_voice: str = "de-DE-Klaus:MAI-Voice-2"

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