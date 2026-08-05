"""
Router: Sprachausgabe

  POST /api/speak        Text vorlesen, liefert MP3
  GET  /api/voices       Alle Sprachmodelle mit ihren Stimmen
  GET  /api/speak/demo   Hörprobe zum direkten Abspielen im Browser

Die Hörprobe gibt es als GET, damit man sie am Handy einfach als Adresse
aufrufen kann – der Browser spielt MP3 dann von selbst ab. So lassen sich
Stimmen vergleichen, ohne dass dafür eine Oberfläche nötig wäre.

Sicherheit:
  - Längenbegrenzung als Kostenbremse (jede Anfrage kostet Geld)
  - Kein API-Key im Request oder in der Antwort
  - Fehler werden als 502 gemeldet, der Grund landet im Log
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.config import settings
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["speak"])

# Kostenbremse: Zu lange Texte werden abgewiesen, nicht still gekürzt –
# sonst hört man das Ende nicht und wundert sich.
MAX_ZEICHEN = 2000

DEMO_SATZ = (
    "Hallo Sebastian. So klinge ich. Ich bin dein persönlicher Assistent "
    "und lese dir deine Antworten vor, wenn du es möchtest."
)


class SpeakRequest(BaseModel):
    """Vorzulesender Text, optional mit abweichender Stimme."""
    text: str = Field(..., min_length=1, max_length=MAX_ZEICHEN)
    voice: Optional[str] = None
    model: Optional[str] = None


def _als_mp3(audio: Optional[bytes], was: str) -> Response:
    """Gemeinsame Antwort für beide Wege."""
    if not audio:
        logger.warning("Sprachausgabe lieferte nichts (%s)", was)
        raise HTTPException(
            status_code=502,
            detail="Sprachausgabe fehlgeschlagen – Details stehen im Server-Log.",
        )
    return Response(
        content=audio,
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": "inline",
        },
    )


@router.post("/speak")
async def speak(request: SpeakRequest):
    """Liest den übergebenen Text vor und liefert das Ergebnis als MP3."""
    audio = llm_service.speak(request.text, voice=request.voice, model=request.model)
    return _als_mp3(audio, f"{len(request.text)} Zeichen")


@router.get("/voices")
async def voices():
    """Alle verfügbaren Sprachmodelle mit Stimmen und Preis.

    Achtung: Nur Microsoft kennzeichnet seine Stimmen nach Sprache. Die
    übrigen Modelle sind mehrsprachig und richten sich nach dem Text –
    dort hilft nur Zuhören, keine Liste.
    """
    modelle = llm_service.list_voices()
    return {
        "hinweis": (
            "Hörprobe: /api/speak/demo?model=<modell>&voice=<stimme>"
        ),
        "aktuell": {
            "model": settings.tts_model,
            "voice": settings.tts_voice,
        },
        "models": modelle,
        "total": len(modelle),
    }


@router.get("/speak/demo")
async def speak_demo(
    voice: Optional[str] = Query(None, description="Stimme, z. B. de-DE-Klaus:MAI-Voice-2"),
    model: Optional[str] = Query(None, description="Modell, z. B. microsoft/mai-voice-2"),
    text: str = Query(DEMO_SATZ, max_length=MAX_ZEICHEN, description="Eigener Probetext"),
):
    """Hörprobe – im Browser aufrufen, dann spielt sie direkt ab."""
    audio = llm_service.speak(text, voice=voice, model=model)
    return _als_mp3(audio, f"Hörprobe {model or 'Standard'} / {voice or 'Standard'}")
