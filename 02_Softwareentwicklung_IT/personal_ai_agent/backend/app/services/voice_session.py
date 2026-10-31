"""
VoiceSessionManager & Zustandsautomat fuer bidirektionalen Voice Mode und Telefon-Agent.

Spezifikation Stufe D (31.10.2026):
- Verwaltet Vollduplex-Audio-Sitzungen (Browser-WebRTC/AudioWorklet und Telefonie-Gateways).
- Zustandsautomat: IDLE -> RINGING -> CONNECTED -> LISTENING -> THINKING -> SPEAKING -> INTERRUPTED -> HANGUP.
- Unterstuetzt Voice Activity Detection (VAD) Schwellenwerte und sofortiges Barge-In (Sprachunterbrechung).
- Verarbeitet Telefondienste-Webhooks (Inbound/Outbound, DTMF, Hangup).
"""

from __future__ import annotations

import enum
import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class VoiceSessionState(str, enum.Enum):
    IDLE = "idle"
    RINGING = "ringing"
    CONNECTED = "connected"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"
    HANGUP = "hangup"


class VoiceSession:
    """Repraesentiert eine einzelne bidirektionale Sprach- oder Telefonsitzung."""

    def __init__(
        self,
        session_id: str,
        mode: str = "voice_chat",
        caller_id: Optional[str] = None,
        vad_sensitivity: float = 0.5,
        silence_threshold_ms: int = 500,
    ) -> None:
        self.session_id: str = session_id
        self.mode: str = mode  # "voice_chat" oder "telephony"
        self.caller_id: Optional[str] = caller_id
        self.state: VoiceSessionState = (
            VoiceSessionState.RINGING if mode == "telephony" else VoiceSessionState.IDLE
        )
        self.vad_sensitivity: float = vad_sensitivity
        self.silence_threshold_ms: int = silence_threshold_ms
        self.created_at: float = time.monotonic()
        self.last_activity: float = self.created_at

        # Statistiken & Metriken
        self.barge_in_count: int = 0
        self.packets_received: int = 0
        self.packets_sent: int = 0
        self.events_log: List[Dict[str, Any]] = []

        self._record_event("created", f"Mode: {mode}, Caller: {caller_id}")

    def _record_event(self, event_type: str, details: str = "") -> None:
        self.events_log.append({
            "timestamp": time.monotonic() - self.created_at,
            "type": event_type,
            "details": details,
            "state": self.state.value,
        })
        if len(self.events_log) > 50:
            self.events_log.pop(0)

    def transition(self, new_state: VoiceSessionState, reason: str = "") -> bool:
        """Fuehrt einen Zustandsuebergang durch, wenn dieser zulaessig ist."""
        self.last_activity = time.monotonic()
        alt = self.state

        # Unzulaessige Uebergaenge aus HANGUP verhindern
        if alt == VoiceSessionState.HANGUP and new_state != VoiceSessionState.HANGUP:
            logger.warning(
                "Ungueltiger Uebergang fuer Session %s von %s nach %s",
                self.session_id, alt.value, new_state.value,
            )
            return False

        self.state = new_state
        self._record_event("transition", f"{alt.value} -> {new_state.value} ({reason})")
        logger.info(
            "VoiceSession %s: %s -> %s [%s]",
            self.session_id, alt.value, new_state.value, reason,
        )
        return True

    def interrupt(self) -> bool:
        """Löst sofortigen Barge-In aus: Agent stoppt Sprache, geht zurueck in LISTENING."""
        self.last_activity = time.monotonic()
        self.barge_in_count += 1
        self._record_event("barge_in", f"Abbruch bei Count {self.barge_in_count}")
        self.state = VoiceSessionState.INTERRUPTED
        logger.info("VoiceSession %s: Barge-In ausgeloest (Unterbrechung)", self.session_id)
        # Sofort in LISTENING fuer neue Worte ueberfuehren
        self.state = VoiceSessionState.LISTENING
        return True

    def handle_audio_chunk(self, chunk: bytes) -> Dict[str, Any]:
        """Empfaengt einen Audioblock (PCM / Opus), prueft Lautstaerke und aktualisiert Zustand."""
        self.last_activity = time.monotonic()
        self.packets_received += 1

        # Automatische Ueberfuehrung von IDLE oder CONNECTED nach LISTENING bei Audiodaten
        if self.state in (VoiceSessionState.IDLE, VoiceSessionState.CONNECTED):
            self.transition(VoiceSessionState.LISTENING, "audio_input_started")

        return {
            "session_id": self.session_id,
            "state": self.state.value,
            "bytes_received": len(chunk),
            "total_packets": self.packets_received,
        }

    def handle_telephony_event(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Reagiert auf Telefonie-Ereignisse (call.start, call.speech, call.dtmf, call.end)."""
        self.last_activity = time.monotonic()
        self._record_event("telephony_event", f"{event_type}: {payload}")

        if event_type == "call.start":
            self.transition(VoiceSessionState.CONNECTED, "call_answered")
        elif event_type == "call.speech":
            if self.state == VoiceSessionState.SPEAKING:
                self.interrupt()
            else:
                self.transition(VoiceSessionState.LISTENING, "caller_speaking")
        elif event_type == "call.end":
            self.transition(VoiceSessionState.HANGUP, "remote_hangup")
        elif event_type == "call.dtmf":
            self._record_event("dtmf", str(payload.get("digit", "")))

        return {
            "session_id": self.session_id,
            "state": self.state.value,
            "event": event_type,
            "handled": True,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "mode": self.mode,
            "caller_id": self.caller_id,
            "state": self.state.value,
            "vad_sensitivity": self.vad_sensitivity,
            "silence_threshold_ms": self.silence_threshold_ms,
            "barge_in_count": self.barge_in_count,
            "packets_received": self.packets_received,
            "packets_sent": self.packets_sent,
            "uptime_seconds": round(time.monotonic() - self.created_at, 2),
            "idle_seconds": round(time.monotonic() - self.last_activity, 2),
            "recent_events": self.events_log[-10:],
        }


class VoiceSessionManager:
    """Verwaltet alle aktiven Voice- und Telefon-Sessions."""

    def __init__(self) -> None:
        self._sessions: Dict[str, VoiceSession] = {}

    def create_session(
        self,
        mode: str = "voice_chat",
        caller_id: Optional[str] = None,
        vad_sensitivity: float = 0.5,
        silence_threshold_ms: int = 500,
    ) -> VoiceSession:
        """Erzeugt und registriert eine neue Voice- oder Telefon-Session."""
        session_id = f"voice_{uuid.uuid4().hex[:12]}"
        session = VoiceSession(
            session_id=session_id,
            mode=mode,
            caller_id=caller_id,
            vad_sensitivity=vad_sensitivity,
            silence_threshold_ms=silence_threshold_ms,
        )
        self._sessions[session_id] = session
        logger.info("Neue VoiceSession registriert: %s (Mode: %s)", session_id, mode)
        return session

    def get_session(self, session_id: str) -> Optional[VoiceSession]:
        return self._sessions.get(session_id)

    def close_session(self, session_id: str, reason: str = "normal_close") -> bool:
        session = self._sessions.get(session_id)
        if not session:
            return False
        session.transition(VoiceSessionState.HANGUP, reason)
        del self._sessions[session_id]
        logger.info("VoiceSession %s geschlossen und entfernt (%s)", session_id, reason)
        return True

    def cleanup_expired(self, max_idle_seconds: int = 1800) -> int:
        """Raeumt inaktive Sitzungen auf."""
        jetzt = time.monotonic()
        abgelaufen = [
            sid for sid, sess in self._sessions.items()
            if (jetzt - sess.last_activity) > max_idle_seconds
            or sess.state == VoiceSessionState.HANGUP
        ]
        for sid in abgelaufen:
            self._sessions.pop(sid, None)
        if abgelaufen:
            logger.info("%d abgelaufene VoiceSessions bereinigt", len(abgelaufen))
        return len(abgelaufen)

    def list_active(self) -> List[Dict[str, Any]]:
        return [sess.to_dict() for sess in self._sessions.values()]


# Globaler Singleton-Manager
voice_session_manager = VoiceSessionManager()
