"""Configuration management using pydantic-settings."""

import logging
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings
from typing import List, Optional

logger = logging.getLogger(__name__)

# Pfade werden am Projektordner verankert, nicht am Arbeitsverzeichnis.
# Sonst entscheidet der Ordner, aus dem uvicorn gestartet wurde, darüber,
# ob Schlüssel, Gedächtnis und System-Prompt gefunden werden – und ein
# Fehlstart legt still ein leeres Gedächtnis an, ohne Fehlermeldung.
BASE_DIR = Path(__file__).resolve().parents[2]   # .../personal_ai_agent
BACKEND_DIR = BASE_DIR / "backend"

# ── Workspace-Wurzel und ihr Schlüssel-Fallback (25.09.2026) ────────────────
#
# Die projektüblichen .env-Dateien sind `personal_ai_agent/.env` und
# `personal_ai_agent/backend/.env` (siehe `class Config` unten). Auf dem PC
# existierte keine von beiden; der OpenRouter-Schlüssel lag in der `.env` der
# **Workspace-Wurzel** zwei Ebenen darüber. Folge: `openrouter_api_key` blieb
# leer, `archiv_suche` konnte die Suchfrage nicht einbetten, und der Agent
# wich für Fragen nach der eigenen Vergangenheit ins Web aus.
#
# Deshalb dieser Fallback: Ist OPENROUTER_API_KEY in den projektüblichen
# Quellen leer, wird er zusätzlich aus der Workspace-Wurzel-`.env` gelesen.
#
# BEWUSST GENAU EIN VARIABLENNAME: Die Datei gehört nicht diesem Projekt und
# kann Variablen anderer Projekte enthalten (HOST, PORT, …). Wäre sie als
# ganze Konfigurationsdatei eingebunden, könnte ein Nachbarprojekt diese App
# still umkonfigurieren. Werte aus ihr werden nie geloggt, nie ausgegeben und
# nie in die Doku geschrieben — nur weitergereicht.
WORKSPACE_DIR = BASE_DIR.parent.parent           # .../workspace agentic engineering
WORKSPACE_ENV_FILE = WORKSPACE_DIR / ".env"
SCHLUESSEL_FALLBACK_VARIABLE = "OPENROUTER_API_KEY"


def variable_aus_env_datei(pfad: Path, name: str) -> str:
    """Eine einzelne Variable aus einer .env-Datei lesen — sonst nichts.

    Absichtlich ein eigener, kleiner Leser statt pydantic-settings: Nur so ist
    garantiert, dass aus einer fremden Datei genau EIN Variablenname gelesen
    wird. Der Wert wird zurückgegeben, aber nie geloggt und nie dokumentiert.

    Fehlende Datei, fehlender Name oder Lesefehler: leerer String.
    """
    try:
        datei = Path(pfad)
        if not datei.is_file():
            return ""
        for zeile in datei.read_text(encoding="utf-8", errors="replace").splitlines():
            zeile = zeile.strip()
            if not zeile or zeile.startswith("#") or "=" not in zeile:
                continue
            kennung, _, wert = zeile.partition("=")
            kennung = kennung.strip()
            if kennung.startswith("export "):
                kennung = kennung[len("export "):].strip()
            if kennung != name:
                continue
            return wert.strip().strip('"').strip("'")
    except OSError:
        return ""
    return ""


