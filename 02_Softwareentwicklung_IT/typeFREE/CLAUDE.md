# typeFREE — Projekt-Direktiven für Claude

## Was ist das?

Systemweite Voice-to-Text-App für Windows:
- Hotkey halten (Standard `Alt + Ä`, auch per `AltGr + Ä` auslösbar; über das Tray-Untermenü „Hotkey wählen" umstellbar) → Mikrofon wird geöffnet und nimmt auf
- Loslassen → OpenAI Whisper transkribiert → Groq glättet → Text wird per Zwischenablage (Strg+V) eingefügt
- Funktioniert systemweit: Terminal, Browser, jedes Textfeld

Architektur, Entscheidungen und Setup: siehe [README.md](README.md).

## Tech-Fakten (gegen `windows/typefree.py` verifiziert)

| Komponente | Technologie |
|------------|-------------|
| Transkription | OpenAI Whisper API `whisper-1`, `language="de"`, plus `prompt=WHISPER_VOKABULAR` (Fachwörter vorgeben → weniger Verhörer an der Quelle) |
| Text-Glättung | Groq `llama-3.1-8b-instant`: Füllwörter raus, Verhaspler geglättet, **Verhörer aus dem Zusammenhang korrigiert**, **Umgangssprache unangetastet**. `max_tokens=4000` (1000 hätte ein 10-Minuten-Diktat abgeschnitten). Bei Fehler **oder unplausibel kurzem Ergebnis** Rückfall auf den Rohtext |
| Hotkey | Python-`keyboard`-Library (systemweit). Modifier über **Scancode**, nicht über den Namen — deutsches Windows meldet `STRG`/`UMSCHALT` |
| Audio | `sounddevice` + `soundfile` + `numpy` (WAV direkt im RAM); Mikrofon wird **nur während der Aufnahme** geöffnet |
| Text einfügen | `pyperclip` + `pyautogui` (Strg+V — unterstützt Umlaute) |
| Status | `pystray`-Tray-Icon, fünf Farben: grau/grün/orange/blau/**rot = Fehler**; kein Overlay, kein tkinter |
| Fehlermeldung | Windows-Sprechblase über `tray_icon.notify` + rotes Icon, das rot bleibt bis zur nächsten erfolgreichen Aufnahme |
| Logdatei | `typefree.log` neben der EXE (`RotatingFileHandler`, 3 × 512 KB) plus `sys.excepthook` und `threading.excepthook` |
| API-Keys | `OPENAI_API_KEY` + `GROQ_API_KEY` aus einer `.env` neben der EXE, gelesen von `load_env_file` (eigener Leser, **kein** python-dotenv); echte Umgebungsvariablen haben Vorrang |
| Konfiguration | `windows/config.json` (gewählter Hotkey) |
| Tests | `windows/tests/` — 53 Prüfungen mit pytest in 10 Dateien, alle gegen reine Funktionen |

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
    └── tests/                 ← 53 Prüfungen in 10 Dateien
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

## Offene Arbeit (Stand 2026-07-29, nach Durchgang 1)

### Voraussetzung — muss VOR dem Autostart gebaut werden

- **Nur eine Instanz zulassen.** Am 29.07.2026 liefen versehentlich zwei typeFREE: beide mit eigenem Tastatur-Hook, beide nahmen auf, beide fügten ein — **jedes Diktat kam doppelt und wurde doppelt bezahlt**, beide schrieben in dieselbe Logdatei. Kein Randfall: Eine Aufgabenplanung, die regelmäßig prüft und neu startet, erzeugt das systematisch. Lösung: benannter Windows-Mutex oder Sperrdatei beim Start; ist er belegt, meldet die zweite Instanz das im Klartext und beendet sich.

### Durchgang 2 — „Autostart, Umzug und Feinschliff"

- Programmordner unter `%LOCALAPPDATA%`, `einrichten.cmd`, Windows-Aufgabenplanung (Anmeldung, Aufwachen, regelmäßige Prüfung, „Mit höchsten Privilegien")
- Nach 3 Fehlstarts in Folge aufgeben und einmalig im Klartext melden
- ~~Kosten mitrechnen und im Tray-Menü anzeigen~~ → **erledigt am 30.07.2026**, aus Durchgang 2 vorgezogen. `whisper_kosten`, `verbrauch_buchen`, `verbrauch_text` als reine Funktionen, Stand in `verbrauch.json` neben der EXE. Nur Whisper — Groq läuft im kostenlosen Tier. Gebucht wird erst nach erfolgreichem Einfügen. Offen geblieben: Groq-Tokenzahl anzeigen (kostet nichts, wäre nur Information)
- Leeres Guthaben an der fehlgeschlagenen Anfrage erkennen → rotes Icon, aber weiterlaufen
- README-Abschnitt „Warum nicht Win+H"

### Textqualität — begonnen, nicht fertig

Die Groq-Anweisung wurde am 29.07. umgebaut (Verhörer korrigieren, Umgangssprache schonen). Ergebnis **teilweise**:

| Fall | Ergebnis |
|---|---|
| „Das ist ein zweiter Test" (korrekt erkannt) | ✅ bleibt heil — die alte Anweisung machte „zweite Test" daraus |
| „Ich **glaube**, das ist nicht so gut" | ❌ wird zu „Ich **denke**" — das Verbot des Wortersetzens wird ignoriert |
| „ich wollte **gucken**" | ❌ wurde zu „wollte **wissen**" (vor dem Umbau gemessen, danach nicht erneut geprüft) |
| „Zweigetest", „die **Ants**" (statt „Ähms") | Verhörer, vor dem Umbau nicht korrigiert |

Vermutete Ursache: `llama-3.1-8b-instant` ist das kleinste Groq-Modell; Verbote befolgen kleine Modelle am schlechtesten. **Nächste Hebel:** größeres Groq-Modell testen (Zeit ist da — Groq lag unter 1 s, Whisper bei 2–6 s); Verbote als Positivbeispiele umschreiben statt als Verbotsliste.

### Nächster Slice-Kandidat: Transkription zu Groq umziehen

Am 30.07.2026 von Sebastian gemeldet: **zu langsam**, und **Deutsch-Englisch-Mischung bei schnellem Sprechen** wird schlecht erkannt. Beide Beschwerden zeigen auf denselben Schritt.

Gemessene Zeiten aus `typefree.log` vom 29.07.2026:

| Schritt | Dauer |
|---|---|
| OpenAI Whisper `whisper-1` | **2–6 s** — der Bremsklotz |
| Groq-Glättung | unter 1 s |
| Einfügen samt Stabilisierungspause | 0,3 s |

**Vorschlag:** Transkription auf Groq `whisper-large-v3-turbo` umstellen.

- Groqs Inferenzgeschwindigkeit ist an der Glättung schon belegt (unter 1 s)
- `whisper-large-v3` ist bei Sprachwechsel innerhalb eines Satzes besser als `whisper-1`; das feste `language="de"` könnte entfallen
- Ein Anbieter, ein Schlüssel — OpenAI entfällt vollständig, `WHISPER_VOKABULAR` bleibt

**Muss gemessen werden, nicht angenommen:** Messlatte sind die Zeiten oben und die aufgezeichneten Prüffälle. Ob `large-v3-turbo` auf Deutsch so genau ist wie `whisper-1`, ist offen.

### Sprachmischung — von Sebastian am 30.07.2026 gemeldet

Englische Sätze und englische Fachbegriffe werden schlecht erkannt. **Ursache im Code:** `language="de"` ist im Whisper-Aufruf festgeschrieben, Whisper versucht also auch bei Englisch, deutsche Wörter zu hören. Drei Stufen, aufsteigend nach Aufwand:

1. `WHISPER_VOKABULAR` um englische Fachbegriffe erweitern — billig, hilft aber nur bei Begriffen **innerhalb** deutscher Sätze
2. `language="de"` weglassen → Whisper erkennt die Sprache selbst. Preis: kurze deutsche Äußerungen werden gelegentlich als andere Sprache erkannt
3. **Sprachwahl im Tray-Menü** (Deutsch / Englisch / automatisch) — die saubere Lösung, eigener Slice

Zusätzlich: Die Groq-Anweisung sagt nichts über gemischte Sprache. Sie müsste englische Fachbegriffe ausdrücklich unangetastet lassen, sonst eindeutscht sie sie. **Muss gemessen werden, nicht geraten** — dieselbe Falle wie bei „glaube → denke".

### Weitere Ideen

- **Umschalt-Modus** („einmal drücken zum Starten/Beenden") mit Auswahl im Tray-Menü
- **Lokale Transkription** mit `faster-whisper` — `small` ~6× Echtzeit auf CPU, `large-v3` ~3×; langsamer als die API, dafür kostenlos und ohne Datenabfluss
- **Win+H selbst testen** — denselben Absatz einmal mit Win+H, einmal mit typeFREE diktieren, danach den Lokal-Slice neu bewerten
- **EU-Anbieter** prüfen (deutsches Whisper-Hosting, Azure OpenAI Westeuropa)
- **Datenschutz auf dem Arbeitgeber-PC** klären, bevor dort diktiert wird
- **`AltGr + Ä` als eigener Eintrag** — heute nicht nötig, weil `Alt + Ä` (Index 10) auch auf AltGr anspringt. Ein *eindeutiges* AltGr bräuchte die Unterscheidung von linkem und rechtem Alt über das Extended-Flag. Achtung: Seit der Scancode-Erkennung setzt AltGr **beide** Modifier — `Strg + Alt + M` würde bei `AltGr + M` feuern
- Groq-Whisper (`whisper-large-v3-turbo`) als schnellere Transkriptions-Alternative
- Android-APK via EAS Build (Widget schwebt über anderen Apps)
- Bei über 800 Zeilen `typefree.py` gezielt aufteilen (Stand 29.07.: ~640)
- Log-Pfad wird als `...\windows\..\typefree.log` geschrieben — funktioniert, ist aber unschön; `os.path.abspath` in `_base`

## Arbeitsweise mit Claude

- Sprache: **Deutsch**
- Erklärungen: immer WARUM, nicht nur WAS
- Jeden Schritt erst erklären, dann auf Bestätigung warten
- Commits: nur wenn explizit gewünscht
