# Plan: typeFREE — Durchgang 1 „Stabilität und Mikrofon"

**Datum:** 2026-07-29 · **Projekt:** `02_Softwareentwicklung_IT/typeFREE` · **Phase:** 3 von 8
**Grundlage:** [alignment.md](alignment.md) — Entscheidungen 2, 8, 9, 10, 11, 12, 13, 15, 20, 21

---

## Ziel

typeFREE gibt das Mikrofon frei, wenn es nicht aufnimmt, beendet die Aufnahme zuverlässig beim Loslassen, kann nicht mehr unbegrenzt Speicher fressen, hält Windows beim Herunterfahren nicht auf und schreibt jeden Fehler in eine Logdatei neben der EXE.

## Vorgehen

Alle drei Fachprüfungen richten sich auf **reine Funktionen** — Funktionen, die nur aus ihren Eingaben ein Ergebnis berechnen, ohne Mikrofon, ohne Tastatur, ohne Netz. Das ist der Grund, warum überhaupt getestet werden kann, ohne ein Mikrofon abzuklemmen. Der `main()`-Umbau (Aufgabe 1) ist die Voraussetzung dafür: Solange `typefree.py` beim Einlesen schon Threads startet, kann keine Testdatei die Datei importieren.

**Technik:** Python · pytest 9.0.3 (bereits installiert) · `sounddevice` · `pystray` · `keyboard`

## Entscheidungen aus dieser Planungsphase

| # | Entscheidung | Begründung |
|---|---|---|
| P1 | **tkinter fliegt komplett raus**, Hotkey-Auswahl wird ein Untermenü im Tray | Das Auswahlfenster war der letzte tkinter-Nutzer und genau das, worauf Windows beim Herunterfahren wartet; der Overlay-Code darin ist bereits toter Code |
| P2 | Fehler werden als **Windows-Sprechblase** am Tray gemeldet, das Icon bleibt zusätzlich rot | Braucht kein Fenster; das rote Icon hält den Zustand sichtbar, bis die nächste Aufnahme klappt |
| P3 | Logdatei **`typefree.log` neben der EXE** | Sofort auffindbar; Umzug in Durchgang 2 nimmt sie mit |
| P4 | **Registry-Autostart wird entfernt**, nicht repariert | Er funktioniert nachweislich nicht und Durchgang 2 ersetzt ihn durch die Aufgabenplanung — eine Reparatur wäre Wegwerf-Code |
| P5 | **Drei Fachprüfungen statt vier** (Hotkey-Logik, Mikrofon-Wächter, Zeitgrenze) plus ein Rauchtest | Der vierte Test aus Entscheidung 21 prüft den Autostart-Befehl und gehört damit zu Durchgang 2 |
| P6 | **Keine Commits während der Umsetzung** | `CLAUDE.md` dieses Projekts: „Commits: nur wenn explizit gewünscht"; Phase 8 macht die atomaren Commits |

## Dateien

| Datei | Was passiert |
|---|---|
| `windows/typefree.py` | Umbau — von 474 auf ca. 400 Zeilen (tkinter-Block raus, Wächter rein) |
| `windows/config.json` | `hotkey_index` von 1 (F5) auf 12 (Strg+Shift+Ä) |
| `windows/tests/conftest.py` | **neu** — macht `import typefree` in Tests möglich |
| `windows/tests/test_import_is_safe.py` | **neu** — Rauchtest |
| `windows/tests/test_hotkey_logic.py` | **neu** — 7 Prüfungen |
| `windows/tests/test_microphone_watch.py` | **neu** — 6 Prüfungen |
| `windows/tests/test_recording_limit.py` | **neu** — 4 Prüfungen |
| `windows/requirements-dev.txt` | **neu** — pytest |
| `typeFREE.spec` | tkinter aus dem Bauplan ausschließen |
| `.gitignore` | `*.log` ergänzen |
| `README.md`, `CLAUDE.md` | Hotkey-Standard und tkinter-Fakten richtigstellen |

**Bleibt unangetastet:** Groq-Anweisung (Durchgang 2), Kostenrechnung (Durchgang 2), Programmordner-Umzug (Durchgang 2), Tray-Icon-Farben Grau/Grün/Orange/Blau, Aufnahme-Modus „Halten", Whisper- und Groq-Modelle.

---

## Aufgabe 1: `main()`-Umbau — Import ohne Nebenwirkungen

Heute passiert beim Einlesen der Datei Folgendes: Zeile 38–40 baut zwei API-Clients, Zeile 92 liest `config.json`, Zeile 255 startet den Tray-Thread, Zeile 256 wartet eine halbe Sekunde, Zeile 319 startet den tkinter-Thread. Ein Test, der `import typefree` schreibt, würde also ein Tray-Icon erzeugen. Das muss weg.

Zusätzlich wandert das Tray-Icon **in den Hauptthread**. `pystray` ist dafür gebaut, und ein Programm, dessen Hauptthread die Windows-Nachrichten abarbeitet, antwortet auf das Abmeldesignal — das ist der zweite Baustein gegen den Winsrv-10001-Eintrag.

**Dateien:**
- Ändern: `windows/typefree.py` — Zeilen 38–40, 92, 255–256, 319–320, 456–474
- Neu: `windows/tests/conftest.py`
- Neu: `windows/tests/test_import_is_safe.py`

- [ ] **Schritt 1: Testgerüst anlegen**

`windows/tests/conftest.py`:

```python
"""Legt den Ordner `windows/` in den Suchpfad, damit `import typefree` klappt."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
```

- [ ] **Schritt 2: Rauchtest schreiben (muss zuerst scheitern)**

`windows/tests/test_import_is_safe.py`:

```python
"""Der Import von typefree darf nichts starten und nichts öffnen."""
import typefree


def test_import_baut_kein_tray_icon():
    assert typefree.tray_icon is None


def test_import_liest_keine_konfiguration():
    assert typefree.active_hotkey is None


def test_import_oeffnet_kein_mikrofon():
    assert typefree._stream is None
```

- [ ] **Schritt 3: Prüfen, dass der Test scheitert**

```bash
python -m pytest windows/tests/test_import_is_safe.py -v
```

Erwartet: **FAIL** — `AttributeError: module 'typefree' has no attribute '_stream'`, und der Import hängt sichtbar ein Tray-Icon in die Taskleiste.

- [ ] **Schritt 4: Zustandsvariablen auf der Modulebene deklarieren**

Ersetze in `windows/typefree.py` den Block Zeile 37–51:

```python
# ── Zustand (wird erst in main() bzw. bei der Aufnahme gefüllt) ───────────────
client        = None    # Groq
openai_client = None    # OpenAI / Whisper
active_hotkey = None
is_recording  = False
audio_frames  = []
lock          = threading.Lock()
tray_icon     = None
_stream       = None    # sounddevice.InputStream — nur während der Aufnahme

# ── Audio-Einstellungen ──────────────────────────────────────────────────────
SAMPLE_RATE = 16000
CHANNELS    = 1
```

Die Zeile `active_hotkey = load_hotkey_config()` (Zeile 92) wird **gelöscht** — sie zieht in `main()`.

`cursor_pos` fehlt in dem neuen Block absichtlich: Die Variable diente nur dazu, das Overlay-Fenster neben dem Mauszeiger zu platzieren. Ihre letzte Verwendung in `start_recording` verschwindet in Aufgabe 7. Bis dahin läuft der Code weiter, weil `global cursor_pos` die Variable bei der ersten Zuweisung selbst anlegt.

- [ ] **Schritt 5: Thread-Starts auf der Modulebene löschen**

Diese Zeilen ersatzlos entfernen:

```python
threading.Thread(target=_start_tray, daemon=True).start()   # Zeile 255
time.sleep(0.5)                                              # Zeile 256
threading.Thread(target=_overlay_thread_func, daemon=True).start()  # Zeile 319
_overlay_ready.wait()                                        # Zeile 320
```

- [ ] **Schritt 6: `main()` schreiben**

Ersetze den `if __name__ == '__main__':`-Block (Zeilen 456–474) vollständig durch:

```python
# ── Hauptprogramm ─────────────────────────────────────────────────────────────
def main():
    global active_hotkey, client, openai_client

    load_env_file()
    setup_logging()

    active_hotkey = load_hotkey_config()
    client        = Groq(api_key=os.environ.get('GROQ_API_KEY') or 'FEHLT')
    openai_client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY') or 'FEHLT')

    log.info('typeFREE gestartet — Hotkey: %s', active_hotkey['label'])
    keyboard.hook(on_key_event)

    # Das Tray-Icon läuft im Hauptthread und blockiert bis „Beenden".
    # Nur so beantwortet typeFREE das Abmeldesignal von Windows.
    _start_tray(on_ready=_report_missing_keys)
    log.info('typeFREE beendet.')


def _report_missing_keys(icon):
    """Wird aufgerufen, sobald das Tray-Icon sichtbar ist."""
    icon.visible = True
    fehlend = [n for n in ('OPENAI_API_KEY', 'GROQ_API_KEY') if not os.environ.get(n)]
    if fehlend:
        report_error(f"Kein API-Schlüssel gefunden: {', '.join(fehlend)}. "
                     f"Bitte .env neben der EXE prüfen.")


if __name__ == '__main__':
    main()
```

`load_env_file`, `setup_logging`, `log` und `report_error` entstehen in Aufgabe 5 und 6 — bis dahin startet das Programm nicht. Das ist gewollt: Die Tests laufen trotzdem, weil sie nur reine Funktionen anfassen.

- [ ] **Schritt 7: Rauchtest muss durchlaufen**

```bash
python -m pytest windows/tests/test_import_is_safe.py -v
```

Erwartet: **3 passed** — und beim Import erscheint kein Tray-Icon mehr.

---

## Aufgabe 2: Loslassen beendet die Aufnahme — immer

Der Fehler steckt in Zeile 445–447: Vor der Prüfung `KEY_UP` wird verlangt, dass alle Modifier noch gedrückt sind. Lässt man `Strg` einen Sekundenbruchteil vor `Ä` los, verwirft die Funktion das Loslassen — die Aufnahme läuft weiter, das Diktat ist verloren.

Die Lösung ist eine reine Entscheidungsfunktion. `on_key_event` bleibt die dünne Schicht, die Tastendrücke einsammelt.

**Dateien:**
- Ändern: `windows/typefree.py` — Zeilen 421–452
- Neu: `windows/tests/test_hotkey_logic.py`

- [ ] **Schritt 1: Prüfungen schreiben (müssen zuerst scheitern)**

`windows/tests/test_hotkey_logic.py`:

```python
"""Prüft die Entscheidung „starten / stoppen / nichts tun" ohne echte Tastatur."""
import typefree

STRG_SHIFT_AE = {'label': 'Strg + Shift + Ä', 'key': 'ä', 'mods': ['ctrl', 'shift']}
F5            = {'label': 'F5',               'key': 'f5', 'mods': []}


def test_druecken_mit_allen_modifiern_startet():
    ergebnis = typefree.decide_hotkey_action(
        'down', 'ä', {'ctrl', 'shift'}, STRG_SHIFT_AE, recording=False)
    assert ergebnis == 'start'


def test_loslassen_beendet_auch_wenn_strg_schon_los_ist():
    """Der eigentliche Fehler: Strg wurde vor Ä losgelassen."""
    ergebnis = typefree.decide_hotkey_action(
        'up', 'ä', set(), STRG_SHIFT_AE, recording=True)
    assert ergebnis == 'stop'


def test_druecken_ohne_modifier_startet_nicht():
    ergebnis = typefree.decide_hotkey_action(
        'down', 'ä', set(), STRG_SHIFT_AE, recording=False)
    assert ergebnis is None


def test_gehaltene_taste_startet_nicht_zweimal():
    """Windows schickt bei gehaltener Taste laufend neue KEY_DOWN-Ereignisse."""
    ergebnis = typefree.decide_hotkey_action(
        'down', 'ä', {'ctrl', 'shift'}, STRG_SHIFT_AE, recording=True)
    assert ergebnis is None


def test_loslassen_ohne_laufende_aufnahme_tut_nichts():
    ergebnis = typefree.decide_hotkey_action(
        'up', 'ä', {'ctrl', 'shift'}, STRG_SHIFT_AE, recording=False)
    assert ergebnis is None


def test_fremde_taste_wird_ignoriert():
    ergebnis = typefree.decide_hotkey_action(
        'down', 'x', {'ctrl', 'shift'}, STRG_SHIFT_AE, recording=False)
    assert ergebnis is None


def test_hotkey_ohne_modifier_startet_direkt():
    ergebnis = typefree.decide_hotkey_action(
        'down', 'f5', set(), F5, recording=False)
    assert ergebnis == 'start'
```

- [ ] **Schritt 2: Prüfen, dass die Tests scheitern**

