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
├── Erinnerungsspeicher (JSON-Datei auf dem Gerät: chroma_data/memory_store.json)
├── OpenRouter → DeepSeek V4 Flash
└── Frontend (im Browser-Tab)
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
   live** als Chat-Blasen in einem durchgehenden `/api/chat/stream` (ohne erst
   umzuswitchen auf 3s-Polling); am Ende das Ergebnis.
3. **Track B – Auftragsbuch**: Nur wenn weder PC noch lokaler Hermes verfügbar ist,
   liegt der Auftrag dort zur späteren Abholung bereit.

Doku: `docs/hermes-pc-routing.md` (Track A), `docs/hermes-local-routing.md` (Track C).

## 📦 Projektstruktur

```
personal_ai_agent/
├── backend/           # FastAPI + lokaler Erinnerungsspeicher + OpenRouter
│   ├── app/
│   │   ├── main.py           # Einstiegspunkt
│   │   ├── config.py         # Konfiguration (.env)
│   │   ├── models.py         # Pydantic-Modelle
│   │   ├── router/           # API-Endpunkte
│   │   │   ├── chat.py       #   Chat-API + Hermes-Weiche (Track A/C/B)
│   │   │   ├── archiv.py     #   Archiv: /status, /suche (memory.db, Mistral)
│   │   │   ├── archiv_wissen.py # Wissensspeicher: Zeitachse + Original nachlesen
│   │   │   ├── auftraege.py  #   Auftragsbuch (Programmieraufträge)
│   │   │   ├── memory.py     #   Memory-API
│   │   │   ├── upload.py / transcribe.py / speak.py / llm_models.py ...
│   │   ├── services/         # Geschäftslogik
│   │   │   ├── llm_service.py       #   OpenRouter/DeepSeek
│   │   │   ├── memory_service.py    #   Erinnerungen: Auswahl, Wiederholungs-Prüfung, Einbetten
│   │   │   ├── archiv_service.py    #   Suche in alten Chat-Archiven (memory.db)
│   │   │   ├── archiv_suche.py      #   Wissensspeicher-Index: Hybridsuche + Original
│   │   │   ├── auftrag_service.py   #   Auftragsbuch-Verwaltung
│   │   │   ├── auftrags_erkennung.py#   Heuristik: ist das ein Auftrag?
│   │   │   ├── hermes_gateway.py    #   PC-Hermes (Track A)
│   │   │   └── hermes_local.py      #   Termux-Hermes live (Track C)
│   │   └── db/
│   │       └── chroma_client.py
│   ├── requirements.txt
│   ├── .env.example
│   └── system_prompt.md      # Persönlichkeit des Agenten
├── frontend/          # Chat-UI (im Browser-Tab)
├── docs/              # Doku (u. a. hermes-pc-routing.md, hermes-local-routing.md)
├── start-termux.sh    # Android-Widget-Start (pull + Server)
└── README.md
```

## 🌟 Features

- ✅ **Text-Chat** mit DeepSeek V4 Flash (via OpenRouter)
- ✅ **Persönliches Gedächtnis** – Agent merkt sich Fakten (lokaler JSON-Speicher auf dem
  Gerät, sichtbar und einzeln löschbar im Chat über den Text „N Erinnerungen" unten rechts;
  Konzept und offene Punkte: `docs/konzept-gedaechtnis.md`)
- ✅ **Wissensspeicher (Chat-Archiv)** – 1.109 Gespräche / 40.627 Nachrichten aus ChatGPT,
  Claude, Gemini, Google-Kalender und -Notizen als durchsuchbarer Index (Hybridsuche:
  Volltext + Bedeutung). Der Agent **weiß** das auch ohne Suchtreffer (Prompt-Baustein)
  und liest Treffer über einen Zeiger im Original nach; bei Unsicherheit fragt er nach,
  statt zu behaupten. Nur lesend, Inhalte bleiben auf dem Gerät
  (`docs/konzept-wissensspeicher.md`)
