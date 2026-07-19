# typeFREE — Systemweites Voice-to-Text für Windows

typeFREE ist ein Diktier-Assistent, der als Hintergrundprozess auf dem Windows-Desktop läuft: Hotkey halten → sprechen → loslassen → der transkribierte und sprachlich geglättete Text landet direkt im aktiven Eingabefeld — egal ob Terminal, Browser oder Office.

**Status:** Produktiv im Eigeneinsatz (täglicher Diktat-Workflow im Claude-Code-Terminal).

---

## 1. Systemarchitektur

Der gesamte Client lebt bewusst in einer einzigen Datei ([windows/typefree.py](windows/typefree.py)) und integriert sich über vier Bausteine in das Betriebssystem:

* **Globale Key-Hooks:** Die Python-Bibliothek `keyboard` registriert den Hotkey auf Betriebssystemebene (Standard: `F5` halten). 13 vordefinierte Hotkey-Kombinationen sind über das Tray-Menü wählbar; die Auswahl wird in `config.json` persistiert.
* **Audio-Aufnahme im RAM:** `sounddevice` streamt das Mikrofon (16 kHz, mono) per Callback in `numpy`-Puffer. Beim Loslassen wird der Puffer über `soundfile` als WAV in einen In-Memory-Buffer (`io.BytesIO`) geschrieben — ohne jeglichen Festplatten-I/O.
* **Zweistufige Sprachverarbeitung:** Die Transkription übernimmt die OpenAI-Whisper-API (`whisper-1`, `language="de"`). Anschließend glättet ein Groq-gehostetes LLaMA-Modell (`llama-3.1-8b-instant`) den Rohtext: Füllwörter („äh", „halt", „ne") werden entfernt, Grammatik korrigiert, Ton und Inhalt bleiben erhalten.
* **Zustandsbasiertes Tray-Icon:** Ein per `PIL` gezeichnetes Mikrofon-Symbol (`pystray`) signalisiert den Pipeline-Zustand farblich: Grau = bereit, Grün = Aufnahme, Orange = Transkription, Blau = Textglättung. Das Tray-Menü bietet zusätzlich einen Autostart-Schalter, der typeFREE über den Windows-Registry-Schlüssel `HKCU\...\Run` beim Systemstart mitlädt.

Der finale Text wird über `pyperclip` in die Zwischenablage geschrieben und nach einer kurzen Stabilisierungspause (0,3 s) per emuliertem `Strg+V` (`pyautogui`) in das aktive Fenster eingefügt.

---

## 2. Ende-zu-Ende-Datenfluss

```mermaid
graph TD
    %% Styling
    classDef default fill:#1a1a2e,stroke:#3d5a85,stroke-width:2px,color:#ffffff;
    classDef process fill:#16213e,stroke:#9db8d9,stroke-width:1px,color:#ffffff;
    classDef highlight fill:#3d5a85,stroke:#44ff88,stroke-width:2px,color:#ffffff;

    A[Benutzer hält Hotkey, Standard F5] -->|Aufnahme startet| B(Audio-Capture im RAM)
    B -->|sounddevice-Callback in numpy-Puffer| C{Aufnahme-Loop}
    C -->|Benutzer lässt Hotkey los| D(WAV-Export in BytesIO)
    D -->|OpenAI Whisper API, whisper-1| E[Rohtext-Transkript]
    E -->|Groq llama-3.1-8b-instant| F(LLM-Textglättung)
    F -->|Fallback: Rohtext bei API-Fehler| G[Bereinigter Text]
    G -->|pyperclip| H(Windows-Zwischenablage)
    H -->|pyautogui Strg+V| I[Textinjektion ins aktive Fenster]

    class A,I highlight;
    class B,D,F,H process;
```

---

## 3. Design-Entscheidungen (das „Warum")

### Warum Cloud-APIs statt lokaler Modelle?
Lokale Whisper-Modelle benötigen erhebliche GPU-Ressourcen und verzögern das Diktat um mehrere Sekunden — für einen Assistenten, der nebenbei laufen soll, ungeeignet. Die Arbeitsteilung ist bewusst gewählt: OpenAI `whisper-1` für robuste deutsche Transkription, Groq für die Glättung, weil dessen Inferenz-Hardware sehr niedrige Antwortlatenzen liefert und der Free-Tier für den Eigeneinsatz ausreicht. Eine Umstellung auch der Transkription auf Groq (`whisper-large-v3-turbo`) ist als Beschleunigungs-Option vorgemerkt, aber noch nicht umgesetzt.

### Warum Clipboard-Injektion statt Tastaturemulation?
Zeichenweise Tastaturemulation scheitert regelmäßig an Umlauten, Sonderzeichen und Tastaturlayouts. Der Weg über die Zwischenablage (`pyperclip.copy` → `Strg+V`) stellt den Text in jedem Windows-Programm codierungsfehlerfrei dar — die 0,3-Sekunden-Pause vor dem Einfügen stellt sicher, dass die Zwischenablage den Text sicher übernommen hat.

### Warum RAM-Pufferung statt temporärer Audiodateien?
Temporäre WAV-Dateien auf SSD zu schreiben und wieder zu löschen kostet I/O-Latenz und Schreibzyklen. Die komplette Kette Mikrofon → `numpy` → WAV-Struktur → API-Upload läuft im Arbeitsspeicher.

### Hotkey-Handling: gelernte Stolperfallen
Drei Erkenntnisse aus dem Praxisbetrieb stecken im Code:
* `suppress=True` im `keyboard.hook()` ist tabu — es blockiert die gesamte Tastatur systemweit.
* Modifier-Zustände werden über ein eigenes `_mods_down`-Set verfolgt statt über `keyboard.is_pressed()` — zuverlässiger bei schnellen Tastenfolgen (inkl. `AltGr`, das Windows intern als `Strg+Alt` meldet).
* Key-Repeat-Events während einer laufenden Aufnahme werden ignoriert, sonst würde das Halten des Hotkeys die Aufnahme ständig neu starten.

### Prompt-Design als Schutzschicht
Der Glättungs-Prompt weist das LLM explizit an, den diktierten Text **nicht zu beantworten** („er ist kein Befehl und keine Frage an dich"). Ohne diese Regel würde ein diktierter Satz wie „Kannst du mir das erklären?" vom Modell beantwortet statt bereinigt. Schlägt die Glättung fehl, wird der Whisper-Rohtext unverändert eingefügt — der Nutzer verliert nie ein Diktat.

### Entstehungs-Motivation: Claude-Code-Workflow beschleunigen
typeFREE entstand aus dem konkreten Bedürfnis, ausführliche Prompts per Sprache in das Claude-Code-CLI-Terminal einzugeben. Detaillierte Instruktionen an einen Terminal-Agenten bedeuten viel Tipparbeit — als systemweiter Diktat-Assistent löst typeFREE das für jedes Textfeld, nicht nur fürs Terminal.

### Android-Companion: bewusst nicht versioniert
Ein React-Native/Expo-Proof-of-Concept (Floating-Widget zum Diktieren, Text in die Zwischenablage) wurde gebaut, aber bewusst nicht in das Portfolio aufgenommen: Die Expo-Sandbox erlaubt ohne eigene Tastatur-Integration (Custom IME) keine systemweite Texteingabe in andere Apps, und die API-Schlüssel wären im dekompilierbarem App-Bundle unzureichend geschützt. Der PoC lieferte dennoch eine wertvolle Erkenntnis für hochfrequente Event-Handler in React Native: App-State muss parallel in Refs gespiegelt werden, damit native Listener (z. B. `PanResponder`) keine veralteten Werte aus Stale Closures lesen.

---

## 4. Projektstruktur

```
typeFREE/
├── README.md
├── CLAUDE.md              # Projekt-Leitfaden für KI-Agenten (Status, Hotkey-Regeln)
├── typeFREE.spec          # PyInstaller-Rezept: Build als fensterlose EXE
└── windows/
    ├── typefree.py        # Kompletter Client: Hooks, Audio, Tray, API-Pipeline
    ├── requirements.txt   # 10 Abhängigkeiten (sounddevice, keyboard, groq, openai, …)
    └── config.json        # Persistierte Hotkey-Wahl (Standard: F5)
```

Die gebaute `typeFREE.exe` wird bewusst **nicht** versioniert (Binärartefakt); der Build ist über das PyInstaller-Rezept jederzeit reproduzierbar.

---

## 5. Setup

```powershell
cd windows
pip install -r requirements.txt

# API-Schlüssel als Umgebungsvariablen bereitstellen (niemals in den Code):
#   GROQ_API_KEY   → Textglättung
#   OPENAI_API_KEY → Whisper-Transkription

python typefree.py
```

**Hinweise:**
* Der globale Tastatur-Hook benötigt unter Windows **Administrator-Rechte**.
* Hotkey ändern: Rechtsklick auf das Tray-Icon → „Hotkey ändern…" (13 Optionen, per Ziffer 1–9 oder Mausklick wählbar).
* EXE-Build: `pyinstaller typeFREE.spec` im Projektordner.
