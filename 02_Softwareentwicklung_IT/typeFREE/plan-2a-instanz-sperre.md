# Plan: typeFREE Slice 2a — Nur eine Instanz

**Datum:** 2026-07-31 · **Phase:** 3 von 8 · **Voraussetzung für:** Durchgang 2 komplett

---

## Warum dieser Slice zuerst kommt

Am 29.07.2026 liefen versehentlich zwei typeFREE gleichzeitig. Beide hatten einen eigenen Tastatur-Hook, beide nahmen auf, beide transkribierten, beide fügten ein: **Jedes Diktat kam doppelt an und wurde doppelt bezahlt.** Belegt im Protokoll:

```
22:01:57  Aufnahme läuft        ← Instanz A
22:01:58  Aufnahme läuft        ← Instanz B
22:01:59  Sende 1.5 s Audio     (zweimal)
```

Beide schrieben außerdem in dieselbe Logdatei — der `RotatingFileHandler` beider Prozesse rotiert unabhängig und kann die Datei beschädigen.

**Das ist kein Randfall.** Entscheidung 3 sieht eine Windows-Aufgabenplanung vor, die regelmäßig prüft und typeFREE bei Bedarf neu startet. Ohne Sperre erzeugt genau diese Selbstheilung den Doppelstart systematisch. Die Sperre ist damit **Voraussetzung**, nicht Beiwerk.

## Entscheidungen für diesen Slice

| # | Entscheidung | Begründung |
|---|---|---|
| 2a-1 | **Benannter Windows-Mutex** statt Sperrdatei | Windows gibt ihn beim Prozessende **immer** frei — auch nach Absturz oder Abschuss im Task-Manager. Eine Sperrdatei würde liegen bleiben, und das Aufräumen verwaister Dateien ist genau die Stelle, an der man sich aussperrt |
| 2a-2 | Namensraum **`Local\`**, nicht `Global\` | Die Sperre gilt je Windows-Sitzung. Ein zweiter Windows-Benutzer darf sein eigenes typeFREE starten. `Global\` bräuchte zudem erhöhte Rechte |
| 2a-3 | Zweite Instanz: **Meldungsfenster, dann beenden** | Von Hand gestartet willst du wissen, warum nichts passiert |
| 2a-4 | **Ausnahme: Schalter `--autostart` schweigt** | Die Aufgabenplanung prüft alle paar Minuten. Ohne diese Ausnahme stapeln sich Meldungsfenster. Sie schreibt nur ins Protokoll |
| 2a-5 | Meldungsfenster über **`ctypes.MessageBoxW`**, nicht pystray | Eine Sprechblase braucht ein laufendes Tray-Icon mit Nachrichtenschleife. Die zweite Instanz soll sich sofort beenden, also gibt es kein Icon |
| 2a-6 | Die Entscheidung liegt in einer **reinen Funktion** | „Sperre belegt" + „Autostart-Schalter" → Verhalten. Prüfbar ohne zweiten Prozess |
| 2a-7 | Sperre wird **vor** allem anderen genommen | Vor Tastatur-Hook, Tray-Icon und Logging-Setup. Eine zweite Instanz darf nicht einmal kurz einen Hook einhängen |

## Nicht-Ziele

- Kein Ordnerumzug nach `%LOCALAPPDATA%` (Slice 2b)
- Keine Aufgabenplanung, keine 3-Fehlstart-Regel (Slice 2c)
- Kein Erkennen einer *hängenden* Instanz — eine laufende Instanz gilt als gesund
- Kein Verdrängen der alten Instanz: Ein laufendes Diktat würde mitten in der Transkription abgebrochen und wäre verloren

## Dateien

| Datei | Was passiert |
|---|---|
| `windows/typefree.py` | Mutex-Sperre, `zweitstart_verhalten`, Auswertung von `--autostart`, Aufruf am Anfang von `main()` |
| `windows/tests/test_einzelinstanz.py` | **neu** — Prüfungen für die Entscheidungslogik |

---

## Aufgabe 1: Die Entscheidung als reine Funktion

Der Kern ist eine Wahrheitstabelle mit vier Fällen. Die gehört in eine Funktion ohne Nebenwirkungen, damit sie ohne zweiten Prozess prüfbar ist.

**Dateien:**
- Neu: `windows/tests/test_einzelinstanz.py`
- Ändern: `windows/typefree.py` — neuer Abschnitt vor `# ── Hauptprogramm ──`

- [ ] **Schritt 1: Prüfungen schreiben**

