"""
Router: POST /api/speak – Antwort mit natürlicher Stimme vorlesen

Verhalten:
  1. Nimmt Text entgegen (Länge begrenzt)
  2. Schickt ihn an microsoft/mai-voice-2-flash über OpenRouter
  3. Gibt MP3-Daten zurück, die der Browser direkt abspielt

Sicherheit:
  - Längenbegrenzung als Kostenbremse (jede Anfrage kostet Geld)
  - Kein API-Key im Request oder in der Antwort
  - Fehler werden als 502 gemeldet, der Grund landet im Log
"""

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["speak"])

# Kostenbremse: Zu lange Texte werden abgewiesen, nicht still gekürzt –
# sonst hört man das Ende nicht und wundert sich.
MAX_ZEICHEN = 2000


class SpeakRequest(BaseModel):
    """Vorzulesender Text."""
    text: str = Field(..., min_length=1, max_length=MAX_ZEICHEN)


@router.post("/speak")
async def speak(request: SpeakRequest):
    """Liest den übergebenen Text vor und liefert das Ergebnis als MP3."""
    audio = llm_service.speak(request.text)

    if not audio:
        logger.warning("Sprachausgabe lieferte nichts (%d Zeichen)", len(request.text))
        raise HTTPException(
            status_code=502,
            detail="Sprachausgabe fehlgeschlagen – Details stehen im Server-Log.",
        )

    return Response(
        content=audio,
        media_type="audio/mpeg",
        headers={"Cache-Control": "no-store"},
    )
