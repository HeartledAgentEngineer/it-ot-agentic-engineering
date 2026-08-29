"""Pydantic models for request/response validation."""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime


class FileAttachment(BaseModel):
    """Eine dem Chat beigefügte Datei.

    Wird vom Frontend nach dem Upload ans Backend geschickt.
    Das Backend hat die Datei dann bereits auf der Platte und
    kann sie für den LLM-Aufruf konvertieren (Bild → Base64,
    PDF → Text).
    """
    id: str
    filename: str
    type: Literal["image", "pdf"]
    url: str
    mime: str
    # Base64-codiertes Bild (nur bei image)
    data_url: Optional[str] = None
    # Extrahierter Text (nur bei pdf)
    text: Optional[str] = None


class Source(BaseModel):
    """Eine Fundstelle aus der Websuche."""
    url: str
    title: str


class ChatRequest(BaseModel):
    """Incoming chat message from the user."""
    message: str = Field(..., min_length=1, max_length=10000)
    conversation_id: Optional[str] = None
    # Websuche kostet je Anfrage extra, deshalb standardmäßig aus.
    #   off    – gar keine Suche
    #   manual – sucht bei jeder Nachricht (Plugin, eine Suche pro Anfrage)
    #   auto   – das Modell entscheidet selbst (Server-Werkzeug)
    web_search: Literal["off", "manual", "auto"] = "off"
    # Abweichendes Modell für diese eine Anfrage. Ohne Angabe gilt das aus
    # der Konfiguration – so bleibt das Backend zustandslos und zwei Geräte
    # kommen sich nicht in die Quere.
    model: Optional[str] = None
    # Datenschutz-Riegel: schickt provider.data_collection="deny" mit, damit
    # die Anfrage garantiert nicht bei einem Anbieter landet, der Prompts
    # speichert. Passt keiner, wird sie abgelehnt – sichtbar statt still.
    no_retention: bool = False
    # Chat-Archive mitdurchsuchen. Standard an – ohne den Wissensspeicher
    # kann der Agent nichts über die eigene Vergangenheit sagen. Abschaltbar,
    # falls eine Frage nichts damit zu tun hat.
    archiv: bool = True
    # Beigefügte Dateien (Bilder, PDFs) – optional
    files: Optional[List[FileAttachment]] = None


class ChatResponse(BaseModel):
    """Response from the LLM."""
    reply: str
    conversation_id: str
    memories_used: int = 0
    memories_created: int = 0
    sources: List[Source] = []
    # Bild-Vorschau (flüchtig): data_url + Pfad des Bildes, das der Agent
    # aus der Dateisuche analysiert hat. Das Frontend zeigt es kurz an und
    # verwirft es — es wird NICHTS gespeichert (nur in-memory/transient).
    bild_vorschau: Optional[str] = None
    bild_pfad: Optional[str] = None
    archiv_used: int = 0


class MemoryItem(BaseModel):
    """A single memory/fact stored in the vector DB."""
    id: Optional[str] = None
    content: str = Field(..., min_length=1, max_length=5000)
    category: str = Field(default="fact", pattern="^(fact|preference|context|project)$")
    importance: int = Field(default=3, ge=1, le=5)
    timestamp: Optional[str] = None
    conversation_id: Optional[str] = None

    class Config:
        from_attributes = True


class MemoryCreate(BaseModel):
    """Request to create a memory."""
    content: str = Field(..., min_length=1, max_length=5000)
    category: str = Field(default="fact", pattern="^(fact|preference|context|project)$")
    importance: int = Field(default=3, ge=1, le=5)
    conversation_id: Optional[str] = None


class MemoryListResponse(BaseModel):
    """List of memories."""
    memories: List[MemoryItem]
    total: int


class AuftragCreate(BaseModel):
    """Ein neuer Auftrag an den Coding-Agenten."""
    auftrag: str = Field(..., min_length=1, max_length=10000)
    hinweis: Optional[str] = Field(default=None, max_length=5000)
    kategorie: Optional[str] = Field(default=None, max_length=50)
    komplexitaet: Optional[str] = Field(default=None, max_length=20)


class AuftragItem(BaseModel):
    """Ein Auftrag samt Stand."""
    id: str
    auftrag: str
    hinweis: Optional[str] = None
    kategorie: Optional[str] = None
    komplexitaet: Optional[str] = None
    status: str
    erstellt: str
    abgeholt: Optional[str] = None
    beendet: Optional[str] = None
    ergebnis: Optional[str] = None
    status_meldungen: list[str] = []
    rueckfragen: list[dict] = []


class AuftragListResponse(BaseModel):
    """Liste von Auftraegen."""
    auftraege: List[AuftragItem]
    total: int


class ErgebnisCreate(BaseModel):
    """Rueckmeldung des Coding-Agenten zu einem Auftrag."""
    ergebnis: str = Field(..., min_length=1, max_length=50000)
    erfolg: bool = True


class StatusMeldungCreate(BaseModel):
    """Zwischenstand des Coding-Agenten."""
    meldung: str = Field(..., min_length=1, max_length=10000)


class RueckfrageCreate(BaseModel):
    """Rückfrage des Coding-Agenten an den Nutzer."""
    frage: str = Field(..., min_length=1, max_length=5000)
    kontext: Optional[str] = Field(default=None, max_length=5000)


class EingabeCreate(BaseModel):
    """Nutzer-Kommentar an einen laufenden Coding-Agenten (Live-Eingabe)."""
    text: str = Field(..., min_length=1, max_length=5000)


class AntwortCreate(BaseModel):
    """Antwort des Nutzers auf eine Rückfrage."""
    antwort: str = Field(..., min_length=1, max_length=5000)


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"
    version: str = "0.1.0"
    llm_configured: bool = False
    memory_available: bool = False


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: Optional[str] = None
