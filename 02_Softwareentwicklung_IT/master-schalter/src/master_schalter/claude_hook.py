"""Claude-Empfang per Hook (P3a, v0.5.0): `python -m master_schalter.claude_hook`.

Claude Code ruft das Modul als Command-Hook auf und gibt das Ereignis als JSON auf stdin (höchstens 1 MB
werden gelesen; ausgewertet werden nur `hook_event_name`, `session_id` und `stop_hook_active`, nichts sonst – auch
`cwd` nicht).

* `UserPromptSubmit`, `PostToolUse`: Status `arbeitet` melden (`status.py`, gedrosselt), dann die Nachrichten
  der Sitzung abholen – erst die Wechselnachrichten des Postfachs, danach die Aufträge (`auftraege.py`). Liegen
  zuzustellende Nachrichten vor, steht auf stdout genau ein JSON
  `{"hookSpecificOutput": {"hookEventName": <Ereignis>, "additionalContext": <Text>}}`; der Text ist die feste
  Einleitung plus die festen Texte, je Zeile einer. Ohne Nachricht gibt es **keine** Ausgabe.
* `Stop`: Status `ruht`. Wechselnachrichten des Postfachs werden bei `Stop` nie zugestellt. Ausnahme (v0.5.1): Liegt
  ein **Auftrag** vor und ist `stop_hook_active` nicht `true`, steht auf stdout `{"decision": "block", "reason":
  <Text>}` – Claude arbeitet dann sofort am Auftrag weiter, statt bis zur nächsten Nutzernachricht zu ruhen; der
  Status bleibt `arbeitet`. `stop_hook_active` verhindert eine Schleife.
* Alle anderen Ereignisse: nichts tun.

Ausgabe vor Zustellung: Der Hook ruft `postfach.vormerken` auf (prüft, verschiebt nichts), schreibt und leert die
Ausgabe und ruft **erst danach** `postfach.bestaetigen` auf (Datei nach `erledigt/`, Vorgang vermerken). Scheitert
die Ausgabe oder stürzt der Hook dazwischen ab, bleibt die Nachricht liegen und kommt beim nächsten Ereignis noch
einmal – lieber doppelt als verloren; gültig bleibt sie nur über die Quittung (G5). Wird sie zwischen Ausgabe
und Bestätigung ungültig (Master gewechselt), steht sie im Chat, `bestaetigen` verwirft sie aber und setzt den
Vorgang nicht auf `im_chat`; die Quittung scheitert dann, und der Text sagt „beginne keinen Schritt“.

Robustheit (K3): jeder Fehler (kaputtes JSON, fehlende oder unzulässige Sitzungskennung nach dem Muster aus G6,
belegte Sperre, `OSError`, Importfehler, jede andere Ausnahme) endet mit Rückgabewert 0 ohne Ausgabe – der Hook
darf den Chat nie blockieren. Das Prozessende (`python -m`) ist hart (`os._exit(0)`), damit ein geschlossenes stdout nicht beim Interpreter-Ende Meldung und Exit 120 erzeugt. Auf Modulebene wird nur die Standardbibliothek importiert; alle Pakete-Module
(`modi`, `status`, `postfach`) werden innerhalb des Fehlerschutzes geladen. Auf stderr wird nichts geschrieben.
Schneller Pfad: Existiert der Postfachordner der Sitzung nicht, wird nichts weiter gelesen.

Laufzeit-Obergrenze: Sperren werden nur kurz abgewartet (`SPERRFRIST`, 0,3 s) und das Vormerken hat ein
Zeitbudget (`VORMERK_BUDGET`, 0,6 s) sowie das Bestätigen ein eigenes (`BESTAETIGEN_BUDGET`, 0,4 s). Ist eine
Sperre belegt oder das Budget erreicht, bleiben Dateien liegen und kommen beim nächsten Ereignis.

Die Kennung der Sitzung steht nie in der Ausgabe; die Postfachtexte enthalten nur Thema, Vorgangs-ID und den
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
EREIGNISSE = ("UserPromptSubmit", "PostToolUse", "Stop")
EINLEITUNG = "Nachricht des Master-Schalters:"
WERKZEUG = "claude"
SPERRFRIST = 0.3                 # Sekunden je Sperre (Themensperre, Dateisperre)
VORMERK_BUDGET = 0.6             # Sekunden für das Vormerken (danach keine weitere Datei)
BESTAETIGEN_BUDGET = 0.4         # Sekunden für das Bestätigen nach der Ausgabe


def _lesen(eingabe: bytes) -> tuple[str, str] | None:
    """`(Ereignis, Sitzungskennung)` aus dem Hook-JSON; `None`, wenn etwas fehlt oder unzulässig ist."""
    gelesen = _lesen_voll(eingabe)
    return (gelesen[0], gelesen[1]) if gelesen else None


def _lesen_voll(eingabe: bytes) -> tuple[str, str, bool] | None:
    """`(Ereignis, Sitzungskennung, stop_hook_active)`; nur ein echtes `true` zählt als aktiv."""
    from . import modi

    if len(eingabe) > MAX_EINGABE:
        return None
    roh = json.loads(eingabe.decode("utf-8"))
    if not isinstance(roh, dict):
        return None
    ereignis, kennung = roh.get("hook_event_name"), roh.get("session_id")
    if ereignis not in EREIGNISSE or not isinstance(kennung, str) \
            or modi.VORGANG_ID_MUSTER.fullmatch(kennung) is None:
        return None
    return ereignis, kennung, roh.get("stop_hook_active") is True


def _ausgeben(text: str) -> None:
    sys.stdout.write(text)         # reines ASCII (json.dumps escaped), unabhängig von der Konsolenkodierung
    sys.stdout.flush()


def verarbeiten(eingabe: bytes, jetzt: datetime | None = None,
                ausgabe: Callable[[str], None] | None = None) -> None:
    """Ereignis verarbeiten; `ausgabe(text)` (Standard: stdout) bekommt höchstens ein JSON. Wirft nie."""
    try:
        gelesen = _lesen_voll(eingabe)
        if gelesen is None:
            return
        ereignis, kennung, stop_aktiv = gelesen
        if ereignis == "Stop":
            weiter = not stop_aktiv and _auftrag_bei_stop(kennung, ausgabe or _ausgeben)
            from . import status
            status.schreiben(WERKZEUG, kennung, status.ARBEITET if weiter else status.RUHT, ereignis, jetzt)
            return
        try:
            from . import status
            status.schreiben(WERKZEUG, kennung, status.ARBEITET, ereignis, jetzt)
        except Exception:         # ein Statusfehler darf die Zustellung nicht verhindern
            pass
        _empfangen(ereignis, kennung, ausgabe or _ausgeben)
    except Exception:             # K3: nie den Chat blockieren, nichts ausgeben
        return


def _empfangen(ereignis: str, kennung: str, ausgabe: Callable[[str], None]) -> None:
    vorgemerkt = _postfach_vormerken(kennung)
    auftraege_vorgemerkt = _auftraege_vormerken(kennung)
    if not vorgemerkt and not auftraege_vorgemerkt:
        return
    kontext = "\n".join([EINLEITUNG, *(v.nachricht.text for v in vorgemerkt),
                         *(a.text for a in auftraege_vorgemerkt)])
    ausgabe(json.dumps({"hookSpecificOutput": {"hookEventName": ereignis, "additionalContext": kontext}}))
    # Erst nach erfolgreicher Ausgabe zustellen (Datei verschieben, Vorgang vermerken).
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
    except Exception:
        return []


def _auftrag_bei_stop(kennung: str, ausgabe: Callable[[str], None]) -> bool:
    """Liegt ein Auftrag vor: `decision: block` ausgeben, dann zustellen; `True` = Claude arbeitet weiter."""
    vorgemerkt = _auftraege_vormerken(kennung)
    if not vorgemerkt:
        return False
    kontext = "\n".join([EINLEITUNG, *(a.text for a in vorgemerkt)])
    ausgabe(json.dumps({"decision": "block", "reason": kontext}))
    from . import auftraege
    auftraege.bestaetigen(vorgemerkt)
    return True


def main(eingabe: bytes | None = None) -> int:
    """Einstieg für `python -m`; Rückgabewert immer 0."""
    try:
        if eingabe is None:
            eingabe = sys.stdin.buffer.read(MAX_EINGABE + 1)
        verarbeiten(eingabe)
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
