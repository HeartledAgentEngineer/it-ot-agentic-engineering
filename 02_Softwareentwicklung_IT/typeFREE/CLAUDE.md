# typeFREE — Projekt-Direktiven für Claude

## Was ist das?

Systemweite Voice-to-Text-App für Windows:
- Hotkey halten (Standard `Alt + Ä`, auch per `AltGr + Ä` auslösbar; über das Tray-Untermenü „Hotkey wählen" umstellbar) → Mikrofon wird geöffnet und nimmt auf
- Loslassen → OpenAI Whisper transkribiert → OpenRouter/Gemini glättet → Text wird per Zwischenablage (Strg+V) eingefügt
- Funktioniert systemweit: Terminal, Browser, jedes Textfeld

Architektur, Entscheidungen und Setup: siehe [README.md](README.md).

## Tech-Fakten (gegen `windows/typefree.py` verifiziert)

| Komponente | Technologie |
|------------|-------------|
| Transkription | OpenAI Whisper API `whisper-1`, `language="de"`, plus `prompt=WHISPER_VOKABULAR` (Fachwörter vorgeben → weniger Verhörer an der Quelle). Fallback auf OpenRouter `openai/whisper-large-v3` |
| Text-Glättung | OpenRouter `google/gemini-2.0-flash-001`: Füllwörter raus, Verhaspler geglättet, **Verhörer aus dem Zusammenhang korrigiert**, **Umgangssprache unangetastet**. `max_tokens=4000` (1000 hätte ein 10-Minuten-Diktat abgeschnitten). Bei Fehler **oder unplausibel kurzem Ergebnis** Rückfall auf den Rohtext |
| Hotkey | Python-`keyboard`-Library (systemweit). Modifier über **Scancode**, nicht über den Namen — deutsches Windows meldet `STRG`/`UMSCHALT` |
| Audio | `sounddevice` + `soundfile` + `numpy` (WAV direkt im RAM); Mikrofon wird **nur während der Aufnahme** geöffnet |
| Text einfügen | `pyperclip` + `pyautogui` (Strg+V — unterstützt Umlaute) |
| Status | `pystray`-Tray-Icon, fünf Farben: grau/grün/orange/blau/**rot = Fehler**; kein Overlay, kein tkinter |
| Fehlermeldung | Windows-Sprechblase über `tray_icon.notify` + rotes Icon, das rot bleibt bis zur nächsten erfolgreichen Aufnahme |
| Logdatei | `typefree.log` neben der EXE (`RotatingFileHandler`, 3 × 512 KB) plus `sys.excepthook` und `threading.excepthook` |
| API-Keys | `OPENAI_API_KEY` + `OPENROUTER_API_KEY` aus einer `.env` neben der EXE, gelesen von `load_env_file` (eigener Leser, **kein** python-dotenv); echte Umgebungsvariablen haben Vorrang |
| Konfiguration | `windows/config.json` (gewählter Hotkey) |
| Kostenrechnung | `whisper_kosten` + `verbrauch_buchen` + `verbrauch_text` (reine Funktionen), Stand in `verbrauch.json` neben der EXE, Anzeige im Tray-Menü. Nur Whisper ($0,006/Min sekundengenau) — Glättung läuft über OpenRouter |
| Tests | `windows/tests/` — 73 Prüfungen mit pytest in 11 Dateien, alle gegen reine Funktionen |

## Versionierte Struktur

```
typeFREE/
├── CLAUDE.md
├── README.md
├── typeFREE.spec              ← PyInstaller-Build aus dem Projekt-Root
└── windows/
    ├── typefree.py            ← Hauptscript
    ├── requirements.txt
    ├── requirements-dev.txt   ← pytest, nur für die Tests
    ├── config.json
    └── tests/                 ← 73 Prüfungen in 11 Dateien
```

Bewusst nicht versioniert: `build/`, `dist/` (EXE), `.env` sowie der Android-PoC
(Expo/React Native Floating Widget — existiert nur lokal).

## Wichtige technische Erkenntnisse

- **`suppress=True` im `keyboard.hook()` NIEMALS verwenden** — sperrt die gesamte Tastatur
- **AltGr = Ctrl+Alt** intern → kann fremde Shortcuts triggern
- **Modifier-Tracking:** `_mods_down`-Set statt `keyboard.is_pressed()` — zuverlässiger
- **Key-Repeat:** KEY_DOWN-Events während laufender Aufnahme ignorieren
- **Loslassen beendet immer:** KEY_UP der Haupttaste stoppt die Aufnahme, auch wenn ein Modifier vorher losgelassen wurde — sonst gehen Diktate verloren
- **Admin-Rechte** nötig für den Keyboard-Hook
- **Logdatei ist Pflicht:** Bei `console=False` in der Spec hinterlässt ein Absturz sonst keine Spur. `StreamHandler` nur anlegen, wenn `sys.stdout` existiert — in der EXE ist es `None`
- **Startbefehle gehören in `main()`:** Seiteneffekte beim Import (Threads, Tray, Config) machen die Datei untestbar
- **Totes Mikrofon erkennt man an exakter digitaler Null**, nicht an leiser Lautstärke — ein echtes Gerät liefert immer Grundrauschen
- **Dateien nie ohne `encoding=` öffnen** — sonst Encoding-Fehler auf nicht-englischen Systemen
- **Strukturierte Logging-Parameter statt f-Strings** — `log.warning('msg %s', var)` statt `log.warning(f'msg {var}')`

## Erledigt (Stand 01.08.2026)

### Durchgang 1 — „Stabilität und Mikrofon" ✅
- `main()`-Umbau: Import sicher, Tray im Hauptthread, Seiteneffekte in `main()`
- Hotkey-Logik: Loslassen beendet IMMER, Modifier-Tracking über Scancodes
- Mikrofon-Wächter: totes Gerät erkennen, Zeitgrenze 10 Min
- `.env`-Leser (eigener, kein python-dotenv)
- Logdatei + Fehler-Abfänger + rotes Icon bei Fehler
- tkinter entfernt, Hotkey-Auswahl im Tray-Menü
- Registry-Autostart entfernt
- Mikrofon nur während der Aufnahme geöffnet
- **Einzelinstanz-Sperre** ✅ Benannter Windows-Mutex `Local\typeFREE_einzelinstanz`

### Durchgang 2 — begonnen
- **Kosten anzeigen** ✅ Whisper-Kosten im Tray-Menü
- **Prompt verbessert** ✅ Füllwörter-Filter (01.08.2026): alle Schreibweisen, neue Füllwörter, Fachbegriff-Ausnahme
- **Tests gefixt** ✅ 73/73 Prüfungen grün (Referenz `client` → `openrouter_client`)

## Offene Arbeit

### ⚠️ Critic-Gegenprobe für Slice A (Prompt-Änderungen)
Nach Phase 7 einen `/critic`-Lauf auf die geänderten Stellen:
```bash
cd "C:\Users\sebas\Desktop\workspace agentic engineering"
node .claude/skills/critic/pruefe.mjs "02_Softwareentwicklung_IT\typeFREE\windows\typefree.py"
```

### Durchgang 2 — „Autostart, Umzug und Feinschliff"

- **Unsichtbarer Start** `einrichten.cmd` — typeFREE mit `pythonw` starten (kein Terminal-Fenster)
- **Windows-Aufgabenplanung** — Autostart bei Anmeldung + Aufwachen, Admin-Rechte, regelmäßige Prüfung
- **Fehlstart-Erkennung** — nach 3 Fehlstarts in Folge aufgeben und einmalig melden
- **Guthaben-Prüfung** — leeres Guthaben an fehlgeschlagener API-Anfrage erkennen → rotes Icon, weiterlaufen
- **README-Abschnitt** „Warum nicht Win+H"

### Textqualität — offene Punkte

Die Glättung läuft jetzt über OpenRouter `google/gemini-2.0-flash-001`:
- Füllwörter werden hoffentlich besser erkannt (Prompt-Verschärfung vom 01.08.)
- „glaube → denke" und „gucken → wissen" müssen nochmal gemessen werden
- Englische Fachbegriffe in deutschen Sätzen werden nicht geschont

### Weitere Ideen

- **Umschalt-Modus** („einmal drücken zum Starten/Beenden") mit Auswahl im Tray-Menü
- **Lokale Transkription** mit `faster-whisper`
- **EU-Anbieter** prüfen (deutsches Whisper-Hosting, Azure OpenAI Westeuropa)
- **Datenschutz auf dem Arbeitgeber-PC** klären
- **`AltGr + Ä` als eigener Eintrag**
- **Android-APK** via EAS Build
- **Sprachwahl im Tray-Menü** (Deutsch / Englisch / automatisch)

## Arbeitsweise mit Claude

- Sprache: **Deutsch**
- Erklärungen: immer WARUM, nicht nur WAS
- Jeden Schritt erst erklären, dann auf Bestätigung warten
- Commits: nur wenn explizit gewünscht