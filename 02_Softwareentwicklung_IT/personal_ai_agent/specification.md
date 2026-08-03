# 📋 Technical Specification – Personal AI Agent (MVP)

> **Phase 1b — grillAnAgent** | Datum: 02.08.2026
> Basis: [brainstorm.md](brainstorm.md)

---

## 1. 🎯 MVP Scope: "Sprach-Chat mit Gedächtnis"

### Was der MVP kann
- Sprach-Eingabe (Mikrofon) → Transkription (Whisper lokal) → LLM (OpenRouter) → Sprach-Ausgabe (TTS lokal)
- Der Agent merkt sich Fakten und Kontext aus vorherigen Gesprächen (Vektor-DB)
- Läuft auf PC + Handy (PWA)
- Keine Audiodaten zu US-Clouds (Whisper + TTS lokal)

### Was der MVP NICHT kann
- ❌ E-Mails lesen/schreiben
- ❌ Cloud-Zugriff (pCloud etc.)
- ❌ Web-Suche / Browser-Funktion
- ❌ Bildanalyse
- ❌ Alexa-Integration
- ❌ Multi-Agenten

---

## 2. 🏗️ Architektur-Übersicht

```
┌─────────────────────────────────────────────────────────────┐
│                      Hetzner VPS (~5,90€/Monat)              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  FastAPI      │    │  Vektor-DB   │    │  Session/     │  │
│  │  (Backend)    │◄──►│  (Chroma)    │    │  Auth-Mgmt    │  │
│  └──────┬───────┘    └──────────────┘    └──────────────┘  │
│         │                                                    │
│  ┌──────▼───────┐                                           │
│  │  OpenRouter  │  (LLM + ggf. Whisper/TTS Cloud-Fallback)   │
│  └──────────────┘                                           │
└─────────────────────────────────────────────────────────────┘
         ▲                                    │
         │ HTTP/WebSocket                     │
         │                                    ▼
┌─────────────────┐              ┌───────────────────────┐
│  PWA (Browser)   │              │  Android (Deep Link)  │
│  - Mikrofon      │              │  "Hey Gemini, öffne  │
│  - Whisper lokal │              │   meinen Agenten"     │
│  - TTS lokal     │              │  → PWA im Browser     │
└─────────────────┘              └───────────────────────┘
```

---

## 3. 🧩 Komponenten im Detail

### 3.1 Backend (FastAPI + Python)

**Endpunkte:**
| Methode | Pfad | Beschreibung |
|---------|------|-------------|
| POST | `/api/chat` | Chat-Nachricht senden (Text) |
| POST | `/api/chat/stream` | Chat mit Streaming-Antwort |
| GET | `/api/conversations` | Konversationsverlauf abrufen |
| POST | `/api/memory` | Fakt im Gedächtnis speichern |
| GET | `/api/memory` | Gespeicherte Fakten abrufen |
| POST | `/api/auth/login` | Authentifizierung (API-Key) |
| WebSocket | `/ws/chat` | Echtzeit-Chat mit Audio-Streaming |

**Abhängigkeiten:**
```
fastapi
uvicorn[standard]
openai (OpenRouter-kompatibel)
chromadb
sentence-transformers (Embeddings lokal)
pydantic
python-jose (JWT für Auth)
httpx
```

### 3.2 Sprachverarbeitung (lokal im Browser/PWA)

- **STT (Speech-to-Text):** Whisper.cpp (via WebAssembly im Browser ODER via Termux auf Android)
  - *Entscheidung:* Für MVP reicht Browser-natives `SpeechRecognition API` als Fallback, später Whisper WASM
- **TTS (Text-to-Speech):** Browser-native `SpeechSynthesis API` für MVP (lokal, keine Kosten)
  - *Alternative:* edge-tts (Python, lokal) via Backend-Endpunkt

### 3.3 LLM-Integration (OpenRouter)

**Entscheidungen:**
| Frage | Entscheidung | Begründung |
|-------|-------------|-----------|
| **Modell** | Claude 3.5 Haiku | Günstig (~0,25€/M Tokens), schnell, gut für Agenten-Kontext |
| **Fallback** | Llama 3.1 70B (kostenlos) | Falls Haiku rate-limited |
| **System-Prompt** | Persönlicher Assistent mit Gedächtnis | Wird pro Session mit Kontext angereichert |

### 3.4 Gedächtnis (Vektor-DB)

**Struktur:**
```
Memories (Collection: "memories")
├── id: str (UUID)
├── content: str (Der Fakt / die Information)
├── embedding: List[float] (384d, all-MiniLM-L6-v2)
├── metadata:
│   ├── category: str ("fact" | "preference" | "context")
│   ├── timestamp: datetime
│   └── conversation_id: str (optional)
└── created_at: datetime
```

- **Embedding-Modell:** `all-MiniLM-L6-v2` (lokal via sentence-transformers)
- **Retrieval:** Top-5 ähnliche Memories pro Chat-Kontext
- **Extraktion:** LLM extrahiert automatisch Fakten aus Unterhaltungen

