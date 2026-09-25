# 🎯 Roadmap – Personal AI Agent (grillAnAgent)

> **Stand:** 15.09.2026
> **Vorgänger-Plan (Mikrofon-Vertical-Slice vom 03.08.2026):** erledigt → siehe Abschnitt 4 „Erledigt (Historie)"
> **Basis:** [specification.md](specification.md), [brainstorm.md](brainstorm.md)

---

## 1. ✅ Ist-Stand

- **Phone-First Backend** läuft, Umfang ~**12.400 Zeilen** (FastAPI, Termux-tauglich).
- **Testsuite:** **26 Testdateien / 208 Tests**, Stand **208 grün / 0 rot** (nach R1, 15.09.2026).
  - Prüfbefehl: `cd backend && .venv/Scripts/python -m pytest tests/ -q` → `208 passed` (Exit 0), Laufzeit ~23 s
  - Die Tests laufen **offline** (LLM-Gate gemockt) — vorher machten sie echte Netz-Calls (~6 s/Test).
- **Gesichter-Katalog + Quiz** vorhanden (`gesichter_service`) — bekannte Personen inkl. Quiz-Abfrage.
- **Coding-Chat** über eigene Conversation-Id **`conv_code`**.
- **3-Track-Hermes-Weiche:** Track A = PC-Hermes · **Track C = lokaler Hermes (Termux)** · **Track B = Auftragsbuch (intern)**. Track C verfügbar, wenn `hermes` **und** `tmux` im PATH liegen (`hermes_local.py:267`); Ziel-Anzeige (Ziel-Pille) vorhanden.
- **Modellauswahl mit Datenschutz-Kennzeichnung** im Frontend (welches Modell / welche Daten wohin).

---

## 2. 🔧 Offene Punkte (priorisiert)

### ✅ R1 — Track-Weiche repariert · erledigt 15.09.2026
- **Ursache:** `route_auftrag()` (`backend/app/services/chat_routing.py`) hatte **keinen `ziel`-Parameter** → Track A (PC-Hermes) wurde **immer zuerst** versucht. Der Umlenk-Button „An lokalen Hermes" landete dadurch trotzdem am PC (der annahm und nichts ans Handy zurückgab). **`conv_code` ebenso:** Kommentar sagte „IMMER lokale CLI", der Code ging PC-zuerst.
- **Fix:** `route_auftrag(..., ziel="")` — bei `ziel="handy"` wird Track A übersprungen. In der Stream-Weiche (`chat.py`) überspringen `ziel="handy"` **und** `conv_code` den PC-Weg. Der `/chat`-Weg reicht `request.ziel` durch.
- **Verifikation:** `backend/tests/test_route_ziel.py` (5 Tests: handy überspringt PC · ohne ziel PC zuerst · handy ohne lokalen Hermes → Buch · ziel=pc · Kontext bleibt).

### ✅ R1b — 8 rote Tests isoliert · erledigt 15.09.2026
- **Ursache (zwei verschiedene, beide verifiziert):**
  1. `_datei_tool` ruft `llm_service.extrahiere_datei_such_intent()` (LLM-Call) als **Vorgate** — die Tests mockten das nicht → echte Netz-Calls (~6 s/Test) und Fehlschlag.
  2. `test_chat_verlauf.py` **löscht `app.router.chat` aus `sys.modules` und importiert das Modul neu**. Danach traf ein Patch per Modulname ein anderes Objekt als die importierte Funktion → `test_kontext_delegation.py` las im Sammellauf den geteilten (leeren/fremden) Topf.
- **Fix:** LLM-Gate wird über die Globals von `_datei_tool` gemockt; Kontext-Tests patchen die **Globals von `_baue_kontext` selbst** (`mock.patch.dict`). Kein Produktcode geändert.
- **Ergebnis:** 208 grün / 0 rot, Laufzeit ~23 s (vorher ~30 s mit Netzzugriffen).

