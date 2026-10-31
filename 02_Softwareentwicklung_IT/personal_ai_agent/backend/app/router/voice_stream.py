"""
Router: Endpunkte fuer bidirektionalen Voice Mode und Telefon-Agent (Stufe D).

Spezifikation 31.10.2026:
- POST /api/voice/session/start          Startet eine neue Voice- oder Telefon-Session
- GET  /api/voice/session/{session_id}   Liefert Zustand und Metriken
- POST /api/voice/session/{session_id}/interrupt Löst sofortigen Barge-In aus
- POST /api/voice/session/{session_id}/chunk     Verarbeitet einen Audioblock
- POST /api/voice/telephony/webhook      Verarbeitet Telefon-Ereignisse (Call Start/End/DTMF)
- GET  /api/voice/sessions               Liste aktiver Sitzungen
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.services.voice_session import (
    VoiceSessionState,
    voice_session_manager,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voice", tags=["voice"])


class SessionStartRequest(BaseModel):
    mode: str = Field("voice_chat", description="Modus: 'voice_chat' oder 'telephony'")
    caller_id: Optional[str] = Field(None, description="Anrufer-ID oder Telefonnummer")
    vad_sensitivity: float = Field(0.5, ge=0.0, le=1.0, description="VAD-Empfindlichkeit 0.0 - 1.0")
    silence_threshold_ms: int = Field(500, ge=100, le=2000, description="Stille-Schwellenwert in ms")


class TelephonyWebhookRequest(BaseModel):
    session_id: str = Field(..., description="Zugehoerige Session-ID")
    event: str = Field(..., description="Ereignis: 'call.start', 'call.speech', 'call.dtmf', 'call.end'")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Zusatzdaten zum Ereignis")


class AudioChunkRequest(BaseModel):
    data_b64: Optional[str] = Field(None, description="Base64-kodierte Audiodaten (PCM 16 Bit / 16 kHz)")
    bytes_count: int = Field(0, description="Anzahl Bytes im Chunk (fuer Metriken)")


@router.post("/session/start", status_code=status.HTTP_201_CREATED)
async def start_voice_session(req: SessionStartRequest) -> Dict[str, Any]:
    """Startet eine neue bidirektionale Sprach- oder Telefonsitzung."""
    # Notrufnummern-Schutz
    if req.caller_id in ("110", "112", "911"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Notrufnummern duerfen nicht ueber den Agenten geleitet werden.",
        )

    sess = voice_session_manager.create_session(
        mode=req.mode,
        caller_id=req.caller_id,
        vad_sensitivity=req.vad_sensitivity,
        silence_threshold_ms=req.silence_threshold_ms,
    )
    return sess.to_dict()


@router.get("/session/{session_id}")
async def get_voice_session(session_id: str) -> Dict[str, Any]:
    """Liefert den aktuellen Zustand und Metriken einer Session."""
    sess = voice_session_manager.get_session(session_id)
    if not sess:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"VoiceSession '{session_id}' nicht gefunden.",
        )
    return sess.to_dict()


@router.post("/session/{session_id}/interrupt")
async def interrupt_voice_session(session_id: str) -> Dict[str, Any]:
    """Löst sofortigen Barge-In (Unterbrechung der Sprachausgabe) aus."""
    sess = voice_session_manager.get_session(session_id)
    if not sess:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"VoiceSession '{session_id}' nicht gefunden.",
        )
    sess.interrupt()
    return {
        "status": "interrupted",
        "session_id": session_id,
        "new_state": sess.state.value,
        "barge_in_count": sess.barge_in_count,
    }


@router.post("/session/{session_id}/chunk")
async def process_audio_chunk(session_id: str, req: AudioChunkRequest) -> Dict[str, Any]:
    """Verarbeitet einen Audioblock fuer eine Session."""
    sess = voice_session_manager.get_session(session_id)
    if not sess:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"VoiceSession '{session_id}' nicht gefunden.",
        )
    dummy_bytes = b"\x00" * max(req.bytes_count, 320)
    ergebnis = sess.handle_audio_chunk(dummy_bytes)
    return ergebnis


@router.post("/telephony/webhook")
async def telephony_webhook(req: TelephonyWebhookRequest) -> Dict[str, Any]:
    """Empfaengt Telefondienst-Webhooks und aktualisiert die Session."""
    sess = voice_session_manager.get_session(req.session_id)
    if not sess:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"VoiceSession '{req.session_id}' fuer Telephony-Webhook nicht gefunden.",
        )
    res = sess.handle_telephony_event(req.event, req.payload)
    return res


@router.get("/sessions")
async def list_voice_sessions() -> Dict[str, Any]:
    """Liefert alle aktiven Sprach- und Telefonsitzungen."""
    voice_session_manager.cleanup_expired(max_idle_seconds=1800)
    aktive = voice_session_manager.list_active()
    return {
        "count": len(aktive),
        "sessions": aktive,
    }
