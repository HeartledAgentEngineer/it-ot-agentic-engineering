# 🤖 Personal AI Agent

Ein **datenschutzkonformer, persönlicher KI-Assistent** – Phone-First, später skalierbar auf Azure/Hetzner.

## 🚀 Quick Start (Lokaler PC)

### 1. Backend starten

```bash
# In backend/ Verzeichnis
cd backend

# Python-Umgebung erstellen
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/Mac

# Abhängigkeiten installieren
pip install -r requirements.txt

# .env konfigurieren
cp .env.example .env
# → OPENROUTER_API_KEY eintragen (https://openrouter.ai/keys)

# Server starten
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

Backend läuft unter: http://localhost:8080  
API-Docs: http://localhost:8080/docs

### 2. Frontend öffnen

Einfach `frontend/index.html` im Browser öffnen (z.B. mit Live Server).

Oder:
```bash
npx serve frontend
```

### 3. Testen

```bash
# Hello-World (minimaler Health-/Smoke-Test)
curl http://localhost:8080/api/hello

# Health-Check
curl http://localhost:8080/api/health

# Chat-Nachricht senden
curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hallo Agent, mein Name ist Sebastian!"}'

# Gespeicherte Erinnerungen abrufen
curl http://localhost:8080/api/memory
```

## 🏗️ Architektur (Phone-First)

```
Handy (Termux)
├── FastAPI Backend (Python) → Port 8080
├── ChromaDB (Vektor-DB, lokal)
├── OpenRouter → DeepSeek V4 Flash
└── PWA Frontend (Browser)
```

**API-Key:** Sicher in `.env` auf dem Gerät (nicht exposed im Web).

## 🤖 Programmieraufträge — automatische Bearbeitung durch Hermes

Erkennt die Auftragserkennung eine Coding-/Programmieraufgabe, durchläuft sie
drei Wege, in dieser Reihenfolge:

1. **Track A – PC-Hermes** (im selben WLAN erreichbar): Der Auftrag geht direkt an
   den PC-Hermes-API-Server.
2. **Track C – lokaler Hermes (Termux)**: Ohne PC startet das Backend die Aufgabe
   **automatisch auf dem Handy** (Hermes-CLI in tmux). Der Agent arbeitet als
   Coding-Agent im Projekt, und seine **Gedanken + Werkzeug-Schritte erscheinen
   live** als Chat-Blasen; am Ende das Ergebnis.
3. **Track B – Auftragsbuch**: Nur wenn weder PC noch lokaler Hermes verfügbar ist,
   liegt der Auftrag dort zur späteren Abholung bereit.

Doku: `docs/hermes-pc-routing.md` (Track A), `docs/hermes-local-routing.md` (Track C).

## 📦 Projektstruktur

```
personal_ai_agent/
├── backend/           # FastAPI + ChromaDB + OpenRouter
│   ├── app/
│   │   ├── main.py           # Einstiegspunkt
│   │   ├── config.py         # Konfiguration (.env)
│   │   ├── models.py         # Pydantic-Modelle
│   │   ├── router/           # API-Endpunkte
│   │   │   ├── chat.py       # Chat-API
│   │   │   ├── memory.py     # Memory-API
│   │   │   └── auth.py       # Auth (vorbereitet)
│   │   ├── services/         # Geschäftslogik
│   │   │   ├── llm_service.py   # OpenRouter
│   │   │   └── memory_service.py# Vektor-DB + Embeddings
│   │   └── db/
│   │       └── chroma_client.py # ChromaDB-Client
│   ├── requirements.txt
│   ├── .env.example
│   └── system_prompt.md      # Persönlichkeit des Agenten
├── frontend/          # PWA (Chat-UI)
│   ├── index.html     # Chat-Oberfläche
│   ├── app.js         # App-Logik + TTS
│   ├── style.css      # Dark-Theme
│   ├── manifest.json  # PWA-Manifest
│   └── sw.js          # Service Worker
├── docs/              # Dokumentation
│   ├── brainstorm.md
│   └── specification.md
├── .gitignore
└── README.md
```

## 🌟 Features

- ✅ **Text-Chat** mit DeepSeek V4 Flash (via OpenRouter)
- ✅ **Persönliches Gedächtnis** – Agent merkt sich Fakten (ChromaDB)
- ✅ **TTS** – Antworten werden vorgelesen (Browser SpeechSynthesis)
- ✅ **PWA** – Installierbar auf dem Handy
- ✅ **IT-Security & Netzwerktechnik** als Spezialgebiet
- ✅ **API-Key sicher lokal** – kein Datenabfluss
- ✅ **Dark Theme** – Augenschonend
- ✅ **Bereit für Migration** – Docker/Cloud-ready

## 🧪 API Endpunkte

| Methode | Pfad | Beschreibung |
|---------|------|-------------|
| `GET` | `/api/health` | Health-Check (Status, LLM, Memory) |
| `GET` | `/health` | Liveness-Check auf Wurzelebene (ohne DB/LLM, z. B. für Docker-Healthcheck) |
| `GET` | `/api/hello` | Hello-World–Smoke-Test (ohne DB-/LLM-Abhängigkeit) |
| `GET` | `/status` | Minimaler Status-Endpoint auf Wurzelebene (ohne DB/LLM) |
| `GET` | `/ping` | Minimaler Ping-Endpoint („Liveness“-Smoke-Test, ohne DB/LLM) |
| `POST` | `/api/chat` | Chat-Nachricht senden |
| `GET` | `/api/memory` | Alle Erinnerungen abrufen |
| `POST` | `/api/memory` | Manuelle Erinnerung erstellen |
| `GET` | `/api/memory/count` | Anzahl Erinnerungen |
| `GET` | `/api/conversations` | Aktive Konversationen |

## 🔮 Ausblick (Phase 2)

- **Mikrofon-Integration** (Whisper lokal)
- **Multi-Device-Sync** (Heimnetz + VPN)
- **Azure/Hetzner Migration** (Docker-ready)
- **Biometrie + Passwort** Auth
- **Multi-Agenten** (Spezialisten für Security, Netzwerk etc.)

## 📄 Lizenz

Privat – Sebastian