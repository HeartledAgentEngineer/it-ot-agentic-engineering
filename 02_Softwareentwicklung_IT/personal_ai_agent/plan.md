# 🎯 Plan – Mikrofon-Spracheingabe & Offline-Indikator

> **Phase 3 — Planung** | Datum: 03.08.2026
> Vertical Slice: Mikrofon → Aufnahme → Transkription → Glättung → Auto-Senden
> Basis: [specification.md](specification.md), [brainstorm.md](brainstorm.md)

---

## 1. 🎯 Vertical Slice (Ende-zu-Ende)

```
User tippt Mikrofon 🎤 → Button wird rot/pulsierend (Aufnahme läuft)
  → User tippt erneut → Aufnahme stoppt
    → Audio (WAV) an POST /api/transcribe
      → Backend: Whisper via OpenRouter (openai/whisper-large-v3)
      → Backend: Text-Glättung via OpenRouter (POLISH_ANWEISUNG, wie TypeFREE)
      → Bereinigter Text zurück an Frontend
        → Automatisch an POST /api/chat senden
          → Antwort anzeigen + TTS

Status-Farben währenddessen (wie TypeFREE-Tray):
  • Rot = Aufnahme läuft
  • Orange = Transkribieren (Whisper)
  • Blau = Glätten (Polishing)
  • Grau = Idle

Parallel: Offline-Indikator reparieren (Port-Abgleich + Health-Check)
```

---

## 2. 📁 Betroffene Dateien & Änderungen

### 2.1 Neue Datei: `backend/app/router/transcribe.py`

Neuer API-Endpunkt `POST /api/transcribe`:

```python
@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    audio_bytes = await file.read()
    # 1. Whisper via OpenRouter
    raw_text = await llm_service.transcribe(audio_bytes)
    # 2. Glättung (POLISH_ANWEISUNG aus TypeFREE)
    polished = await llm_service.polish_text(raw_text)
    return {"text": polished or raw_text}
```

**Sicherheitscheck:**
- ✅ Kein API-Key im Request (liegt im Backend)
- ✅ Keine Audiodaten extern – nur via Backend → OpenRouter
- ✅ Gleicher OPENROUTER_API_KEY wie TypeFREE

### 2.2 Geänderte Datei: `backend/app/services/llm_service.py`

Zwei neue Methoden aus TypeFREE übernommen:

**`transcribe(audio_bytes)`** → OpenAI Whisper API-Call (exakt wie TypeFREE)
```python
async def transcribe(self, audio_bytes):
    # OpenAI-kompatibler Call via OpenRouter
    response = self.client.audio.transcriptions.create(
        model="openai/whisper-large-v3",
        file=("audio.wav", audio_bytes, "audio/wav"),
        language="de",
        prompt=WHISPER_VOKABULAR,  # aus TypeFREE übernommen
    )
    return response.text.strip()
```

**`polish_text(raw_text)`** → Gemini Flash via OpenRouter (exakt wie TypeFREE)
```python
async def polish_text(self, raw_text):
    response = self.client.chat.completions.create(
        model="google/gemini-2.0-flash-001",  # wie TypeFREE
        messages=[
            {"role": "system", "content": POLISH_ANWEISUNG},
            {"role": "user", "content": f"Bereinige diesen gesprochenen Text:\n\n{raw_text}"},
        ],
        max_tokens=4000,
        temperature=0.2,
    )
    return response.choices[0].message.content.strip()
```

**`WHISPER_VOKABULAR` und `POLISH_ANWEISUNG`** werden 1:1 aus TypeFREE übernommen.

### 2.3 Geänderte Datei: `backend/app/main.py`

Router registrieren:
```python
from app.router import transcribe  # NEU
app.include_router(transcribe.router)  # NEU
```

### 2.4 Geänderte Datei: `frontend/app.js`