### R2 — `chat.py` entlasten · Prio: mittel
- `backend/app/router/chat.py` ist auf **1949 Zeilen / 28 Funktionen** angewachsen → schwer lesbar/testbar.
- Ziel: in Services/Module aufteilen (z. B. Routing, Stream, Persistenz trennen).
- *Aufwand:* ~1–2 Tage (Refactor mit Testabsicherung). *Abhängigkeit:* sollte **nach** R1 erfolgen (Routing vorher stabilisieren).

### R3 — `frontend/app.js` aufteilen · Prio: mittel
- `frontend/app.js` umfasst **7082 Zeilen** (Vanilla JS, monolithisch).
- Ziel: in thematische Module (Chat, Voice, Gesichter/Quiz, Einstellungen) zerlegen.
- *Aufwand:* ~2–3 Tage (viel Fläche, Regression-Risiko). *Abhängigkeit:* unabhängig von Backend-R1/R2, aber besser nach R2.

### R4 — Personen-Katalog ↔ Erinnerungen-Brücke · Prio: mittel
- `gesichter_service` hat **keine Verbindung** zu `memory_service` (Erinnerungen) → Personen und ihre Erinnerungen sind getrennt.
- Ziel: Brücke Personen ↔ Erinnerungen (Person als Struktur-Träger für zugehörige Memories).
- *Aufwand:* ~1 Tag. *Abhängigkeit:* braucht saubere `memory_service`-API; mit R2 koordinieren.

### R5 — pCloud-Anbindung · Prio: niedrig (Blauplan)
- Nur Planung, **kein Code**: `docs/plan-pcloud-anbindung.md` (Stand 15.09.2026).
- *Aufwand:* offen — erst nach R1–R4. *Abhängigkeit:* Konzept-Entscheidung (Auth/Scope) ausstehend.

### R6 — `HERMES_LOCAL_*`-Konfig dokumentieren · Prio: niedrig (Doku)
- Felder existieren in `backend/app/config.py` (Z. 167/176/182), fehlten aber in `backend/.env.example`:
  `hermes_local_session`, `hermes_local_kanal` (tmux | `query`), `hermes_local_model`.
- Erledigt: **in `backend/.env.example` ergänzt** (siehe unten). Offen: ggf. README-Verweis.
- *Aufwand:* ~15 min (Doku). *Abhängigkeit:* keine.

---

## 3. 📌 Reihenfolge (Empfehlung)

1. **R1 + R1b** (Track-Weiche + rote Tests) — kleine, isolierte Fixes, sofort machbar.
2. **R2 + R4** (Backend-Entlastung + Personen-Brücke).
3. **R3** (Frontend-Aufteilung).
4. **R5** (pCloud) — erst nach stabilem Backend.

---

## 4. ✅ Erledigt (Historie)

### Mikrofon-Spracheingabe & Offline-Indikator (Vertical Slice, 03.08.2026)

> Phase 3 — Planung | Datum: 03.08.2026
> Vertical Slice: Mikrofon → Aufnahme → Transkription → Glättung → Auto-Senden

**Ende-zu-Ende-Fluss:**
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

**Betroffene Dateien & Änderungen:**

- **Neu `backend/app/router/transcribe.py`** — Endpunkt `POST /api/transcribe`:
  Whisper-Transkription + Glättung, Rückgabe `{"text": polished or raw_text}`.
  Sicherheit: kein API-Key im Request, keine Audiodaten extern außer via Backend → OpenRouter.
- **`backend/app/services/llm_service.py`** — zwei Methoden aus TypeFREE:
  `transcribe(audio_bytes)` (Whisper, `language="de"`, `WHISPER_VOKABULAR`) und
  `polish_text(raw_text)` (Gemini Flash, `POLISH_ANWEISUNG`, max_tokens=4000, temperature=0.2).
