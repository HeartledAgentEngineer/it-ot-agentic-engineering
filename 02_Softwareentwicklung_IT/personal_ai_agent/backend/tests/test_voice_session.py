"""
Tests fuer VoiceSessionManager und Voice/Telephony Router (Stufe D).
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.router import voice_stream
from app.services.voice_session import (
    VoiceSession,
    VoiceSessionManager,
    VoiceSessionState,
    voice_session_manager,
)


def test_session_lifecycle_and_transitions():
    mgr = VoiceSessionManager()
    sess = mgr.create_session(mode="voice_chat")

    assert sess.state == VoiceSessionState.IDLE
    assert sess.mode == "voice_chat"
    assert sess.barge_in_count == 0

    # Uebergang zu LISTENING
    assert sess.transition(VoiceSessionState.LISTENING, "speech_detected")
    assert sess.state == VoiceSessionState.LISTENING

    # Uebergang zu THINKING
    assert sess.transition(VoiceSessionState.THINKING, "silence_detected")
    assert sess.state == VoiceSessionState.THINKING

    # Uebergang zu SPEAKING
    assert sess.transition(VoiceSessionState.SPEAKING, "tts_started")
    assert sess.state == VoiceSessionState.SPEAKING

    # Barge-In waehrend SPEAKING
    sess.interrupt()
    assert sess.barge_in_count == 1
    assert sess.state == VoiceSessionState.LISTENING

    # Beenden
    assert sess.transition(VoiceSessionState.HANGUP, "user_done")
    assert sess.state == VoiceSessionState.HANGUP

    # Nach HANGUP darf kein neuer Uebergang mehr moeglich sein
    assert not sess.transition(VoiceSessionState.SPEAKING, "invalid_attempt")


def test_telephony_events():
    sess = VoiceSession(session_id="test_tel_01", mode="telephony", caller_id="+491701234567")
    assert sess.state == VoiceSessionState.RINGING

    # Anruf angenommen
    res = sess.handle_telephony_event("call.start", {})
    assert res["state"] == VoiceSessionState.CONNECTED.value

    # Anrufer spricht
    sess.transition(VoiceSessionState.SPEAKING)
    res_speech = sess.handle_telephony_event("call.speech", {})
    assert sess.barge_in_count == 1
    assert res_speech["state"] == VoiceSessionState.LISTENING.value

    # DTMF Eingabe
    sess.handle_telephony_event("call.dtmf", {"digit": "1"})

    # Auflegen
    res_end = sess.handle_telephony_event("call.end", {})
    assert res_end["state"] == VoiceSessionState.HANGUP.value


def test_audio_chunk_handling():
    sess = VoiceSession(session_id="test_audio_01", mode="voice_chat")
    assert sess.packets_received == 0

    chunk = b"\x00" * 320
    res = sess.handle_audio_chunk(chunk)

    assert res["total_packets"] == 1
    assert res["bytes_received"] == 320
    assert sess.state == VoiceSessionState.LISTENING


def test_manager_cleanup():
    mgr = VoiceSessionManager()
    s1 = mgr.create_session()
    s2 = mgr.create_session()

    s1.transition(VoiceSessionState.HANGUP)

    # Cleanup sollte s1 entfernen
    cleaned = mgr.cleanup_expired(max_idle_seconds=0)
    assert cleaned >= 1
    assert mgr.get_session(s1.session_id) is None


def test_api_endpoints_integration():
    app_voice = FastAPI()
    app_voice.include_router(voice_stream.router)
    client = TestClient(app_voice)

    # 1. Session starten
    res_start = client.post("/api/voice/session/start", json={
        "mode": "voice_chat",
        "caller_id": "+49151000000",
        "vad_sensitivity": 0.6,
        "silence_threshold_ms": 400,
    })
    assert res_start.status_code == 201
    daten = res_start.json()
    sid = daten["session_id"]
    assert daten["state"] == "idle"

    # 2. Notrufnummer-Schutz testen
    res_notruf = client.post("/api/voice/session/start", json={
        "mode": "telephony",
        "caller_id": "112",
    })
    assert res_notruf.status_code == 400
    assert "Notrufnummern" in res_notruf.json()["detail"]

    # 3. Session abrufen
    res_get = client.get(f"/api/voice/session/{sid}")
    assert res_get.status_code == 200
    assert res_get.json()["session_id"] == sid

    # 4. Audio Chunk senden
    res_chunk = client.post(f"/api/voice/session/{sid}/chunk", json={
        "bytes_count": 640,
    })
    assert res_chunk.status_code == 200
    assert res_chunk.json()["state"] == "listening"

    # 5. Barge-In Interrupt senden
    res_intr = client.post(f"/api/voice/session/{sid}/interrupt")
    assert res_intr.status_code == 200
    assert res_intr.json()["status"] == "interrupted"
    assert res_intr.json()["barge_in_count"] == 1

    # 6. Telephony Webhook senden
    res_hook = client.post("/api/voice/telephony/webhook", json={
        "session_id": sid,
        "event": "call.end",
        "payload": {},
    })
    assert res_hook.status_code == 200
    assert res_hook.json()["state"] == "hangup"

    # 7. Alle Sessions auflisten
    res_list = client.get("/api/voice/sessions")
    assert res_list.status_code == 200
    assert "sessions" in res_list.json()