- ✅ **TTS** – Antworten werden vorgelesen (Browser SpeechSynthesis)
- ✅ **Chat im Browser-Tab** – erreichbar über die lokale URL (keine App/keine Installation nötig)
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
| `GET` | `/api/models` | Modellauswahl: nutzbare Modelle (Preis, Kontext, Cache-Preis, Beschreibung – für gängige Modelle deutsch, sonst englisch, Wissensstand, max. Ausgabe, EU, Datenschutz) |
| `GET` | `/api/models/{id}/details` | Anbieter eines Modells samt Datenschutz-Profil |
| `GET` | `/api/memory` | Alle Erinnerungen abrufen (die Oberfläche zeigt sie im Gedächtnis-Blatt) |
| `POST` | `/api/memory` | Manuelle Erinnerung erstellen |
| `GET` | `/api/memory/count` | Anzahl Erinnerungen |
| `DELETE` | `/api/memory/{id}` | **Einzelne** Erinnerung löschen (im Chat über „Entfernen" am Eintrag). `404`, wenn es sie nicht gab |
| `POST` | `/api/memory/wiederholungen?ausfuehren=false` | Mehrfach gespeicherte Fakten aufräumen — standardmäßig Trockenlauf (zeigt nur, was wegfiele) |
| `POST` | `/api/memory/vektoren` | Einträge ohne Vektor nachträglich einbetten (braucht `MISTRAL_API_KEY`) |
| `DELETE` | `/api/memory/clear` | **Alle** Erinnerungen löschen (nur für Tests; die Oberfläche bietet das bewusst nicht an) |
| `GET` | `/api/conversations` | Aktive Konversationen |
| `GET` | `/api/conversations/{id}` | Nachrichten eines Gesprächs – jede Nachricht trägt ein `zeit`-Feld (ISO der Sende-/Empfangszeit). Assistant-Nachrichten, bei denen über die Dateisuche ein Bild gezeigt wurde, tragen zusätzlich `bild_pfad`: nur der Pfad (nie die Datei selbst), damit das Frontend das Bild nach einem Reload frisch nachladen kann (sonst wäre die Bild-Vorschau flüchtig verschwunden). |
| `DELETE` | `/api/chat/letzte-runde` | **Seit 2026-08-31 gesperrt** (Verlauf ist STRENG append-only, Sebastian-Regel): liefert immer `entfernt: false` und entfernt nichts. Der frühere Bearbeiten-Flow entfernte die letzte Runde; jetzt bleibt die alte Runde stehen und neue Formulierung/Antwort werden angehängt. Ohne `conversation_id` gilt `conv_main`. |
| `GET` | `/api/gesichter` | Alle gelernten Personen des Gesichter-Katalogs (Name, Rolle, Beschreibung, Referenzbild-Pfad) |
| `POST` | `/api/gesichter` | Person anlegen oder (nach Name) aktualisieren — fürs „Gesichter merken“ (reaktiv im Chat: „das bin ich“, „das ist Julian, mein Zwillingsbruder“, auch mehrere Personen auf einem Bild) oder gepflegt. `referenz_bild_pfad` speichert NUR den Pfad, nie die Bilddatei; zusätzlich wird eine eingebettete Miniatur erzeugt (pCloud-sicher). Extrahieren von Personennamen/Rollen ist LLM-gestützt (agentisch), mit deterministischem Fallback |
| `DELETE` | `/api/gesichter/{name}` | Gelernte Person nach Name aus dem Katalog entfernen |
| `GET` | `/api/gesichter/kontext` | Der Kontext-Block für den Prompt (Tests/Debug): wird beim Betrachten eines Bildes in die Chat-Nachricht eingefügt, damit der Vision-LLM bekannte Personen benennt |
| `POST` | `/api/gesichter/quiz/start` | Nächste Quiz-Frage: wählt ein noch nicht durchgespieltes Lieblingsbild, liefert `bild_pfad` + `data_url` + alle gelernten Personen als `optionen` (nach Wahrscheinlichkeit sortiert) |
| `POST` | `/api/gesichter/quiz/analysiere` | Führt die (langsame) Gesichts-Analyse für ein schon angezeigtes Bild nach: erkennt Gesichter (inkl. Vermutung) |
| `POST` | `/api/gesichter/quiz/antwort` | Speichert die Quiz-Antwort. `ueberspringen:true` markiert das Bild nur als gesehen. `manuell_bbox:true` (seit 2026-09-11) bettet den SELBST gezeichneten `bbox`-Ausschnitt direkt als Personen-Referenz ein (`op:embed_crop`) — so lässt sich auch eine Person anlernen, die YuNet nicht (richtig) erkannt hat. Ohne `manuell_bbox` wird unter den YuNet-erkannten Gesichtern gewählt |
| `GET` | `/api/gesichter/referenzen` | Alle gelernten Referenzen je Person (ref_id, Jahr, Miniatur) für das Referenz-Management |
| `GET` | `/api/archiv/status` | Alter Archiv-Zugriff (`memory.db`): eingebunden? Was steckt drin, welcher Suchweg trägt? |
| `GET` | `/api/archiv/suche?q=…&modus=hybrid\|volltext\|semantisch` | Suche im alten Archiv (`memory.db`) |
| `GET` | `/api/archiv/wissen/statistik` | Wissensspeicher (neuer Index): Gespräche/Nachrichten/Chunks/Vektoren je Quelle, Zeitraum, Themen-Häufigkeit |
| `GET` | `/api/archiv/wissen/chronik?richtung=alt\|neu&limit=N` | älteste/neueste Gespräche mit Datum, Quelle, Thema und Zeiger |
| `GET` | `/api/archiv/wissen/frage?q=…&modus=hybrid\|volltext\|vektor` | Hybridsuche, zeitlich sortiert, mit `sicher`/`grund`/`rueckfrage` (bei Unsicherheit **keine** behauptete Antwort) |
| `GET` | `/api/archiv/wissen/original?chat_kennung=…&ordinal=…&kontext=1` | Originaltext einer Fundstelle, unverändert, mit Kontextfenster |
| `GET` | `/api/archiv/wissen/ueberblick` | Der Bewusstseins-Baustein „was mein Agent weiß" (Quellen, Zeitraum, Nutzungsregel) als JSON |

## 📚 Wissensspeicher (Chat-Archiv)

Der Agent soll **wissen, dass er ein Archiv hat** und Fragen zu früheren Gesprächen
zuerst dort suchen — nicht im Web. Drei Teile gehören dazu:

1. **Index** — eine SQLite-Datei (`archiv_index.db`, ~240 MB) mit Nachrichten, Chunks,
   FTS5-Volltextindex und Vektoren. Gebaut mit
   `cd backend && .venv/Scripts/python -m scripts.archiv_index_bauen --mit-vektoren`;
   gelesen wird ausschließlich lesend (`mode=ro`).
2. **Verdrahtung** — `archiv_wissen.router` ist in `app/main.py` eingehängt, und der
   Baustein aus `archiv_suche.prompt_baustein(kurz=True)` steht in **jedem** Prompt
   (`llm_service._build_messages`, auch ohne Suchtreffer).
3. **Einstellung** — `ARCHIV_INDEX_PATH` (siehe `.env.example`): erster vorhandener
   Kandidat aus der Suchreihenfolge gewinnt; ohne Angabe zeigt der Standard auf
   `Chats von GPT, GEMINI, Claude/db/archiv_index.db`.

**Schlüssel:** Die Bedeutungssuche (Vektoren) braucht `OPENROUTER_API_KEY` für die
Frage-Einbettung. Fehlt er, läuft die Suche ehrlich im Volltext weiter und sagt es
(`wege.vektor_status: "kein_schluessel"`, `hinweis`). Fehlt der Schlüssel in beiden
projektüblichen `.env`-Dateien, wird er zusätzlich aus der `.env` der Workspace-Wurzel
gelesen — und zwar **nur dieser eine Variablenname** (`app/config.py`).

**Aufs Handy** (USB, einmalig): `adb push` nach `/sdcard/Download/`, dann in Termux
verschieben, damit die Datei nicht im geteilten Ordner liegt und die App ohne
Speicherrechte liest — Details in `docs/konzept-wissensspeicher.md` §7.

## 🔮 Ausblick (Phase 2)

- **Mikrofon-Integration** (Whisper lokal)
- **Multi-Device-Sync** (Heimnetz + VPN)
- **Azure/Hetzner Migration** (Docker-ready)
- **Biometrie + Passwort** Auth
- **Multi-Agenten** (Spezialisten für Security, Netzwerk etc.)

## 📄 Lizenz

Privat – Sebastian