```bash
python -m pytest windows/tests/test_hotkey_logic.py -v
```

Erwartet: **7 failed** — `AttributeError: module 'typefree' has no attribute 'decide_hotkey_action'`

- [ ] **Schritt 3: Die Entscheidungsfunktion schreiben**

Ersetze in `windows/typefree.py` den Block Zeile 421–452 durch:

```python
# ── Tastenerkennung ───────────────────────────────────────────────────────────
_mods_down = set()

# Windows meldet linke und rechte Taste getrennt, AltGr meldet sich als „alt gr".
MODIFIER_ALIASES = {
    'ctrl':  'ctrl',  'left ctrl':  'ctrl',  'right ctrl':  'ctrl',
    'shift': 'shift', 'left shift': 'shift', 'right shift': 'shift',
    'alt':   'alt',   'left alt':   'alt',   'right alt':   'alt', 'alt gr': 'alt',
}


def decide_hotkey_action(event_type, key_name, mods_down, hotkey, recording):
    """Reine Entscheidung: 'start', 'stop' oder None.

    Loslassen der Haupttaste beendet die Aufnahme IMMER — die Modifier werden
    dabei absichtlich NICHT geprüft. Sonst läuft die Aufnahme weiter, wenn man
    Strg einen Wimpernschlag vor Ä loslässt, und das Diktat ist verloren.
    """
    if key_name != hotkey['key']:
        return None
    if event_type == 'up':
        return 'stop' if recording else None
    if recording:
        return None                                    # gehaltene Taste
    if not set(hotkey['mods']).issubset(mods_down):
        return None
    return 'start'


def on_key_event(event):
    """Sammelt Tastenereignisse ein und führt die Entscheidung aus."""
    name = (event.name or '').lower()

    alias = MODIFIER_ALIASES.get(name)
    if alias:
        if event.event_type == keyboard.KEY_DOWN:
            _mods_down.add(alias)
        else:
            _mods_down.discard(alias)
        return

    event_type = 'down' if event.event_type == keyboard.KEY_DOWN else 'up'
    action = decide_hotkey_action(event_type, name, _mods_down,
                                 active_hotkey, is_recording)

    if action == 'start':
        start_recording()
    elif action == 'stop':
        threading.Thread(target=stop_and_transcribe,
                         name='transcribe', daemon=True).start()
```

- [ ] **Schritt 4: Prüfen, dass die Tests laufen**

```bash
python -m pytest windows/tests/test_hotkey_logic.py -v
```

Erwartet: **7 passed**

---

## Aufgabe 3: Mikrofon-Wächter — totes Gerät erkennen, Denkpause nicht

Zwei reine Funktionen. Die erste unterscheidet „Gerät liefert Stille" von „Raum ist leise": Ein echtes Mikrofon liefert immer Grundrauschen, exakte digitale Null bedeutet zuverlässig abgeklemmt (Entscheidung 10). Die zweite entscheidet anhand von Zeitstempeln, ob das Gerät als tot gilt.

**Dateien:**
- Ändern: `windows/typefree.py` — neuer Abschnitt vor `audio_callback` (Zeile 323)
- Neu: `windows/tests/test_microphone_watch.py`

- [ ] **Schritt 1: Prüfungen schreiben (müssen zuerst scheitern)**

`windows/tests/test_microphone_watch.py`:

```python
"""Prüft die Mikrofon-Überwachung ohne echtes Mikrofon."""
import numpy as np
import typefree


def _block(wert=0.0, laenge=160):
    block = np.zeros((laenge, 1), dtype='float32')
    if wert:
        block[42, 0] = wert
    return block


def test_exakte_nullen_gelten_als_stumm():
    assert typefree.block_is_silent(_block()) is True


def test_leises_grundrauschen_gilt_als_signal():
    assert typefree.block_is_silent(_block(1e-7)) is False


def test_denkpause_von_acht_sekunden_ist_kein_fehler():
    """Pakete kommen weiter und enthalten Rauschen — kein Fehlalarm."""
    tot = typefree.is_microphone_dead(
        now=8.0, last_data_at=7.9, last_signal_at=7.9)
    assert tot is False


def test_abgeklemmtes_geraet_liefert_keine_pakete_mehr():
    tot = typefree.is_microphone_dead(
        now=8.0, last_data_at=4.5, last_signal_at=4.5)
    assert tot is True


def test_pakete_kommen_aber_nur_exakte_nullen():
    tot = typefree.is_microphone_dead(
        now=8.0, last_data_at=7.9, last_signal_at=4.0)
    assert tot is True


def test_knapp_unter_der_grenze_schlaegt_nicht_an():
    tot = typefree.is_microphone_dead(
        now=3.0, last_data_at=0.1, last_signal_at=0.1)
    assert tot is False
```

- [ ] **Schritt 2: Prüfen, dass die Tests scheitern**

```bash
python -m pytest windows/tests/test_microphone_watch.py -v
```

Erwartet: **6 failed** — `AttributeError: module 'typefree' has no attribute 'block_is_silent'`

- [ ] **Schritt 3: Die beiden Funktionen schreiben**

Füge in `windows/typefree.py` direkt vor dem Abschnitt `# ── Audio-Callback ──` ein:

```python
# ── Mikrofon-Überwachung ──────────────────────────────────────────────────────
MIC_TIMEOUT_SECONDS = 3.0


def block_is_silent(block):
    """Wahr nur bei exakter digitaler Null.

    Ein angeschlossenes Mikrofon liefert immer Grundrauschen. Exakte Nullen
    bedeuten deshalb „abgeklemmt", nicht „leise" — sonst gäbe es bei jeder
    Denkpause einen Fehlalarm.
    """
    return not np.any(block)


def is_microphone_dead(now, last_data_at, last_signal_at,
                       limit=MIC_TIMEOUT_SECONDS):
    """Kein Datenpaket ODER nur exakte Nullen, jeweils länger als `limit`."""
    return (now - last_data_at) >= limit or (now - last_signal_at) >= limit
```

- [ ] **Schritt 4: Prüfen, dass die Tests laufen**

```bash
python -m pytest windows/tests/test_microphone_watch.py -v
```

Erwartet: **6 passed**

---

## Aufgabe 4: Zeitgrenze — 10 Minuten, Text wird trotzdem gesendet

`audio_frames` wuchs bisher unbegrenzt, solange `is_recording` wahr war — rund 230 MB pro Stunde, belegt durch den `RADAR_PRE_LEAK_64`-Eintrag vom 21.07.2026. Eine harte Obergrenze stoppt das Leck, ohne ein echtes Diktat abzuschneiden.