`windows/tests/test_einzelinstanz.py`:

```python
"""Nur eine typeFREE-Instanz darf laufen.

Am 29.07.2026 liefen zwei gleichzeitig: jedes Diktat kam doppelt an und
wurde doppelt bezahlt. Die geplante Aufgabenplanung würde das systematisch
erzeugen, weil sie regelmäßig prüft und neu startet.
"""
import typefree


def test_freie_sperre_laesst_starten():
    assert typefree.zweitstart_verhalten(
        schon_da=False, autostart=False) == 'weiter'


def test_freie_sperre_laesst_auch_den_autostart_durch():
    assert typefree.zweitstart_verhalten(
        schon_da=False, autostart=True) == 'weiter'


def test_belegte_sperre_meldet_sich_beim_handstart():
    """Von Hand gestartet willst du wissen, warum nichts passiert."""
    assert typefree.zweitstart_verhalten(
        schon_da=True, autostart=False) == 'melden_und_beenden'


def test_belegte_sperre_schweigt_beim_autostart():
    """Die Aufgabenplanung prüft alle paar Minuten — sonst stapeln sich Fenster."""
    assert typefree.zweitstart_verhalten(
        schon_da=True, autostart=True) == 'still_beenden'


def test_autostart_schalter_wird_erkannt():
    assert typefree.ist_autostart(['typefree.py', '--autostart']) is True
    assert typefree.ist_autostart(['typefree.py']) is False


def test_unbekannte_schalter_gelten_nicht_als_autostart():
    assert typefree.ist_autostart(['typefree.py', '--irgendwas']) is False
```

- [ ] **Schritt 2: Prüfen, dass die Tests scheitern**

```bash
python -m pytest windows/tests/test_einzelinstanz.py -v
```

Erwartet: **6 failed** — `module 'typefree' has no attribute 'zweitstart_verhalten'`

- [ ] **Schritt 3: Die Funktionen schreiben**

Vor dem Abschnitt `# ── Hauptprogramm ──` einfügen:

```python
# ── Nur eine Instanz ──────────────────────────────────────────────────────────
# Ein benannter Mutex, kein Sperrdatei-Ansatz: Windows gibt ihn beim
# Prozessende IMMER frei, auch nach einem Absturz oder Abschuss im
# Task-Manager. Eine liegengebliebene Sperrdatei wäre schlimmer als keine —
# dann startet typeFREE nie wieder, weil es sich für schon laufend hält.
#
# `Local\` statt `Global\`: Die Sperre gilt je Windows-Sitzung. Ein zweiter
# Benutzer darf sein eigenes typeFREE starten, und `Global\` bräuchte erhöhte
# Rechte.
MUTEX_NAME = r'Local\typeFREE_einzelinstanz'
_ERROR_ALREADY_EXISTS = 183
_mutex_handle = None          # festhalten, damit Python ihn nicht aufräumt


def ist_autostart(argumente):
    """Wurde mit `--autostart` gestartet? (Aufgabenplanung, Slice 2c)"""
    return '--autostart' in argumente[1:]


def zweitstart_verhalten(schon_da, autostart):
    """Reine Entscheidung: 'weiter', 'melden_und_beenden' oder 'still_beenden'.

    Beim Autostart wird geschwiegen: Die Aufgabenplanung prüft alle paar
    Minuten, und Meldungsfenster würden sich stapeln.
    """
    if not schon_da:
        return 'weiter'
    return 'still_beenden' if autostart else 'melden_und_beenden'


def sperre_belegen(name=MUTEX_NAME):
    """Nimmt den Mutex. Gibt zurück, ob schon eine Instanz läuft.

    Der Handle wird bewusst nicht geschlossen — Windows gibt ihn beim
    Prozessende frei. Das ist der ganze Vorteil gegenüber einer Sperrdatei.
    """
    global _mutex_handle
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    # restype setzen: Ein Handle ist auf 64-Bit-Windows 64 Bit breit. Ohne
    # diese Zeile schneidet ctypes den Rückgabewert auf int ab. Für uns
    # unschädlich (wir schließen ihn nie), aber falsch — und der nächste
    # Leser soll nicht rätseln.
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    _mutex_handle = kernel32.CreateMutexW(None, False, name)
    return ctypes.get_last_error() == _ERROR_ALREADY_EXISTS


def _meldung_zeigen(titel, text):
    """Windows-Meldungsfenster ohne Tray-Icon. 0x40 = Info-Symbol."""
    ctypes.windll.user32.MessageBoxW(0, text, titel, 0x40)
```

