# Änderungsprotokoll 31.10.2026 — Architektur-Fundament: Bidirektionaler Voice Mode & Telefon-Agent (Stufe D)

## Kontext & Problemstellung
1. **Bisherige Halbduplex-Sprachstrecke (D3):**
   Audioaufnahme → Stopp → Transkription → Textfeld → Chat-Antwort → Vorlesen. Bei einer Latenz von 2–4 Sekunden und fehlender Unterbrechbarkeit (Barge-In) entspricht dies noch keinem natürlichen, gesprächigen Sprachassistenten wie Gemini Live oder ChatGPT Advanced Voice.
2. **Telefonie-Vorbereitung:**
   Für eingehende und ausgehende Telefongespräche (SIP / WebRTC / Twilio / Android In-Call Service) fehlten ein zentraler Zustandsautomat, Latenzmessungen, VAD-Konfiguration und Webhook-Empfänger.
3. **Tor-Gate-Unterstützung für untracked Files:**
   Neu angelegte Dateien im Projekt wurden von `git diff` nicht erfasst, wodurch `tor.py` vor dem ersten Staging auf die Gesamttestsuite zurückfiel.

---

## Änderungen

### 1. Architektur-Spezifikation (`docs/spec-voice-agent-stufe-d.md`)
- Vollständiger Blueprint für Vollduplex-Audio (PCM 16 kHz Mono / Opus via WebSocket/WebRTC).
- Latenz-Budget (TTFA ~800–1200 ms), VAD-Schwellenwerte und Unterbrechungs-Protokoll (Barge-In bei `speech_prob > 0.6`).
- Telephony-Spezifikation (Inbound/Outbound, Anruferidentifikation gegen Namensbestand, PII-Maskierung, Notruf-Restriktion).

### 2. Backend-Dienst (`backend/app/services/voice_session.py`)
- **`VoiceSessionState` Enum:** `IDLE`, `RINGING`, `CONNECTED`, `LISTENING`, `THINKING`, `SPEAKING`, `INTERRUPTED`, `HANGUP`.
- **`VoiceSession`:**
  - Kapselt Audio-Puffer, Paketstatistiken, VAD-Sensitivität und Stille-Schwellenwerte.
  - `transition()`: Validiert Zustandswechsel, blockiert Re-Aktivierung nach `HANGUP`.
  - `interrupt()`: Löst sofortigen Barge-In aus, erhöht `barge_in_count` und wechselt unmittelbar zurück in `LISTENING`.
  - `handle_telephony_event()`: Behandelt `call.start`, `call.speech`, `call.dtmf`, `call.end`.
- **`VoiceSessionManager`:**
  - Registriert, verwaltet und bereinigt aktive Sitzungen (`cleanup_expired`).

### 3. Router (`backend/app/router/voice_stream.py`)
- `POST /api/voice/session/start`: Initialisiert neue Sprach- oder Telefonsitzung. Blockiert Notrufnummern (110, 112, 911).
- `GET /api/voice/session/{session_id}`: Liefert Session-Zustand, VAD-Parameter und Metriken.
- `POST /api/voice/session/{session_id}/interrupt`: Löst Barge-In aus.
- `POST /api/voice/session/{session_id}/chunk`: Verarbeitet Audioblöcke.
- `POST /api/voice/telephony/webhook`: Empfängt Telefon-Ereignisse.
- `GET /api/voice/sessions`: Liefert aktive Sitzungen.

### 4. Tor-Gate Optimierung (`tools/gate/tor.py`)
- `geaenderte_git_dateien()` erfasst jetzt auch neu erstellte (`?? `) Projektdateien via `git status --porcelain`.
- Verhindert den teuren Gesamttest-Rückfall, wenn neue Komponenten oder Tests angelegt werden.

---

## Verifikation & Tests
- `backend/tests/test_voice_session.py`: 5 Tests für Lebenszyklus, Zustandsübergänge, Barge-In, Audio-Chunking, Manager-Bereinigung und REST-Integration über `TestClient`.
- `backend/tests/test_tor.py`: Neuer Test `test_finde_relevante_tests_voice_session`.
- Gesamtlauf `test_tor.py` + `test_voice_session.py` (14 Tests) in **5,27 s** erfolgreich (Exit 0).