**Dateien:**
- Ändern: `windows/typefree.py` — Abschnitt „Mikrofon-Überwachung" erweitern
- Neu: `windows/tests/test_recording_limit.py`

- [ ] **Schritt 1: Prüfungen schreiben (müssen zuerst scheitern)**

`windows/tests/test_recording_limit.py`:

```python
"""Prüft die 10-Minuten-Obergrenze gegen das Speicherleck."""
import numpy as np
import typefree

BLOCK = 1600   # 0,1 Sekunde bei 16 kHz


def _frames(sekunden):
    anzahl = int(sekunden * typefree.SAMPLE_RATE) // BLOCK
    return [np.zeros((BLOCK, 1), dtype='float32') for _ in range(anzahl)]


def test_leere_aufnahme_hat_dauer_null():
    assert typefree.recorded_seconds([]) == 0.0


def test_dauer_wird_korrekt_gerechnet():
    assert typefree.recorded_seconds(_frames(5)) == 5.0


def test_neun_minuten_neunundfuenfzig_laeuft_weiter():
    assert typefree.recording_limit_reached(_frames(599)) is False


def test_zehn_minuten_erreichen_die_grenze():
    assert typefree.recording_limit_reached(_frames(600)) is True
```

- [ ] **Schritt 2: Prüfen, dass die Tests scheitern**

```bash
python -m pytest windows/tests/test_recording_limit.py -v
```

Erwartet: **4 failed** — `AttributeError: module 'typefree' has no attribute 'recorded_seconds'`

- [ ] **Schritt 3: Die beiden Funktionen schreiben**

Ergänze im Abschnitt „Mikrofon-Überwachung":

```python
MAX_RECORDING_SECONDS = 600   # 10 Minuten — Deckel gegen das Speicherleck


def recorded_seconds(frames, sample_rate=SAMPLE_RATE):
    """Aufnahmedauer aus den gesammelten Audioblöcken."""
    return sum(len(f) for f in frames) / sample_rate


def recording_limit_reached(frames, sample_rate=SAMPLE_RATE,
                            limit=MAX_RECORDING_SECONDS):
    """Wahr, sobald die Obergrenze erreicht ist. Der Text wird trotzdem gesendet."""
    return recorded_seconds(frames, sample_rate) >= limit
```

- [ ] **Schritt 4: Prüfen, dass die Tests laufen**

```bash
python -m pytest windows/tests/test_recording_limit.py -v
```

Erwartet: **4 passed**

- [ ] **Schritt 5: Alle Tests zusammen laufen lassen**

```bash
python -m pytest windows/tests -v
```

Erwartet: **20 passed** (3 Rauchtest + 7 Hotkey + 6 Mikrofon + 4 Zeitgrenze)

---

## Aufgabe 5: `.env`-Leser

Heute kommt typeFREE nur an die Schlüssel, wenn sie als Umgebungsvariable im Terminal gesetzt sind. Beim Autostart ist das nie der Fall — deshalb wäre der Autostart selbst mit korrigiertem Pfad gescheitert. `python-dotenv` wäre eine zusätzliche Abhängigkeit in der EXE für fünf Zeilen Arbeit (Entscheidung 8).

**Dateien:**
- Ändern: `windows/typefree.py` — neuer Abschnitt direkt nach der `_base`-Berechnung (Zeile 35)

- [ ] **Schritt 1: Den Leser schreiben**

Füge direkt nach der `_base`-Berechnung ein:

```python
# ── API-Schlüssel aus der .env neben der EXE ──────────────────────────────────
def load_env_file(path=None):
    """Liest `KEY=WERT`-Zeilen aus der .env in die Umgebungsvariablen.

    Echte Umgebungsvariablen haben Vorrang (`setdefault`) — so lässt sich beim
    Entwickeln im Terminal ein anderer Schlüssel vorgeben.
    Gibt die gefundenen Namen zurück, damit der Aufrufer prüfen kann.
    """
    path = path or os.path.join(_base, '.env')
    gefunden = []
    if not os.path.exists(path):
        return gefunden
    with open(path, 'r', encoding='utf-8-sig') as f:
        for zeile in f:
            zeile = zeile.strip()
            if not zeile or zeile.startswith('#') or '=' not in zeile:
                continue
            name, _, wert = zeile.partition('=')
            name = name.strip()
            wert = wert.strip().strip('"').strip("'")
            os.environ.setdefault(name, wert)
            gefunden.append(name)
    return gefunden
```

- [ ] **Schritt 2: Von Hand prüfen**

```bash
python -c "import sys; sys.path.insert(0,'windows'); import typefree, os; print(typefree.load_env_file()); print('OPENAI gesetzt:', bool(os.environ.get('OPENAI_API_KEY')))"
```

Erwartet: eine Liste mit den Namen aus der `.env` und `OPENAI gesetzt: True`.
Wichtig: Die Ausgabe darf **keinen Schlüsselwert** enthalten — nur die Namen.

---

## Aufgabe 6: Logdatei, Fehler-Abfänger und Fehlermeldung

Bisher galt: `console=False` in der Spec, keine Logdatei, kein `sys.excepthook`, alle Threads sind Daemon-Threads. Stirbt ein Thread an einem Fehler, hinterlässt er keine Spur — genau deshalb war nicht auffindbar, warum typeFREE verschwand.

**Dateien:**
- Ändern: `windows/typefree.py` — Import-Block und neuer Abschnitt nach `load_env_file`

- [ ] **Schritt 1: Importe ergänzen**

Im Import-Block oben ergänzen:

```python
import logging
from logging.handlers import RotatingFileHandler
```

- [ ] **Schritt 2: Logging und Abfänger schreiben**

Füge nach `load_env_file` ein:

```python
# ── Logdatei und Fehler-Abfänger ──────────────────────────────────────────────
LOG_PATH = os.path.join(_base, 'typefree.log')
log = logging.getLogger('typefree')


def setup_logging():
    """Schreibt alles nach typefree.log neben der EXE, max. 3 × 512 KB."""
    if log.handlers:
        return
    log.setLevel(logging.INFO)
    fmt = logging.Formatter(
        '%(asctime)s %(levelname)-8s [%(threadName)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S')

    datei = RotatingFileHandler(LOG_PATH, maxBytes=512 * 1024,
                                backupCount=2, encoding='utf-8')
    datei.setFormatter(fmt)
    log.addHandler(datei)

    # In der fertigen EXE (console=False) gibt es keine Standardausgabe.
    # Ein StreamHandler auf None würde beim ersten Log-Aufruf abstürzen.
    if sys.stdout is not None:
        konsole = logging.StreamHandler(sys.stdout)
        konsole.setFormatter(fmt)
        log.addHandler(konsole)

    sys.excepthook = _log_uncaught
    threading.excepthook = _log_uncaught_in_thread
    log.info('Logdatei: %s', LOG_PATH)


def _log_uncaught(exc_type, exc_value, exc_tb):
    log.critical('Unbehandelter Fehler im Hauptthread',
                 exc_info=(exc_type, exc_value, exc_tb))


def _log_uncaught_in_thread(args):
    log.critical('Unbehandelter Fehler im Thread %s', args.thread.name,
                 exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
```

- [ ] **Schritt 3: `report_error` und das rote Icon schreiben**

Ergänze bei den Icon-Definitionen (nach Zeile 197) eine fünfte Farbe:

```python
ICON_ERROR = _make_mic_icon('#ff3333')
```

Und nach den Status-Helfern:

```python
def report_error(nachricht):
    """Ein Fehler darf nie stillschweigend passieren.

    Logdatei + Windows-Sprechblase + rotes Icon. Das Icon bleibt rot, bis die
    nächste Aufnahme erfolgreich durchläuft.
    """
    log.error(nachricht)
    _set_tray_icon(ICON_ERROR, f'typeFREE — Fehler: {nachricht}')
    if tray_icon:
        try:
            tray_icon.notify('typeFREE — Fehler', nachricht)
        except Exception:
            log.exception('Sprechblase konnte nicht angezeigt werden')
```

- [ ] **Schritt 4: Alle `print()` durch Logaufrufe ersetzen**

Betroffen sind die Zeilen 89, 157, 220, 224, 338, 368, 381, 385, 402, 405, 408, 415, 457–461, 474. Muster:

```python
# vorher
print(f"[Config] Speichern fehlgeschlagen: {e}")
# nachher
log.exception('Hotkey speichern fehlgeschlagen')
```

```python
# vorher
print(f"[OK] Erkannt: {raw_text}")
# nachher
log.info('Erkannt: %s', raw_text)
```

Regel: `log.info` für den Normalverlauf, `log.warning` für Auffälligkeiten, `log.exception` innerhalb von `except`-Blöcken (schreibt den Aufrufverlauf mit), `report_error` immer dann, wenn ein **Diktat verloren geht**.

- [ ] **Schritt 5: Von Hand prüfen**

```bash
python -c "import sys; sys.path.insert(0,'windows'); import typefree; typefree.setup_logging(); typefree.log.info('Testeintrag'); print(open(typefree.LOG_PATH, encoding='utf-8').read())"
```

Erwartet: `typefree.log` enthält die Zeile `Testeintrag`.

---

## Aufgabe 7: tkinter entfernen, Hotkey-Auswahl ins Tray

Der Overlay-Code (`_set_overlay`, Zeilen 285–301) wird nirgends aufgerufen — toter Code. Übrig bleibt das Auswahlfenster. Ein eigenes Fenster ist das, was Windows beim Herunterfahren um Erlaubnis fragt; verschwindet es, verschwindet auch der Winsrv-10001-Eintrag (Entscheidung P1). Die Auswahl zieht als Untermenü ins Tray — dort, wo man die Einstellung eines Hintergrundprogramms sucht.

**Dateien:**
- Ändern: `windows/typefree.py` — Zeilen 23–24, 94–181, 199–256, 259–320
- Ändern: `windows/config.json`

- [ ] **Schritt 1: tkinter-Importe löschen**

```python
import tkinter as tk                    # Zeile 23 — löschen
from tkinter import font as tkfont      # Zeile 24 — löschen (war ohnehin unbenutzt)
```

- [ ] **Schritt 2: Auswahlfenster und Overlay-Block löschen**

Ersatzlos entfernen:
- `show_hotkey_selector` samt der inneren Funktion `_open` (Zeilen 95–181)
- Den ganzen Abschnitt `# ── Cursor-Popup / Tk-Root ──` (Zeilen 259–320): `_overlay_root`, `_overlay_label`, `_overlay_ready`, `_overlay_thread_func`, `_set_overlay`
- Die Variable `cursor_pos` und die Zeile `cursor_pos = pyautogui.position()` in `start_recording` (Zeile 333) — sie diente nur der Positionierung des Overlays

`pyautogui` bleibt im Import — es fügt den Text mit `Strg+V` ein.

- [ ] **Schritt 3: Status-Helfer an die Stelle der Overlay-Funktionen setzen**

Ersetze `show_recording_overlay`, `show_transcribing_overlay`, `show_polishing_overlay` und `hide_overlay` (Zeilen 303–317) durch:

```python
def _status_idle():
    _set_tray_icon(ICON_IDLE, f"typeFREE — {active_hotkey['label']}")


def _status_recording():
    _set_tray_icon(ICON_RECORDING, 'typeFREE — nimmt auf ...')


def _status_transcribing():
    _set_tray_icon(ICON_TRANSCRIBING, 'typeFREE — transkribiert ...')


def _status_polishing():
    _set_tray_icon(ICON_POLISHING, 'typeFREE — glättet ...')
```

Die Sprechblase „● Aufnahme läuft" (Zeilen 306–307) fällt weg — das grüne Icon reicht (Entscheidung 15). Alle Aufrufstellen von `show_*_overlay` und `hide_overlay` in `start_recording` und `stop_and_transcribe` auf die neuen Namen umstellen.

- [ ] **Schritt 4: Standard-Hotkey auf Strg+Shift+Ä umstellen**

In `load_hotkey_config` (Zeilen 73–81):

```python
DEFAULT_HOTKEY_INDEX = 12   # Strg + Shift + Ä — F5 kollidiert mit der
                            # Funktionstasten-Belegung des Rechners


def load_hotkey_config():
    """Lädt die gespeicherte Hotkey-Wahl, Standard: Strg + Shift + Ä."""
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            idx = json.load(f).get('hotkey_index', DEFAULT_HOTKEY_INDEX)
            return HOTKEY_OPTIONS[idx]
    except Exception:
        return HOTKEY_OPTIONS[DEFAULT_HOTKEY_INDEX]
```

`windows/config.json` enthält heute `"hotkey_index": 1` (= F5) und würde den neuen Standard überstimmen. Inhalt ersetzen durch:

```json
{
  "hotkey_index": 12
}
```

- [ ] **Schritt 5: Tray-Menü mit Untermenü bauen**

Ersetze `_start_tray` (Zeilen 231–253) durch:

```python
def _select_hotkey(index):
    """Baut den Menü-Handler für einen Eintrag der Auswahlliste."""
    def _apply(icon, item):
        global active_hotkey
        active_hotkey = HOTKEY_OPTIONS[index]
        save_hotkey_config(index)
        log.info('Hotkey geändert auf: %s', active_hotkey['label'])
        _status_idle()
        icon.update_menu()
    return _apply


def _hotkey_submenu():
    """13 Einträge mit Punkt-Markierung beim aktiven Hotkey."""
    return pystray.Menu(*(
        pystray.MenuItem(
            opt['label'],
            _select_hotkey(i),
            checked=lambda item, i=i: active_hotkey is HOTKEY_OPTIONS[i],
            radio=True,
        )
        for i, opt in enumerate(HOTKEY_OPTIONS)
    ))


def _start_tray(on_ready=None):
    """Blockiert im Hauptthread, bis „Beenden" gewählt wird."""
    global tray_icon
    menu = pystray.Menu(
        pystray.MenuItem('typeFREE', None, enabled=False),
        pystray.MenuItem(lambda item: f"Hotkey: {active_hotkey['label']}",
                         None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Hotkey wählen', _hotkey_submenu()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Beenden', _on_quit),
    )
    tray_icon = pystray.Icon(
        name='typeFREE',
        icon=ICON_IDLE,
        title=f"typeFREE — {active_hotkey['label']}",
        menu=menu,
    )
    tray_icon.run(setup=on_ready)
```

- [ ] **Schritt 6: Sauber beenden statt `os._exit`**

Ersetze `_on_quit` (Zeilen 227–229):

```python
def _on_quit(icon, item):
    """Beendet ordentlich: Mikrofon freigeben, Icon stoppen, main() läuft aus."""
    log.info('Beenden über Tray-Menü')
    _close_stream()
    icon.stop()
```

`os._exit(0)` war der Grund, warum nichts mehr aufgeräumt wurde. Da `_start_tray` jetzt im Hauptthread läuft, kehrt `main()` nach `icon.stop()` von selbst zurück; die Daemon-Threads enden mit dem Prozess.

- [ ] **Schritt 7: Prüfen, dass kein tkinter mehr vorkommt**

```bash
python -m pytest windows/tests -v
```

Erwartet: **20 passed**

```bash
grep -n "tkinter\|_overlay\|cursor_pos\|show_hotkey_selector\|os._exit" windows/typefree.py
```

Erwartet: **keine Ausgabe**.

---

## Aufgabe 8: Registry-Autostart entfernen

Der Menüpunkt „Mit Windows starten" schreibt den Pfad ohne Anführungszeichen in die Registry (Zeile 223) — bei einem Pfad mit Leerzeichen scheitert der Start. Selbst mit korrigiertem Pfad kann der Registry-Eintrag sich keine Admin-Rechte holen, und der Tastatur-Hook wäre vor Admin-Fenstern blind. Durchgang 2 baut den Autostart über die Windows-Aufgabenplanung neu (Entscheidung 3). Ein Knopf, der nichts tut, ist schlechter als kein Knopf.

**Dateien:**
- Ändern: `windows/typefree.py` — Zeilen 26, 204–225, 239–243

- [ ] **Schritt 1: Autostart-Code löschen**

Ersatzlos entfernen:
- `import winreg` (Zeile 26)
- `AUTOSTART_KEY`, `AUTOSTART_NAME` (Zeilen 204–205)
- `_is_autostart` (Zeilen 207–214)
- `_toggle_autostart` (Zeilen 216–225)
- Den Menüeintrag „Mit Windows starten" samt dem `Menu.SEPARATOR` darüber (Zeilen 239–244) — in Aufgabe 7 ist er im neuen `_start_tray` bereits nicht mehr enthalten

- [ ] **Schritt 2: Prüfen**

```bash
grep -n "winreg\|autostart\|AUTOSTART" windows/typefree.py
```

Erwartet: **keine Ausgabe**.

- [ ] **Schritt 3: Alten Registry-Eintrag von Hand entfernen**

Falls typeFREE früher einmal in die Registry geschrieben hat, bleibt der Eintrag sonst als Karteileiche stehen. Erst anschauen:

```bash
reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v typeFREE
```

Nur falls ein Eintrag gemeldet wird, entfernen:

```bash
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v typeFREE /f
```

---

## Aufgabe 9: Mikrofon nur während der Aufnahme öffnen

Heute öffnet Zeile 463 den Audio-Stream beim Start und schließt ihn erst beim Beenden — daher das blaue Dauersymbol in der Taskleiste, und das Gerät ist für andere Programme belegt. Der Stream wird jetzt beim Drücken geöffnet und **vor** dem Netzaufruf geschlossen, damit das Symbol sofort verschwindet (Entscheidung 2).

**Dateien:**
- Ändern: `windows/typefree.py` — Zeilen 323–338, 373–418, `main()`

- [ ] **Schritt 1: Öffnen und Schließen schreiben**

Füge im Abschnitt „Mikrofon-Überwachung" ein:

```python
_last_data_at   = 0.0    # Zeitpunkt des letzten Datenpakets (time.monotonic)
_last_signal_at = 0.0    # Zeitpunkt des letzten Pakets mit echtem Signal
_session        = 0      # zählt Aufnahmen, damit alte Wächter sich beenden


def _open_stream():
    """Öffnet das Mikrofon. Kostet ca. 0,2 s — bewusst in Kauf genommen."""
    global _stream
    _stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype='float32',
        callback=audio_callback,
    )
    _stream.start()


def _close_stream():
    """Gibt das Mikrofon frei. Mehrfacher Aufruf ist unschädlich."""
    global _stream
    stream, _stream = _stream, None
    if stream is None:
        return
    try:
        stream.stop()
        stream.close()
    except Exception:
        log.exception('Mikrofon schließen fehlgeschlagen')
```

- [ ] **Schritt 2: `audio_callback` erweitern**

Ersetze `audio_callback` (Zeilen 324–327):