class Settings(BaseSettings):
    """Application settings loaded from .env or environment variables."""

    # OpenRouter
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    # Geprüft am 11.08.2026: deepseek-chat ist mit den Privacy-/Provider-
    # Einstellungen dieses Kontos NICHT routbar und kostet bei der Ausgabe
    # das 3,7-Fache (1,029 statt 0,280 $/Mio). Die Oberfläche behauptete
    # ohnehin schon "V4 Flash" – hier stand nur nie das passende Modell.
    # Aktuellstes DeepSeek-Flash (V4.1) als Standard-Modell der App.
    # Hinweis: OpenRouter-ID ist `deepseek/deepseek-v4.1-flash` (mit Punkt).
    # Hermes selbst (CLI, ~/.hermes/config.yaml) läuft ebenfalls auf diesem Modell.
    llm_model: str = "deepseek/deepseek-v4.1-flash"

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
    allowed_models_fallback: str = "deepseek/deepseek-v4.1-flash,deepseek/deepseek-v4-flash-0731,deepseek/deepseek-v4-flash"

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
    "deepseek/deepseek-v4.1-flash",
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

    # Einbettungen fuer die Erinnerungen laufen ueber OpenRouter (Entscheidung
    # Sebastian, 25.09.2026; siehe docs/konzept-gedaechtnis.md
    # §„Entschieden 25.09.2026"). OpenAI-kompatibler Endpunkt:
    #   POST {openrouter_base_url}/embeddings  {"model": ..., "input": [text]}
    # Moegliche Modelle des Kontos: GET {openrouter_base_url}/embeddings/models
    # Preis des Beispielmodells ~0,02 $/1 Mio Token.
    #
    # Die frueheren Wege sind ENTFALLEN: ein lokales Modell
    # (sentence-transformers, auf keinem der beiden Geraete installiert) und
    # Mistral-Embeddings. Beide sind durch openrouter_embed_model ersetzt.
    openrouter_embed_model: str = "openai/text-embedding-3-small"

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

    # Index des Wissensspeichers (eine SQLite-Datei mit Nachrichten, Chunks,
    # FTS5-Volltextindex und Vektoren). Gebaut wird er von
    # `backend/scripts/archiv_index_bauen.py` im Schwesterprojekt; hier wird
    # nur gelesen (`mode=ro`).
    #
    # Standard ist der vorhandene Archivpfad — bewusst NICHT im Projektordner,
    # weil der Ordner per .gitignore aus dem Repo ausgenommen ist und eine
    # 240-MB-Datei mit den vollstaendigen Gespraechen sonst mitcommittet werden
    # koennte.
    #
    # Suchreihenfolge von `archiv_suche` (erster vorhandener Kandidat gewinnt):
    #   1. dieses Setting (per .env: ARCHIV_INDEX_PATH ueberschreibbar)
    #   2. Umgebungsvariable ARCHIV_INDEX_PATH
    #   3. personal_ai_agent/archiv_index.db
    #   4. personal_ai_agent/backend/archiv_index.db
    #   5. <Workspace-Wurzel>/Chats von GPT, GEMINI, Claude/db/archiv_index.db
    #   6. /sdcard/Download/archiv_index.db                     (Handy)
    #   7. /data/data/com.termux/files/home/archiv_index.db     (Handy, Termux)
    # Ein Pfad, der nicht existiert, faellt ehrlich durch auf den naechsten;
    # ist keiner da, meldet die Suche "kein_index" statt zu crashen.
    archiv_index_path: str = str(
        WORKSPACE_DIR / "Chats von GPT, GEMINI, Claude" / "db" / "archiv_index.db"
    )

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

    # Track-C-Kanal (Zweitweg, 2026-09-01): 
    #   "query"  = Einmal-Subprozess `hermes chat -q ... -Q` an die Termux-
    #              Session statt tmux (deterministisch, Kontext automatisch).
    #   "aktiv"  = Inbox-Kanal an die LAUFENDE Termux-Hermes-Session (ohne
    #              tmux): Server schreibt Auftraege in ~/hermes_inbox/, die
    #              aktive Session antwortet. Fuer "Server redet mit mir".
    #   "" / "tmux" = klassischer tmux-Weg.
    hermes_local_kanal: str = ""

    # Modell fuer die LOKALEN Hermes-Laeufe (Coding-Agent). Der Inbox-Daemon,
    # die tmux-Session und der query-Zweitweg starten `hermes chat` mit diesem
    # Modell. Wunsch Sebastian (2026-09-15): DeepSeek V4.1 Flash, damit der
    # Coding-Agent intern dasselbe Modell faehrt wie der Chat.
    hermes_local_model: str = "deepseek/deepseek-v4.1-flash"

    # Gesamt-Zeitbudget eines lokalen Hermes-Auftrags in Sekunden. Coding-
    # Auftraege brauchen regelmaessig laenger als 15 Minuten — der frueher
    # feste 900s-Abbruch ("Timeout nach 900s: keine Antwort der aktiven
    # Session") war die Ursache fuer abgebrochene Coding-Laeufe.
    hermes_auftrag_timeout: int = 3600

    # Ruhe-Budget in Sekunden: So lange OHNE neue Zwischenmeldung darf ein
    # Auftrag still sein, bevor der Stream einen Hinweis ausgibt (der Auftrag
    # laeuft weiter, es wird NICHT abgebrochen).
    hermes_auftrag_idle: int = 420

    # Logging
    log_level: str = "INFO"

    # Security
    api_key: Optional[str] = None
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24h

    @model_validator(mode="after")
    def _schluessel_aus_workspace_wurzel(self):
        """OPENROUTER_API_KEY aus der Workspace-Wurzel-`.env` nachtragen.

        Greift nur, wenn der Schluessel in den projektueblichen Quellen
        (Umgebungsvariable, `personal_ai_agent/.env`, `backend/.env`) leer
        ist — und liest aus der fremden Datei ausschliesslich
        :data:`SCHLUESSEL_FALLBACK_VARIABLE`.

        Ehrlich statt still: Ob der Schluessel da ist oder fehlt, steht als
        Hinweis im Log (ohne Wert). Der Dienst degradiert bei fehlendem
        Schluessel sichtbar auf Volltextsuche (siehe ``archiv_suche``).
        """
        if (self.openrouter_api_key or "").strip():
            return self
        wert = variable_aus_env_datei(WORKSPACE_ENV_FILE, SCHLUESSEL_FALLBACK_VARIABLE)
        if wert:
            self.openrouter_api_key = wert
            logger.info(
                "%s aus der Workspace-Wurzel-.env uebernommen (nur dieser eine "
                "Variablenname; Wert wird nicht protokolliert).",
                SCHLUESSEL_FALLBACK_VARIABLE,
            )
        else:
            logger.warning(
                "%s fehlt in Umgebung, %s und %s. Bedeutungssuche (Vektoren) "
                "bleibt aus, es wird nur nach Wortlaut gesucht.",
                SCHLUESSEL_FALLBACK_VARIABLE,
                BASE_DIR / ".env",
                BACKEND_DIR / ".env",
            )
        return self

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