### 3.5 Authentifizierung

- **MVP:** Einfacher API-Key (uuid) als Header
- **Session:** JWT-Token mit 24h Gültigkeit
- **Erweiterung:** Später OAuth2 / Passkey

### 3.6 PWA (Frontend)

**Technologie:**
- Vanilla HTML/CSS/JS (kein Framework für MVP – schnell, keine Dependencies)
- ODER: Minimal setup mit Svelte (leicht, compiliert zu vanilla JS)

**Features:**
- Mikrofon-Zugriff (MediaRecorder API)
- Audio-Visualisierung (einfach)
- Chat-UI (Nachrichtenverlauf)
- Deep-Link-Unterstützung (`agent.sebastian.domain/open`)
- Service Worker für Offline-Fallback

---

## 4. 📁 Projektstruktur

```
personal_ai_agent/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI-App + Router
│   │   ├── config.py            # Umgebungsvariablen / Settings
│   │   ├── models.py            # Pydantic-Modelle
│   │   ├── router/
│   │   │   ├── __init__.py
│   │   │   ├── chat.py          # Chat-Endpunkte
│   │   │   ├── memory.py        # Memory-Endpunkte
│   │   │   └── auth.py          # Auth-Endpunkte
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── llm_service.py   # OpenRouter-Integration
│   │   │   ├── memory_service.py# Vektor-DB-Logik
│   │   │   └── auth_service.py  # JWT/Auth-Logik
│   │   └── db/
│   │       ├── __init__.py
│   │       └── chroma_client.py # ChromaDB-Client
│   ├── requirements.txt
│   ├── .env.example
│   └── Dockerfile
├── frontend/
│   ├── index.html
│   ├── app.js
│   ├── style.css
│   ├── manifest.json
│   └── sw.js                    # Service Worker
├── docs/
│   ├── brainstorm.md
│   └── specification.md
├── .gitignore
└── README.md
```

---

## 5. 🚀 Implementierungs-Reihenfolge

### Sprint 1: Backend-Grundgerüst
1. FastAPI-App mit Config & Modellen
2. ChromaDB-Integration (Vektor-DB)
3. OpenRouter-LLM-Service
4. Chat-API (einfach, ohne Streaming)
5. Memory-Extraktion & Speicherung

### Sprint 2: Frontend (PWA)
1. HTML/CSS-Grundgerüst (Chat-UI)
2. JavaScript: Mikrofon → Whisper → API
3. TTS-Ausgabe (SpeechSynthesis)
4. PWA-Manifest + Service Worker
5. Deep-Link-Unterstützung

### Sprint 3: Integration & Deployment
1. Docker-Compose für Backend
2. Hetzner VPS Setup
3. Domain + SSL (Let's Encrypt)
4. CI/CD mit GitHub Actions (optional)

---

## 6. 🔮 Offene Fragen & Entscheidungen

| # | Frage | Entscheidung | Status |
|---|-------|-------------|--------|
| 1 | **Modell** | Claude 3.5 Haiku (OpenRouter) | ✅ Festgelegt |
| 2 | **TTS** | Browser SpeechSynthesis API (lokal) | ✅ Festgelegt |
| 3 | **Auth** | API-Key + JWT (MVP) | ✅ Festgelegt |
| 4 | **PWA vs. Native** | PWA (MVP), evtl. später native Android | ✅ Festgelegt |
| 5 | **Gedächtnis** | Fakten-basiert + Conversation Context | ✅ Festgelegt |
| 6 | **Azure-Timing** | Erst bei Scale-Up aktivieren | ✅ Festgelegt |

---

## 7. 📊 Datenfluss (Beispiel-Chat)

```
User (spricht): "Hey Agent, mein Name ist Sebastian"

1. Browser: MediaRecorder → Audio-Blob
2. Browser: Whisper.cpp/WASM → "Hey Agent, mein Name ist Sebastian"
3. Browser: POST /api/chat { text: "Hey Agent, mein Name ist Sebastian" }
4. Backend: GET /api/memory → relevante Fakten (Top-5)
5. Backend: LLM-Call (OpenRouter) mit System-Prompt + Memory-Kontext
6. LLM: "Hallo Sebastian! Schön dich kennenzulernen. Ich merke mir: Sebastian ist dein Name."
7. Backend: POST /api/memory { content: "Der Nutzer heißt Sebastian", category: "fact" }
8. Backend: Response → { text: "Hallo Sebastian! Schön dich kennenzulernen." }
9. Browser: SpeechSynthesis → gesprochene Antwort
```

---

## 8. 🧪 Teststrategie (MVP)

- **Unit-Tests:** Pytest für Backend-Services
- **Integration:** Test-API mit curl/httpie
- **Manuell:** Chat-Verlauf im Browser testen
- **Gedächtnis:** "Weißt du noch, wer ich bin?" nach Neuladen testen