```python
def audio_callback(indata, frames, time_info, status):
    global _last_data_at, _last_signal_at
    if status:
        # Bisher wurde `status` ignoriert — hier melden sich verlorene Pakete
        # und Gerätefehler, die den stillen Ausfall erklären.
        log.warning('Audio-Gerätemeldung: %s', status)
    if not is_recording:
        return
    jetzt = time.monotonic()
    _last_data_at = jetzt
    if not block_is_silent(indata):
        _last_signal_at = jetzt
    with lock:
        audio_frames.append(indata.copy())
```

- [ ] **Schritt 3: `start_recording` umbauen**

Ersetze `start_recording` (Zeilen 331–338):

```python
def start_recording():
    global is_recording, audio_frames, _last_data_at, _last_signal_at, _session
    with lock:
        audio_frames = []
    jetzt = time.monotonic()
    _last_data_at   = jetzt
    _last_signal_at = jetzt
    _session += 1
    session = _session

    try:
        _open_stream()
    except Exception:
        log.exception('Mikrofon konnte nicht geöffnet werden')
        report_error('Mikrofon konnte nicht geöffnet werden — siehe typefree.log')
        return

    is_recording = True
    _status_recording()
    threading.Thread(target=_watch_recording, args=(session,),
                     name='watchdog', daemon=True).start()
    log.info('Aufnahme läuft')
```

`_watch_recording` entsteht erst in **Aufgabe 10**. Zwischen Aufgabe 9 und 10 bricht eine Aufnahme deshalb mit `NameError` ab — der Fehler landet dank Aufgabe 6 in `typefree.log`. Zwischendurch nicht von Hand testen, sondern Aufgabe 10 direkt anschließen.

- [ ] **Schritt 4: `stop_and_transcribe` umbauen**

Ersetze `stop_and_transcribe` (Zeilen 373–418):

```python
def stop_and_transcribe():
    global is_recording

    with lock:
        if not is_recording:
            return          # verhindert doppeltes Senden, wenn die Zeitgrenze
                            # und das Loslassen fast gleichzeitig zuschlagen
        is_recording = False
        frames = list(audio_frames)

    _close_stream()          # Mikrofon SOFORT freigeben, vor dem Netzaufruf
    _status_transcribing()

    if not frames:
        _status_idle()
        log.warning('Keine Audiodaten — Taste länger halten')
        return

    log.info('Sende %.1f s Audio an Whisper', recorded_seconds(frames))
    audio_data = np.concatenate(frames, axis=0)

    buffer = io.BytesIO()
    sf.write(buffer, audio_data, SAMPLE_RATE, format='WAV', subtype='PCM_16')
    buffer.seek(0)
    buffer.name = 'audio.wav'

    try:
        transcript = openai_client.audio.transcriptions.create(
            model='whisper-1', file=buffer, language='de')
        raw_text = transcript.text.strip()
        log.info('Erkannt: %s', raw_text)

        _status_polishing()
        polished = polish_text(raw_text)
        final_text = polished if polished else raw_text
        log.info('Geglättet: %s', final_text)

        pyperclip.copy(final_text)
        time.sleep(0.3)
        pyautogui.hotkey('ctrl', 'v')
        _status_idle()        # nur im Erfolgsfall zurück auf grau

    except Exception as e:
        log.exception('Transkription fehlgeschlagen')
        report_error(f'Text konnte nicht erzeugt werden: {e}')
```

Der frühere `finally: hide_overlay()` ist absichtlich weg: Er hätte das rote Icon sofort wieder auf grau gesetzt und den Fehler unsichtbar gemacht.

- [ ] **Schritt 5: Den Dauer-Stream aus `main()` entfernen**

Der `with sd.InputStream(...)`-Block aus dem alten `if __name__`-Abschnitt existiert nach Aufgabe 1 nicht mehr. Zur Sicherheit prüfen:

```bash
grep -n "sd.InputStream" windows/typefree.py
```

Erwartet: **genau eine Stelle** — innerhalb von `_open_stream`.

- [ ] **Schritt 6: Tests laufen lassen**

```bash
python -m pytest windows/tests -v
```

Erwartet: **20 passed**

---

## Aufgabe 10: Der Wächter-Thread

Der Wächter läuft nur während einer Aufnahme, prüft viermal je Sekunde und macht zwei Dinge: Zeitgrenze durchsetzen und totes Mikrofon erkennen. Bei totem Gerät wird **einmal** neu verbunden; erst wenn das misslingt, gibt es roten Alarm (Entscheidung 9).

**Dateien:**
- Ändern: `windows/typefree.py` — Abschnitt „Mikrofon-Überwachung" erweitern

- [ ] **Schritt 1: Neuverbindung und Wächter schreiben**

```python
def _reconnect_microphone():
    """Einmaliger Versuch, das Mikrofon neu zu öffnen. Setzt die Uhren zurück."""
    global _last_data_at, _last_signal_at
    log.warning('Mikrofon antwortet nicht — neu verbinden')
    _close_stream()
    try:
        _open_stream()
    except Exception:
        log.exception('Neu verbinden fehlgeschlagen')
        return False
    jetzt = time.monotonic()
    _last_data_at   = jetzt
    _last_signal_at = jetzt
    return True


def _watch_recording(session):
    """Wacht über eine einzelne Aufnahme.

    `session` sorgt dafür, dass ein Wächter aus einer früheren Aufnahme sich
    beendet, statt in die neue hineinzureden.
    """
    global is_recording
    reconnected = False

    while True:
        time.sleep(0.25)
        if not is_recording or session != _session:
            return

        with lock:
            frames = list(audio_frames)

        if recording_limit_reached(frames):
            log.info('Zeitgrenze von %s Sekunden erreicht — Text wird trotzdem '
                     'gesendet', MAX_RECORDING_SECONDS)
            threading.Thread(target=stop_and_transcribe,
                             name='transcribe', daemon=True).start()
            return

        if is_microphone_dead(time.monotonic(), _last_data_at, _last_signal_at):
            if not reconnected and _reconnect_microphone():
                reconnected = True
                continue
            is_recording = False
            _close_stream()
            report_error('Mikrofon liefert keine Daten. Bitte Gerät in den '
                         'Windows-Einstellungen prüfen.')
            return
```

- [ ] **Schritt 2: Tests laufen lassen**

```bash
python -m pytest windows/tests -v
```

Erwartet: **20 passed**

- [ ] **Schritt 3: Programm von Hand starten**

Als Administrator, weil der Tastatur-Hook es braucht:

```bash
python windows/typefree.py
```

Erwartet: Tray-Icon erscheint grau, `typefree.log` enthält „typeFREE gestartet — Hotkey: Strg + Shift + Ä", und in der Taskleiste ist **kein** blaues Mikrofonsymbol zu sehen.

