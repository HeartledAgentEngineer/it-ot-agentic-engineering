# typeFREE — Projekt-Direktiven für Claude

## Was ist das?

Systemweite Voice-to-Text-App für Windows:
- Hotkey halten (Standard F5, im Tray-Menü umstellbar) → Mikrofon nimmt auf
- Loslassen → OpenAI Whisper transkribiert → Groq glättet → Text wird per Zwischenablage (Strg+V) eingefügt
- Funktioniert systemweit: Terminal, Browser, jedes Textfeld

Architektur, Entscheidungen und Setup: siehe [README.md](README.md).

## Tech-Fakten (gegen `windows/typefree.py` verifiziert)

| Komponente | Technologie |
|------------|-------------|
| Transkription | OpenAI Whisper API `whisper-1` mit `language="de"` |
| Text-Glättung | Groq `llama-3.1-8b-instant` (lockerer Ton, keine Füllwörter); bei Fehler Fallback auf Rohtext |
| Hotkey | Python-`keyboard`-Library (systemweit, braucht Admin-Rechte) |
| Audio | `sounddevice` + `soundfile` + `numpy` (WAV direkt im RAM) |
| Text einfügen | `pyperclip` + `pyautogui` (Strg+V — unterstützt Umlaute) |
| Status | `pystray`-Tray-Icon mit Statusfarben, kein Overlay |
| API-Keys | `OPENAI_API_KEY` + `GROQ_API_KEY` als **Umgebungsvariablen** (`os.environ`, kein python-dotenv) |
| Konfiguration | `windows/config.json` (gewählter Hotkey) |

## Versionierte Struktur

```
typeFREE/
├── CLAUDE.md
├── README.md
├── typeFREE.spec              ← PyInstaller-Build aus dem Projekt-Root
└── windows/
    ├── typefree.py            ← Hauptscript
    ├── requirements.txt
    └── config.json
```

Bewusst nicht versioniert: `build/`, `dist/` (EXE), `.env` sowie der Android-PoC
(Expo/React Native Floating Widget — existiert nur lokal).

## Wichtige technische Erkenntnisse

- **`suppress=True` im `keyboard.hook()` NIEMALS verwenden** — sperrt die gesamte Tastatur
- **AltGr = Ctrl+Alt** intern → kann fremde Shortcuts triggern
- **Modifier-Tracking:** `_mods_down`-Set statt `keyboard.is_pressed()` — zuverlässiger
- **Key-Repeat:** KEY_DOWN-Events während laufender Aufnahme ignorieren
- **Admin-Rechte** nötig für den Keyboard-Hook

## Vorgemerkte Ideen (nicht umgesetzt)

- Groq-Whisper (`whisper-large-v3-turbo`) als schnellere Transkriptions-Alternative
- Android-APK via EAS Build (Widget schwebt über anderen Apps)

## Arbeitsweise mit Claude

- Sprache: **Deutsch**
- Erklärungen: immer WARUM, nicht nur WAS
- Jeden Schritt erst erklären, dann auf Bestätigung warten
- Commits: nur wenn explizit gewünscht
