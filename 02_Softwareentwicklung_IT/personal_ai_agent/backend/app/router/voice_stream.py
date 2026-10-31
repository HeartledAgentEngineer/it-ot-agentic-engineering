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

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field

from app.services.voice_session import (
    VoiceSessionState,
    voice_session_manager,
)
from app.services.sprachbefehl_service import analysiere_sprachbefehl

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


class BefehlAnalyseRequest(BaseModel):
    text: str = Field(..., description="Gesprochener oder getippter Freitext zur Aktions-Erkennung")


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


@router.post("/befehl")
async def sprachbefehl_analysieren(req: BefehlAnalyseRequest) -> Dict[str, Any]:
    """Analysiert Freitext auf App-Aktionen (Navigation, Blaettern, Notizen, Bildgeschichten)."""
    return analysiere_sprachbefehl(req.text)


@router.websocket("/stream/{session_id}")
async def voice_stream_websocket(websocket: WebSocket, session_id: str):
    """Bidirektionaler WebSocket-Stream fuer Audio und Echtzeit-Ereignisse."""
    await websocket.accept()
    sess = voice_session_manager.get_session(session_id)
    if not sess:
        sess = voice_session_manager.create_session(
            session_id=session_id,
            mode="voice_chat",
        )

    try:
        while True:
            message = await websocket.receive()
            if "bytes" in message and message["bytes"]:
                audio_chunk = message["bytes"]
                res = sess.handle_audio_chunk(audio_chunk)
                if sess.state == VoiceSessionState.LISTENING and sess.barge_in_count > 0:
                    await websocket.send_json({
                        "type": "interrupted",
                        "session_id": session_id,
                        "state": sess.state.value,
                    })
                else:
                    await websocket.send_json({
                        "type": "chunk_ack",
                        "total_packets": res["total_packets"],
                        "bytes_received": res["bytes_received"],
                        "state": sess.state.value,
                    })
            elif "text" in message and message["text"]:
                import json
                try:
                    data = json.loads(message["text"])
                except Exception:
                    data = {"type": "raw", "text": message["text"]}

                typ = data.get("type")
                if typ == "interrupt":
                    sess.interrupt()
                    await websocket.send_json({
                        "type": "interrupted",
                        "session_id": session_id,
                        "new_state": sess.state.value,
                        "barge_in_count": sess.barge_in_count,
                    })
                elif typ == "befehl":
                    text = data.get("text", "")
                    ergebnis = analysiere_sprachbefehl(text)
                    await websocket.send_json({
                        "type": "befehl_ergebnis",
                        "data": ergebnis,
                    })
                elif typ == "ping":
                    await websocket.send_json({"type": "pong"})
                elif typ in ("hangup", "end"):
                    sess.transition(VoiceSessionState.HANGUP)
                    await websocket.send_json({
                        "type": "ended",
                        "session_id": session_id,
                    })
                    break
    except WebSocketDisconnect:
        logger.info("Voice-WebSocket getrennt: %s", session_id)
    except Exception as e:
        logger.exception("Fehler im Voice-WebSocket %s: %s", session_id, e)
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
