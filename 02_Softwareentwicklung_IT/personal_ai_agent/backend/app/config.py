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
    allowed_models_fallback: str = "deepseek/deepseek-v4-flash-0731,deepseek/deepseek-v4-flash"

# Schnellauswahl in der Oberfläche, nach Preis gestaffelt. Alle vier am
        # 11.08.2026 gegen /models/user geprüft. Wer hier nicht mehr nutzbar ist,
        # wird ausgegraut statt still entfernt – sonst merkt man Änderungen nicht.
        #   gpt-5-nano          sparsam
        #   deepseek-0731-v4    Alltag (günstigster V4 Flash, Favorit Sebastian)
        #   deepseek-v4-flash   Alltag, 1 Mio Kontext
        #   deepseek-v4-pro     mehr Substanz
        #   claude-sonnet-5     stark
        # Preise stehen bewusst nicht hier: /models/user liefert die des jeweils
        # routbaren Anbieters, die von den Katalogpreisen abweichen (V4 Flash
        # etwa 0,068/0,168 statt 0,14/0,28 $/Mio). Die Oberfläche zeigt sie live.
    favorite_models: List[str] = [
    "openai/gpt-5-nano",
    "deepseek/deepseek-v4-flash-0731",
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

    # Wissensspeicher aus den Chat-Archiven (Schwesterprojekt
    # "Chats von GPT, GEMINI, Claude"). Nur lesender Zugriff.
    # Leer = nicht eingebunden, der Agent laeuft dann wie bisher.
    #
    # Auf dem Handy liegt sie ueblicherweise unter:
    #   /sdcard/Download/memory.db
    # oder nach dem Verschieben in Termux:
    #   /data/data/com.termux/files/home/memory.db
    archiv_db_path: str = ""

    # Vektordatei zum Archiv (rohe float32-Matrix, 30.891 x 1024).
    # Ohne sie laeuft nur die Volltextsuche – die findet Woerter, aber keine
    # Bedeutung. Fuer "erzaehl mir von damals" braucht es die Vektoren.
    archiv_vektor_path: str = ""

    # Schluessel fuer die Frage-Einbettung. Die Chunks sind bereits gerechnet;
    # was fehlt, ist ein Vektor fuer die jeweilige Frage – ein Aufruf je
    # Suche, wenige Zehntausendstel Cent. Ohne Schluessel bleibt es beim
    # Volltext.
    mistral_api_key: str = ""
    mistral_embed_model: str = "mistral-embed"

    # Wie viele Archiv-Treffer hoechstens in den Prompt wandern. Jeder Treffer
    # ist ein Gespraechsausschnitt und kostet Token – fuenf sind ein
    # brauchbarer Ausgleich zwischen Kontext und Kosten.
    archiv_top_k: int = 5

    # Sprachausgabe – Microsoft läuft über Azure (EU-Rechenzentrum).
    # Gültige Stimmen liefert:
    #   GET /api/v1/models?output_modalities=speech → supported_voices
    tts_model: str = "microsoft/mai-voice-2-flash"
    tts_voice: str = "de-DE-Klaus:MAI-Voice-2"

    # System Prompt (liegt in backend/, nicht im Projektordner)
    system_prompt_file: str = str(BACKEND_DIR / "system_prompt.md")

    # Persoenlicher Teil des System-Prompts. Wird angehaengt, wenn die Datei
    # existiert, und ist per .gitignore vom Repo ausgenommen - dasselbe
    # Muster wie .env und .env.example.
    #
    # Grund: Das Repo ist oeffentlich. Profil, Geraete und Haltung des
    # Nutzers gehen niemanden etwas an, der sich den Code ansieht. Die
    # oeffentliche Datei beschreibt nur, wie der Agent arbeitet.
    system_prompt_local_file: str = str(BACKEND_DIR / "system_prompt.local.md")

    # Auftragsbuch fuer den Coding-Agenten (Hermes). Liegt neben chroma_data
    # und ist wie dieses per .gitignore ausgenommen: Es enthaelt, was der
    # Nutzer diktiert hat, und das Repo ist oeffentlich.
    auftraege_datei: str = str(BASE_DIR / "auftraege.json")

    # Nach wie vielen Minuten ein abgeholter Auftrag wieder als offen gilt.
    # Hermes arbeitet in kurzlebigen Sitzungen; bricht eine ab, wuerde der
    # Auftrag ohne diese Frist fuer immer haengen bleiben. Der Wert sollte
    # ueber dem Cron-Takt liegen, sonst holt sich der naechste Lauf einen
    # Auftrag, an dem noch gearbeitet wird.
    auftrag_timeout_minuten: int = 30

    # PC-Hermes (Track A): Der lokale Hermes-API-Server auf dem PC, den das
    # Handy-Backend bei erkannter Programmieraufgabe direkt anspricht, wenn
    # der PC im selben WLAN erreichbar ist. Ist er das nicht, faellt die
    # Weiche aufs Auftragsbuch zurueck (Track B, unveraendert).
    #
    # Die IP ist die lokale Adresse des PCs (nicht localhost, denn das
    # Backend laeuft auf dem Handy). Sie kommt in die .env dieses Projekts
    # (nicht in den Code).
    hermes_pc_base_url: str = ""
    hermes_pc_api_key: str = ""
    hermes_pc_timeout: int = 30

    # Track-C-Andocken (zwei-Stellen-Steuerung, ab 2026-08-31): Ist gesetzt,
    # docken lokale Hermes-Auftraege an diese BEREITS laufende tmux-Session an,
    # statt eine NEUE 'hermes chat'-Session zu starten. So sprechen Nutzer
    # (Frontend-Chat) + Backend mit derselben Hermes-Instanz. Leer = Standard
    # (neue Session je Auftrag). Kommt aus der .env, nie in den Code.
    hermes_local_session: str = ""

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
        # Unbekannte Variablen in der .env (z. B. altes db_path oder fremde
        # Zeilen) IGNORIEREN statt crashen. Vorher brach der Server beim Start
        # mit pydantic extra_forbidden ab, sobald eine fremde Variable drin
        # stand. Nur deklarierte Settings sind relevant; der Rest ist egal.
        extra = "ignore"


settings = Settings()