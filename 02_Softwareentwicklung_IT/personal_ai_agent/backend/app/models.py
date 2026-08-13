"""Pydantic models for request/response validation."""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime


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


class ChatResponse(BaseModel):
    """Response from the LLM."""
    reply: str
    conversation_id: str
    memories_used: int = 0
    memories_created: int = 0
    sources: List[Source] = []
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
    content: str
    category: str = "fact"
    importance: int = 3
    conversation_id: Optional[str] = None


class MemoryListResponse(BaseModel):
    """List of memories."""
    memories: List[MemoryItem]
    total: int


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