- **`backend/app/main.py`** — Router registrieren (`app.include_router(transcribe.router)`).
- **`frontend/app.js`** — MediaRecorder-Logik (`getUserMedia`, Aufnahme bis erneuter Tipp),
  Audio-Blob → `POST /api/transcribe` → automatisch `sendMessage(text)`; Status-Klassen.
- **`frontend/style.css`** — Aufnahme-Status (`.recording` rot/pulsierend, `.transcribing` orange, `.polishing` blau).
- **`frontend/index.html`** — `disabled` vom Mikrofon-Button entfernt, aria-labels.

> **Nachtrag 25.09.2026 (dieser Plan ist Historie, zwei Angaben sind überholt):**
> Der Weg heißt jetzt **`POST /api/sprache/transkript`** (kanonisch, wie in
> `docs/roadmap-personal-agent.md` D3 zugesagt); `/api/transcribe` bleibt bedient —
> dieselbe Funktion, kein zweiter Codepfad. Und aufgenommen wird **nicht** mit
> MediaRecorder: Der liefert nur WebM/Opus, was der Anbieter mit HTTP 400 ablehnt;
> die Aufnahme läuft über einen AudioWorklet und baut die WAV-Datei selbst
> (Befund 7 unten war in der Praxis nicht tragfähig). Neu ist außerdem die
> sichtbare Zustandszeile (`#mic-status`: „Mikrofon offen / hört zu / denkt nach /
> spricht") — Details in `docs/changelog-2026-09-25-sprachaufnahme-frontend.md`.

**Teststrategie:**

| Schritt | Test |
|---------|------|
| 1 | Mikrofon-Button klicken → rote Aufnahme-Anzeige |
| 2 | Nochmal klicken → Aufnahme stoppt → orange Anzeige |
| 3 | Audio kommt bei `/api/transcribe` an → Whisper liefert Text |
| 4 | Glättung entfernt Füllwörter → blau |
| 5 | Text wird automatisch an `/api/chat` geschickt |
| 6 | Antwort kommt zurück + TTS |
| 7 | Offline-Indikator zeigt "Online" bei laufendem Server |

**/critic-Befunde — alle behoben:**

| # | Problem | Lösung im Code |
|---|---------|---------------|
| 1 | Keine Dateigrößen-Prüfung (DoS) | `transcribe.py`: `max_size=25MB` vor `file.read()` + HTTP 413 |
| 2 | Leere API-Response (IndexError) | `llm_service.py`: `if response.choices`-Prüfung |
| 3 | Fehlendes Error-Handling | `transcribe.py`: try-except mit HTTP 502 + Log |
| 4 | Kein Timeout bei Whisper | `llm_service.py`: `timeout=30` |
| 5 | Kein Timeout bei Polishing | `llm_service.py`: `timeout=30` |
| 6 | getUserMedia ohne Fehlerbehandlung | `app.js`: try-catch mit addMessage-Hinweis |
| 7 | MediaRecorder liefert WebM statt WAV | `app.js`: MIME `audio/webm;codecs=opus` + Backend akzeptiert webm |
| 8 | Race-Condition Auto-Senden | `app.js`: State-Flag `isTranscribing` |
| 9 | WHISPER_VOKABULAR undefiniert | `llm_service.py`: 1:1 aus TypeFREE übernommen |
| 10 | Fehlerfall nicht dokumentiert | `transcribe.py`: `{"text": null, "error": "..."}` + addMessage |

**Offene Risiken (Historie):**

| Risiko | Maßnahme |
|--------|----------|
| Mikrofon-Berechtigung verweigert | Fehlerbehandlung + Nutzer-Hinweis (try-catch in app.js) |
| Whisper API-Timeouts (30s) | Frontend zeigt "Transkription dauert länger..." nach 10s |
| Offline-Indikator zeigt falsch "Offline" | Port in Backend-Konfig und Frontend-API_BASE synchronisieren |
| MediaRecorder-Codec-Unterstützung | Fallback auf AudioContext-Konvertierung |