---

## Aufgabe 11: Bauplan, Git-Ausschlüsse, Testabhängigkeit

**Dateien:**
- Ändern: `typeFREE.spec`
- Ändern: `.gitignore`
- Neu: `windows/requirements-dev.txt`

- [ ] **Schritt 1: tkinter aus dem Bauplan ausschließen**

In `typeFREE.spec`, Zeile 12:

```python
    excludes=['tkinter'],
```

Ohne diesen Eintrag packt PyInstaller tkinter weiter mit ein, obwohl es niemand mehr braucht — die EXE bleibt unnötig groß.

- [ ] **Schritt 2: Logdatei aus Git ausschließen**

In `.gitignore` ergänzen:

```
# Logdatei liegt neben der EXE
*.log
```

- [ ] **Schritt 3: Testabhängigkeit festhalten**

`windows/requirements-dev.txt`:

```
# Zusätzlich zu requirements.txt — nur für die Tests, nicht in der EXE
pytest>=8.0
```

- [ ] **Schritt 4: EXE neu bauen und prüfen**

```bash
pyinstaller typeFREE.spec
```

Erwartet: `dist/typeFREE.exe` mit aktuellem Datum und **kleiner** als die alte Datei (tkinter fehlt).
Danach die `.env` neben `dist/typeFREE.exe` legen — sonst findet die EXE keine Schlüssel.

---

## Aufgabe 12: Dokumentation richtigstellen

`README.md` und `CLAUDE.md` behaupten nach dem Umbau Falsches: „Standard F5", das tkinter-Auswahlfenster, kein Logging. Falsche Dokumentation ist schlimmer als keine.

**Dateien:**
- Ändern: `README.md`
- Ändern: `CLAUDE.md`

Die Fundstellen sind bereits gesucht und belegt. Genau diese acht Stellen sind anzupassen:

- [ ] **Schritt 1: `README.md`**

| Zeile | Was ist falsch | Was hin muss |
|---|---|---|
| 13 | „Standard: `F5` halten" | „Standard: `Strg + Shift + Ä` halten" |
| 16 | „Das Tray-Menü bietet zusätzlich einen Autostart-Schalter, der typeFREE über den Windows-Registry-Schlüssel `HKCU\...\Run` beim Systemstart mitlädt." | Satz **streichen**. Statt dessen: fünfte Farbe **Rot = Fehler** in die Aufzählung der Statusfarben aufnehmen |
| 31 | Mermaid-Diagramm: `A[Benutzer hält Hotkey, Standard F5]` | `A[Benutzer hält Hotkey, Standard Strg+Shift+Ä]` |
| 84 | „Persistierte Hotkey-Wahl (Standard: F5)" | „(Standard: Strg + Shift + Ä)" |
| 97 | „API-Schlüssel als Umgebungsvariablen bereitstellen" | „API-Schlüssel in eine `.env` neben der EXE schreiben" samt Beispielinhalt der `.env` |

- [ ] **Schritt 2: `CLAUDE.md`**

| Zeile | Was ist falsch | Was hin muss |
|---|---|---|
| 6 | „Standard F5, im Tray-Menü umstellbar" | „Standard Strg + Shift + Ä, über das Tray-Untermenü ‚Hotkey wählen' umstellbar" |
| 21 | Tabellenzeile Status | ergänzen: fünf Farben inkl. **Rot = Fehler**; Fehler zusätzlich als Windows-Sprechblase |
| 22 | „`OPENAI_API_KEY` + `GROQ_API_KEY` als **Umgebungsvariablen** (`os.environ`, kein python-dotenv)" | „aus `.env` neben der EXE, gelesen von `load_env_file` (eigener Leser, kein python-dotenv)" |

Zusätzlich im Block „Versionierte Struktur" ergänzen:

```
└── windows/
    ├── typefree.py
    ├── requirements.txt
    ├── requirements-dev.txt   ← neu: pytest
    ├── config.json
    └── tests/                 ← neu: die drei Fachprüfungen + Rauchtest
```

Und eine Zeile bei „Wichtige technische Erkenntnisse": *Logdatei liegt als `typefree.log` neben der EXE — ohne sie sind Abstürze bei `console=False` unauffindbar.*

**Nicht** anzufassen: der Abschnitt „Warum nicht Win+H" (Entscheidung 24) — der gehört zu Durchgang 2.

---

## Handprüfung für Phase 5

Diese Punkte aus `alignment.md` lassen sich nach Durchgang 1 prüfen. Der Rest wartet auf Durchgang 2.

- [ ] Das blaue Windows-Mikrofonsymbol erscheint **nur während** einer Aufnahme
- [ ] `Strg` vor `Ä` loslassen → Aufnahme stoppt trotzdem und der Text wird eingefügt
- [ ] Beim Drücken 8 Sekunden nachdenken, ohne zu sprechen → **kein** Fehlalarm
- [ ] Mikrofon in den Windows-Einstellungen deaktivieren → rotes Icon **und** Sprechblase binnen 3 Sekunden
- [ ] Windows herunterfahren → kein neuer Winsrv-10001-Eintrag im Ereignisprotokoll
- [ ] Hotkey über das Tray-Untermenü umstellen → Punkt-Markierung wandert, neuer Hotkey wirkt sofort
- [ ] `python -m pytest windows/tests -v` → **20 passed**
- [ ] Nach einem gewollten Absturz steht der Fehler samt Aufrufverlauf in `typefree.log`

**Nicht prüfbar in Durchgang 1** (kommt mit Durchgang 2): Neustart-Verhalten, Aufwachen aus dem Ruhezustand, Selbstheilung nach 5 Minuten, Kostenanzeige im Tray, USB-Stick-Umzug, Slang-Erhaltung.

## Vorgemerkt für später

- Der `.env`-Leser wäre eine vierte, sehr billige Fachprüfung wert (Kommentarzeilen, Anführungszeichen, Vorrang echter Umgebungsvariablen) — bewusst nicht in diesem Durchgang, weil die Testliste in `alignment.md` auf drei festgelegt wurde
- Die 3-Sekunden-Grenze und die 10-Minuten-Grenze stehen als Konstanten im Code, nicht in `config.json` — falls sie sich im Alltag als falsch erweisen, wäre das ein eigener kleiner Slice

---

*Erstellt mit dem Skill `writing-plans`. Nach Abschluss von Phase 8 löschen (Phasendateien werden aufgeräumt).*
