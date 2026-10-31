# Architektur-Spezifikation: Bidirektionaler Voice Mode & Telefon-Agent (Stufe D)

**Status:** Entwurf & Architektur-Fundament  
**Datum:** 31.10.2026  
**Ziel:** Echtzeit-Sprachassistent mit bidirektionalem Streaming, Voice Activity Detection (VAD), sofortiger Unterbrechbarkeit (Barge-In) und Telefon-Gateway.

---

## 1. Leitbild & Motivation

Sebastian formulierte das Ziel für Stufe D:
> *„Wir bauen quasi unser eigenes Gemini nach, was auch überall in Apps, auf dem Sperrbildschirm, überall kann. Wenn ich ‚OK Agent‘ sage, nimmt er mein Mikrofon auf … und macht dann das, was er gerade soll.“*
> *„... bald wieder live spracherkennt soll auch schon funktionieren dass der bidirektionale voice Mode sprachassistent telefonanerkennung funktioniert das war erstmal vorbereitet werden“*

Bisherige Sprachstrecke (Stufe D3):
- Halbduplex: Mikrofon-Aufnahme per AudioWorklet → Stopp durch Klick/Ruhe → POST `/api/sprache/transkript` → Text ins Feld → Chat-Antwort → Optional Vorlesen (`/api/speak`).
- Latenz: 2–4 Sekunden bis zum ersten Ton.
- Nicht unterbrechbar: Spricht das System einmal, muss gewartet werden, bis der Satz zu Ende gesprochen ist.

Neuer bidirektionaler Voice Mode (Stufe D4 / D5):
- **Echtzeit-Vollduplex:** Kontinuierliches Audio-Streaming (PCM 16 kHz Mono / Opus via WebSocket oder WebRTC).
- **Sub-Sekunden-Latenz:** Streaming-STT (Transkript-Fragmente treffen während des Sprechens ein), spekulative LLM-Token-Erzeugung und Streaming-TTS.
- **Barge-In (Sofortige Unterbrechung):** Sobald der Nutzer spricht, stoppt die Audiowiedergabe sofort (< 150 ms), der TTS-Puffer wird verworfen und das LLM wird informiert.
- **Telefon-Gateway (Inbound & Outbound):** Annahme und Steuerung von Telefongesprächen (SIP / WebRTC / Twilio / Android In-Call Service) mit strukturierter Zustandskontrolle.

---

## 2. Systemarchitektur & Datenfluss

```
[Mikrofon / Telefonie]
        │ Audio-Chunks (PCM 16kHz / 20ms Frames)
        ▼
┌────────────────────────────────────────────────────────┐
│  Client-seitiger AudioWorklet / WebRTC Audio Track     │
│  - Pegel-Überwachung & lokale Vor-VAD                  │
│  - Sofortiger Abbruch bei Nutzersprache (Local Mute)   │
└────────────────────────────────────────────────────────┘
        │ WebSocket / WebRTC DataChannel
        ▼
┌────────────────────────────────────────────────────────┐
│  VoiceSessionManager (Backend)                         │
│  Zustandsautomat: IDLE ⇆ LISTENING ⇆ THINKING ⇆ SPEAKING│
│  - VAD (Voice Activity Detection): Silero / Energy     │
│  - Barge-In Event Dispatcher                           │
└────────────────────────────────────────────────────────┘
   │                      │                     │
   ▼ STT                  ▼ Orchestrierung      ▼ TTS
┌──────────────┐   ┌──────────────┐     ┌──────────────┐
│ Streaming STT│   │ PII-Shield & │     │ Edge-TTS /   │
│ Whisper-Chunk│──▶│ LLM-Streaming│────▶│ Cloud-Audio  │
│ mai-trans-2  │   │ OpenRouter   │     │ (Klaus)      │
└──────────────┘   └──────────────┘     └──────────────┘
```

---

## 3. Zustandsautomat der Voice- und Telefon-Session

Jede Session durchläuft definierte Zustände:

| Zustand | Bedeutung | Aktionen / Ereignisse |
|---|---|---|
| `IDLE` | Sitzung initialisiert, Ruhezustand | Wartet auf Wake-Word, Anruf oder Klick |
| `RINGING` | Telefonat klingelt | Eingehender Anruf: Anruferprüfung, Freizeichen |
| `CONNECTED` | Verbindung aufgebaut | Begrüßung / Audio-Stream initialisiert |
| `LISTENING` | Nutzer spricht | Audio-Buffer sammelt Chunks, VAD aktiv |
| `THINKING` | Pause erkannt, LLM generiert | Token-Streaming startet, STT abgeschlossen |
| `SPEAKING` | Agent liest vor / spricht | Audio-Chunks fließen zum Client |
| `INTERRUPTED` | Barge-In: Nutzer fiel ins Wort | Audio stoppt SOFORT, LLM bricht Generation ab |
| `HANGUP` | Beendet | Session-Bereinigung, Statistik-Persistenz |

---

## 4. Barge-In & Latenz-Optimierung

### 4.1. Latenz-Budget
- VAD-Schwellenwert (Sprechbeginn-Erkennung): **80–120 ms**
- Audio-Unterbrechung (Client-Stop): **< 50 ms**
- STT-Endepunkt-Erkennung (Nutzer fertig): **400–600 ms**
- Erstes LLM-Token: **200–350 ms**
- Erster TTS-Audioblock: **150–250 ms**
- **Gesamte Time-to-First-Audio (TTFA):** **~ 800–1200 ms**

### 4.2. Unterbrechungs-Protokoll (Barge-In)
1. Nutzer beginnt während `SPEAKING` zu sprechen.
2. VAD schlägt an (`speech_prob > 0.6` über 3 aufeinanderfolgende 20ms-Frames).
3. Client sendet sofort:
   ```json
   { "type": "interrupt", "timestamp": 1730345000.123, "played_bytes": 14200 }
   ```
4. Backend bricht die laufende LLM-Generierung und den TTS-Worker per `asyncio.Event` oder Task-Cancellation ab.
5. Der Client stoppt den Audio-Wiedergabepuffer augenblicklich (`audio.pause()`, Puffer leeren).
6. Der neue Nutzersatz wird nahtlos als neue Eingabe verarbeitet.

---

## 5. Telefon-Agent (Telephony Gateway)

### 5.1. Schnittstellen
- **Inbound Webhook (`/api/voice/telephony/webhook`):**
  - Kompatibel mit Twilio Voice, SIP-Gateways (Asterisk/FreePBX) und lokalen Android In-Call Services.
  - Payloads: `call.start`, `call.speech`, `call.dtmf`, `call.end`.
- **Anrufer-Identifikation & Sicherheit:**
  - Anrufernummer wird gegen `bekannte_namen_streng()` und Telefonbuch abgeglichen.
  - Fremde Anrufer erhalten höfliche Standard-Auskunft (z.B. „Sebastian ist gerade unterwegs, ich nehme eine Nachricht auf“).
  - PII-Shield maskiert Telefonnummern deterministisch (`[PHONE_01]`).
  - **Notruf-Sperre:** Anrufe an Notrufnummern (110, 112, 911) werden systemseitig blockiert und auf das reguläre Android-Telefonie-Subsystem verwiesen.

---

## 6. Endpunkte & WebSocket-Spezifikation

- `POST /api/voice/session/start`:
  Initialisiert eine Session (`mode`: `voice_chat` oder `telephony`, `caller_id`).
- `GET /api/voice/session/{session_id}`:
  Liefert Zustand, VAD-Einstellungen und Latenz-Statistiken.
- `POST /api/voice/session/{session_id}/interrupt`:
  Löst manuellen oder VAD-gesteuerten Barge-In aus.
- `POST /api/voice/telephony/webhook`:
  Verarbeitet Telefondienste-Ereignisse.
- `WebSocket /api/voice/stream/{session_id}`:
  Bidirektionaler Binär- (PCM 16 Bit / 16 kHz) und JSON-Nachrichten-Kanal.
