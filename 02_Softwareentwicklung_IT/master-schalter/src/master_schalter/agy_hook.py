"""Antigravity-Empfang per Hook (v0.6.0): `python -m master_schalter.agy_hook EREIGNIS`.

Antigravity (agy) ruft das Modul als Command-Hook auf und gibt das Ereignis als JSON auf stdin
(höchstens 1 MB werden gelesen). **Den Ereignisnamen liefert Antigravity nicht auf stdin** – er steht
als erstes Argument im `command` der `hooks.json`, deshalb wird er von `sys.argv[1]` gelesen und streng
gegen die bekannten Namen geprüft. Aus dem JSON werden nur `conversationId` und `invocationNum`
ausgewertet, nichts sonst – auch `workspacePaths` oder `transcriptPath` nicht.

Ereignisse (belegt in der Doku `antigravity.google/docs/hooks` und im Proto `.exa.hooks_pb` des
`language_server.exe`):

* `SessionStart`, `PreInvocation`, `PostInvocation`: Status `arbeitet` melden (`status.py`, gedrosselt),
  dann Nachrichten abholen – erst die Wechselnachrichten des Postfachs, danach die Aufträge
  (`auftraege.py`). Liegen welche vor, steht auf stdout genau ein JSON
  `{"injectSteps": [{"systemMessage": {"systemMessage": <Text>}}]}`; der Text ist die feste Einleitung
  plus die festen Texte, je Zeile einer. Ohne Nachricht gibt es **keine** Ausgabe.
* `Stop`: Status `ruht`. Liegen Nachrichten oder Aufträge vor und ist die Schleifenbremse frei, steht auf
  stdout `{"decision": "continue", "reason": <Text>}` – Antigravity arbeitet dann sofort weiter, statt
  bis zur nächsten Nutzernachricht zu ruhen; der Status bleibt `arbeitet`. Ohne Nachricht oder bei
  erschöpfter Bremse steht `{}` – dann bleibt alles liegen und kommt beim nächsten Ereignis wieder.
* Alle anderen Ereignisse: nichts tun.

Schleifenbremse (Unterschied zu Claude): Claude schützt sich über `stop_hook_active`. Antigravity kennt
kein solches Feld; `{"decision": "continue"}` setzt den Agenten **immer** wieder in Gang. Deshalb zählt
dieses Modul die Fortsetzungen je Gespräch mit (`AGY_STOP_MAX`) und setzt den Zähler bei `invocationNum == 0`
zurück – das ist der Beginn eines neuen Auftrags. Die Bremse ist die einzige Absicherung gegen eine
Endlosschleife; sie muss erhalten bleiben.

Ausgabe vor Zustellung: Der Hook ruft `postfach.vormerken` auf (prüft, verschiebt nichts), schreibt die
Ausgabe und ruft **erst danach** `postfach.bestaetigen` bzw. `auftraege.bestaetigen` auf (Datei nach
`erledigt/`, Vorgang vermerken). Scheitert die Ausgabe, bleibt die Nachricht liegen und kommt beim
nächsten Ereignis noch einmal – lieber doppelt als verloren; gültig bleibt sie nur über die Quittung (G5).

Robustheit (K3): jeder Fehler (kaputtes JSON, fehlender oder unbekannter Ereignisname, unzulässige
Sitzungskennung nach dem Muster aus G6, belegte Sperre, `OSError`, Importfehler, jede andere Ausnahme)
endet mit Rückgabewert 0 ohne Ausgabe – der Hook darf den Chat nie blockieren. Auf stderr wird nichts
geschrieben; das Prozessende (`python -m`) ist hart (`os._exit(0)`), damit ein geschlossenes stdout nicht
Exit 120 erzeugt. Auf Modulebene wird nur die Standardbibliothek importiert; alle Pakete-Module
(`modi`, `status`, `postfach`, `auftraege`) werden innerhalb des Fehlerschutzes geladen.

Laufzeit-Obergrenze: wie bei Claude (`SPERRFRIST` 0,3 s, `VORMERK_BUDGET` 0,6 s, `BESTAETIGEN_BUDGET` 0,4 s).
Die Kennung der Sitzung steht nie in der Ausgabe; die Texte enthalten nur Thema, Vorgangs-ID und den
repo-relativen Pfad der laufenden Übergabe.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from typing import Callable

MAX_EINGABE = 1_000_000          # höchstens 1 MB stdin
EREIGNISSE = ("SessionStart", "PreInvocation", "PostInvocation", "Stop")
EINLEITUNG = "Nachricht des Master-Schalters:"
WERKZEUG = "agy"
SPERRFRIST = 0.3                 # Sekunden je Sperre (Themensperre, Dateisperre)
VORMERK_BUDGET = 0.6             # Sekunden für das Vormerken (danach keine weitere Datei)
BESTAETIGEN_BUDGET = 0.4         # Sekunden für das Bestätigen nach der Ausgabe
AGY_STOP_MAX = 3                 # höchstens so viele Fortsetzungen je Gespräch (Schutz vor Endlosschleife)
BREMSE_DATEI = "agy-stop.json"
BREMSE_VERFALL = 3600            # Sekunden, nach denen ein alter Zählerstand nicht mehr zählt


# --- Eingabe --------------------------------------------------------------------

def _lesen_voll(eingabe: bytes, ereignis: str) -> tuple[str, str, int] | None:
    """`(Ereignis, Sitzungskennung, Aufrufnummer)`; `None`, wenn etwas fehlt oder unzulässig ist."""
    from . import modi

    if not isinstance(ereignis, str) or ereignis not in EREIGNISSE or len(eingabe) > MAX_EINGABE:
        return None
    roh = json.loads(eingabe.decode("utf-8"))
    if not isinstance(roh, dict):
        return None
    kennung = roh.get("conversationId")
    if not isinstance(kennung, str) or modi.VORGANG_ID_MUSTER.fullmatch(kennung) is None:
        return None
    nummer = roh.get("invocationNum")
    return ereignis, kennung, nummer if isinstance(nummer, int) and not isinstance(nummer, bool) else 0


def _ausgeben(text: str) -> None:
    sys.stdout.write(text)         # reines ASCII (json.dumps escaped), unabhängig von der Konsolenkodierung
    sys.stdout.flush()


# --- Schleifenbremse ------------------------------------------------------------

def _bremse_pfad():
    from .signale import daten_ordner

    return daten_ordner() / BREMSE_DATEI


def _bremse_lesen() -> dict:
    try:
        roh = json.loads(_bremse_pfad().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return roh if isinstance(roh, dict) else {}


def _bremse_frei(kennung: str) -> bool:
    """`True`, wenn für dieses Gespräch noch eine Fortsetzung erlaubt ist (im Zweifel: ja)."""
    try:
        eintrag = _bremse_lesen().get(kennung)
        if eintrag is None:
            return True
        stand, zeit = eintrag.get("stand"), eintrag.get("zeit")
        if not isinstance(stand, int) or isinstance(stand, bool) or not isinstance(zeit, (int, float)):
            return True
        if time.time() - zeit > BREMSE_VERFALL:
            return True
        return stand < AGY_STOP_MAX
    except Exception:                # noqa: BLE001 - die Bremse darf den Hook nie scheitern lassen
        return True


def _bremse_schreiben(kennung: str, stand: int) -> None:
    daten = _bremse_lesen()
    daten[kennung] = {"stand": stand, "zeit": time.time()}
    pfad = _bremse_pfad()
    pfad.parent.mkdir(parents=True, exist_ok=True)
    from .signale import _atomar_schreiben

    _atomar_schreiben(pfad, json.dumps(daten))


def _bremse_hoch(kennung: str) -> None:
    """Eine Fortsetzung verbuchen; ein Fehler dabei verhindert die Ausgabe nicht."""
    try:
        eintrag = _bremse_lesen().get(kennung) or {}
        stand = eintrag.get("stand")
        _bremse_schreiben(kennung, (stand if isinstance(stand, int) and not isinstance(stand, bool) else 0) + 1)
    except Exception:                # noqa: BLE001
        pass


def _bremse_zuruecksetzen(kennung: str) -> None:
    """Neuer Auftrag im Gespräch (`invocationNum == 0`): Zähler wieder auf null."""
    try:
        daten = _bremse_lesen()
        if kennung in daten:
            daten.pop(kennung)
            from .signale import _atomar_schreiben

            _atomar_schreiben(_bremse_pfad(), json.dumps(daten))
    except Exception:                # noqa: BLE001
        pass


# --- Verarbeiten -----------------------------------------------------------------

def verarbeiten(eingabe: bytes, ereignis: str, jetzt: datetime | None = None,
                ausgabe: Callable[[str], None] | None = None) -> None:
    """Ereignis verarbeiten; `ausgabe(text)` (Standard: stdout) bekommt höchstens ein JSON. Wirft nie."""
    try:
        gelesen = _lesen_voll(eingabe, ereignis)
        if gelesen is None:
            return
        ereignis, kennung, nummer = gelesen
        if ereignis == "Stop":
            schreiben = ausgabe or _ausgeben
            weiter = _weiterarbeiten(kennung, schreiben)
            if not weiter:
                schreiben("{}")           # belegt wirksame Form: kein `decision` heißt anhalten
            _status(kennung, ereignis, jetzt, "arbeitet" if weiter else "ruht")
            return
        if nummer == 0:
            _bremse_zuruecksetzen(kennung)
        _status(kennung, ereignis, jetzt, "arbeitet")
        _empfangen(kennung, ausgabe or _ausgeben)
    except Exception:             # K3: nie den Chat blockieren, nichts ausgeben
        return


def _status(kennung: str, ereignis: str, jetzt: datetime | None, stand: str) -> None:
    """Status melden; ein Statusfehler darf die Zustellung nicht verhindern."""
    try:
        from . import agy_senden, status

        agy_senden.umgebung_merken()
        status.schreiben(WERKZEUG, kennung, getattr(status, stand.upper()), ereignis, jetzt)
    except Exception:             # noqa: BLE001
        pass


def _empfangen(kennung: str, ausgabe: Callable[[str], None]) -> None:
    vorgemerkt = _postfach_vormerken(kennung)
    auftraege_vorgemerkt = _auftraege_vormerken(kennung)
    if not vorgemerkt and not auftraege_vorgemerkt:
        return
    ausgabe(json.dumps({"injectSteps": [{"systemMessage": {"systemMessage": _text(vorgemerkt, auftraege_vorgemerkt)}}]}))
    _bestaetigen(vorgemerkt, auftraege_vorgemerkt)


def _weiterarbeiten(kennung: str, ausgabe: Callable[[str], None]) -> bool:
    """Liegt etwas vor und ist die Bremse frei: `continue` ausgeben, dann zustellen; `True` = läuft weiter."""
    if not _bremse_frei(kennung):
        return False
    vorgemerkt = _postfach_vormerken(kennung)
    auftraege_vorgemerkt = _auftraege_vormerken(kennung)
    if not vorgemerkt and not auftraege_vorgemerkt:
        return False
    _bremse_hoch(kennung)                    # vor der Ausgabe: die Fortsetzung ist damit verbucht
    ausgabe(json.dumps({"decision": "continue", "reason": _text(vorgemerkt, auftraege_vorgemerkt)}))
    _bestaetigen(vorgemerkt, auftraege_vorgemerkt)
    return True


def _text(vorgemerkt: list, auftraege_vorgemerkt: list) -> str:
    return "\n".join([EINLEITUNG, *(v.nachricht.text for v in vorgemerkt),
                      *(a.text for a in auftraege_vorgemerkt)])


def _bestaetigen(vorgemerkt: list, auftraege_vorgemerkt: list) -> None:
    """Erst nach erfolgreicher Ausgabe zustellen (Datei verschieben, Vorgang vermerken)."""
    if vorgemerkt:
        from . import postfach

        postfach.bestaetigen(vorgemerkt, frist=SPERRFRIST, bis=time.monotonic() + BESTAETIGEN_BUDGET)
    if auftraege_vorgemerkt:
        from . import auftraege

        auftraege.bestaetigen(auftraege_vorgemerkt)


def _postfach_vormerken(kennung: str) -> list:
    from . import postfach        # erst nach dem schnellen Pfad laden (spart Importzeit ohne Postfach)

    if not postfach.ordner(WERKZEUG, kennung).is_dir():
        return []
    return postfach.vormerken(WERKZEUG, kennung, frist=SPERRFRIST, bis=time.monotonic() + VORMERK_BUDGET)


def _auftraege_vormerken(kennung: str) -> list:
    """Aufträge der Sitzung (`auftraege.py`); ein Fehler hier verhindert die Postfachzustellung nicht."""
    try:
        from . import auftraege

        if not auftraege.ordner(kennung).is_dir():
            return []
        return auftraege.vormerken(kennung, auftraege.basis())
    except Exception:             # noqa: BLE001
        return []


def main(argumente: list[str] | None = None, eingabe: bytes | None = None) -> int:
    """Einstieg für `python -m`; Rückgabewert immer 0. Erstes Argument ist der Ereignisname."""
    try:
        argumente = sys.argv[1:] if argumente is None else argumente
        ereignis = argumente[0] if argumente else ""
        daten = sys.stdin.buffer.read(MAX_EINGABE + 1) if eingabe is None else eingabe
        verarbeiten(daten, ereignis)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    _rueckgabe = main()
    try:
        sys.stdout.flush()
    except Exception:
        pass
    # Hartes Ende: Scheiterte `flush()` (stdout geschlossen), versucht der Interpreter beim normalen Beenden
    # erneut zu leeren – das ergäbe eine stderr-Meldung und Exit 120. `os._exit` umgeht das; der Hook endet immer mit 0.
    os._exit(_rueckgabe)