`import ctypes` gehört zu den übrigen Importen an den Dateianfang, nicht in die Funktionen — der Rest der Datei hält es genauso.

- [ ] **Schritt 4: Prüfen, dass die Tests laufen**

```bash
python -m pytest windows/tests/test_einzelinstanz.py -v
```

Erwartet: **6 passed**

---

## Aufgabe 2: In `main()` verdrahten

Die Sperre muss **vor allem anderen** greifen — vor Tastatur-Hook, Tray-Icon und Logging. Eine zweite Instanz darf nicht einmal kurz einen Hook einhängen.

**Dateien:**
- Ändern: `windows/typefree.py` — `main()`

- [ ] **Schritt 1: `main()` umbauen**

Am Anfang von `main()`, direkt nach `load_env_file()` und `setup_logging()` — das Protokoll wird gebraucht, um den Zweitstart festzuhalten:

```python
def main():
    global active_hotkey, client, openai_client, verbrauch

    load_env_file()
    setup_logging()

    autostart = ist_autostart(sys.argv)
    verhalten = zweitstart_verhalten(sperre_belegen(), autostart)
    if verhalten != 'weiter':
        log.warning('typeFREE läuft bereits — dieser Start wird beendet '
                    '(%s)', verhalten)
        if verhalten == 'melden_und_beenden':
            _meldung_zeigen(
                'typeFREE läuft bereits',
                'Es läuft schon ein typeFREE. Ein zweites würde jedes Diktat '
                'doppelt einfügen und doppelt kosten.\n\n'
                'Das laufende findest du als Mikrofon-Symbol in der '
                'Taskleiste.')
        return

    active_hotkey = load_hotkey_config()
    ...
```

- [ ] **Schritt 2: Alle Tests laufen lassen**

```bash
python -m pytest windows/tests -v
```

Erwartet: **73 passed** (67 vorhandene + 6 neue)

- [ ] **Schritt 3: Von Hand prüfen — der eigentliche Beweis**

> [!IMPORTANT]
> **Vorher die laufende Instanz beenden.** Beim Schreiben dieses Plans lief typeFREE (PID 15548, gestartet 13:00:22). Sie kennt die Sperre noch nicht und würde die Prüfung verfälschen: Der „erste" Start wäre in Wahrheit schon der zweite. Tray-Menü → Beenden.

Erste Instanz starten:

```bash
python windows/typefree.py
```

Erwartet: Tray-Icon erscheint, Protokoll zeigt „typeFREE gestartet".

**Zweite Instanz in einem zweiten Terminal starten** — derselbe Befehl.

Erwartet: **Meldungsfenster** „typeFREE läuft bereits", danach beendet sich der zweite Prozess von selbst. Im Protokoll steht eine Warnung. **Nur ein** Mikrofon-Symbol in der Taskleiste.

- [ ] **Schritt 4: Die Autostart-Ausnahme prüfen**

```bash
python windows/typefree.py --autostart
```

Erwartet: **kein** Fenster, nur eine Zeile im Protokoll, Prozess endet sofort.

- [ ] **Schritt 5: Freigabe nach Absturz prüfen**

Das ist der Punkt, an dem eine Sperrdatei versagen würde. Erste Instanz über den **Task-Manager abschießen** (nicht über das Tray-Menü), dann neu starten.

Erwartet: Der Neustart läuft **normal durch** — kein Meldungsfenster, keine verwaiste Sperre.

---

## Handprüfung für Phase 5

- [ ] Zwei Handstarts → nur eine Instanz, Meldungsfenster beim zweiten
- [ ] Start mit `--autostart` bei laufender Instanz → stumm, nur Protokoll
- [ ] Instanz im Task-Manager abschießen, neu starten → läuft normal an
- [ ] Ein Diktat kommt **einmal** an, nicht doppelt
- [ ] 73 Prüfungen grün

## Danach

`/critic`-Gegenprobe über `node .claude/skills/critic/pruefe.mjs` — sie deckt zugleich die noch offene Gegenprobe aus Phase 7 von Durchgang 1 mit ab.

Dann Slice **2b**: EXE bauen, Programmordner unter `%LOCALAPPDATA%`, `einrichten.cmd`. Erst danach 2c mit der Aufgabenplanung — sie ist der einzige Teil, der Windows-Systemeinstellungen anfasst.

---

*Erstellt mit dem Skill `writing-plans`. Nach Abschluss von Phase 8 löschen.*