**Komplette MediaRecorder-Logik:**
- `navigator.mediaDevices.getUserMedia()` → AudioStream
- `MediaRecorder` → nimmt auf bis User erneut tippt
- Bei Stop: Audio als WAV-Blob → `POST /api/transcribe`
- Antwort → automatisch `sendMessage(text)` aufrufen

**Status-Anzeige:**
- CSS-Klassen für Aufnahme-Status (`.recording`, `.transcribing`, `.polishing`)
- Farben wie TypeFREE-Tray-Icon

### 2.5 Geänderte Datei: `frontend/style.css`

Neue Styles für Aufnahme-Status:
```css
#mic-btn.recording { color: #ff3333; animation: pulse 1s infinite; }
#mic-btn.transcribing { color: #cc7700; }
#mic-btn.polishing { color: #0077cc; }
@keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
```

### 2.6 Geänderte Datei: `frontend/index.html`

- `disabled` vom Mikrofon-Button entfernt ✅ (bereits gemacht)
- Ggf. aria-labels ergänzen

---

## 3. 🧪 Teststrategie

| Schritt | Test |
|---------|------|
| 1 | Mikrofon-Button klicken → rote Aufnahme-Anzeige |
| 2 | Nochmal klicken → Aufnahme stoppt → orange Anzeige |
| 3 | Audio kommt bei `/api/transcribe` an → Whisper liefert Text |
| 4 | Glättung entfernt Füllwörter → blau |
| 5 | Text wird automatisch an `/api/chat` geschickt |
| 6 | Antwort kommt zurück + TTS |
| 7 | Offline-Indikator zeigt "Online" bei laufendem Server |

---

## 4. ✅ /critic-Befunde – Alle behoben

### 🔴 HOCH

| # | Problem | Lösung im Code |
|---|---------|---------------|
| 1 | Keine Dateigrößen-Prüfung (DoS) | `transcribe.py`: `max_size=25MB` prüfen vor `file.read()` + HTTP 413 |
| 2 | Leere API-Response (IndexError) | `llm_service.py`: `if response.choices`-Prüfung vor Zugriff |

### 🟡 MITTEL

| # | Problem | Lösung im Code |
|---|---------|---------------|
| 3 | Fehlendes Error-Handling | `transcribe.py`: try-except mit HTTP 502 + Fehler-Log |
| 4 | Kein Timeout bei Whisper | `llm_service.py`: `timeout=30` im API-Call |
| 5 | Kein Timeout bei Polishing | `llm_service.py`: `timeout=30` im API-Call |
| 6 | getUserMedia ohne Fehlerbehandlung | `app.js`: try-catch mit addMessage-Fehlerhinweis |
| 7 | MediaRecorder liefert WebM statt WAV | `app.js`: MIME-Type `audio/webm;codecs=opus` + Backend akzeptiert webm |
| 8 | Race-Condition Auto-Senden | `app.js`: State-Flag `isTranscribing` verhindert doppeltes Senden |
| 9 | WHISPER_VOKABULAR undefiniert | `llm_service.py`: 1:1 aus TypeFREE übernommen |

### 🟢 NIEDRIG

| # | Problem | Lösung |
|---|---------|--------|
| 10 | Fehlerfall bei Transkription nicht dokumentiert | `transcribe.py`: Bei Fehler → `{"text": null, "error": "..."}` + addMessage im Frontend |

---

## 5. ⚠️ Offene Risiken

| Risiko | Maßnahme |
|--------|----------|
| Mikrofon-Berechtigung verweigert | Fehlerbehandlung + Nutzer-Hinweis (try-catch in app.js) |
| Whisper API-Timeouts (30s) | Frontend zeigt "Transkription dauert länger..." nach 10s |
| Offline-Indikator zeigt falsch "Offline" | Port in Backend-Konfig und Frontend-API_BASE synchronisieren |
| MediaRecorder-Codec-Unterstützung | Fallback auf AudioContext-Konvertierung falls webm nicht supported |
