"""Pydantic models for request/response validation."""

from pydantic import BaseModel, Field
from typing import Optional, List
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
    web_search: bool = False


class ChatResponse(BaseModel):
    """Response from the LLM."""
    reply: str
    conversation_id: str
    memories_used: int = 0
    memories_created: int = 0
    sources: List[Source] = []


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