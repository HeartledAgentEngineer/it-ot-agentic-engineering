"""Tor mit Sperre: fuehrt den Pruefbefehl aus, aber nur einer zur Zeit.

Warum: mehrere Agenten (Hermes, Claude Code, Nachtlauf) teilen sich einen
Arbeitsbaum. Laufen zwei Test-Serien gleichzeitig, schreiben Tests
Laufzeitdateien neu (z. B. auftraege.json ueber .tmp) und die Dateibaum-Pruefungen
schlagen fehl - das Tor wird rot, obwohl der Code in Ordnung ist.

Verhalten:
  1. Sperre holen (.git/tor.lock, atomar via O_CREAT|O_EXCL)
  2. laeuft schon eine Sperre: warten (Standard 900 s), dann aufgeben
  3. tote Sperre (Prozess weg oder zu alt): aufraeumen und uebernehmen
  4. Pruefbefehl ausfuehren, Ausgabe durchreichen, Sperre immer freigeben
  5. Exit-Code = Exit-Code des Pruefbefehls

Aufruf:  python tools/gate/tor.py [--wartezeit 900]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HIER = Path(__file__).resolve().parent
REPO = HIER.parents[1]                      # .../personal_ai_agent
BACKEND = REPO / "backend"
PYTHON = BACKEND / ".venv" / "Scripts" / "python.exe"
SPERRE = REPO.parents[1] / ".git" / "tor.lock"   # Workspace-Wurzel/.git/tor.lock
TOT_NACH = 3600                              # aeltere Sperre gilt als tot


def _lebt(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def sperre_holen(wartezeit: int) -> bool:
    ende = time.time() + wartezeit
    while True:
        try:
            fd = os.open(SPERRE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            inhalt = {}
            try:
                inhalt = json.loads(SPERRE.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass
            pid = int(inhalt.get("pid") or 0)
            alter = time.time() - float(inhalt.get("zeit") or 0)
            if not _lebt(pid) or alter > TOT_NACH:
                print(f"[Tor] tote Sperre von PID {pid} ({alter:.0f} s alt) - uebernehmen", flush=True)
                try:
                    SPERRE.unlink()
                except OSError:
                    pass
                continue
            if time.time() >= ende:
                print(f"[Tor] Zeit abgelaufen: PID {pid} testet seit {alter:.0f} s", flush=True)
                return False
            print(f"[Tor] warte auf laufendes Tor (PID {pid}, {alter:.0f} s)", flush=True)
            time.sleep(10)
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({"pid": os.getpid(), "zeit": time.time(),
                       "rechner": os.environ.get("COMPUTERNAME", ""),
                       "wer": os.environ.get("TOR_WER", "")}, fh)
        return True


def sperre_freigeben() -> None:
    try:
        daten = json.loads(SPERRE.read_text(encoding="utf-8"))
        if int(daten.get("pid") or 0) == os.getpid():
            SPERRE.unlink()
    except (OSError, json.JSONDecodeError):
        pass


def pruefen() -> int:
    befehl = [str(PYTHON), "-m", "pytest", "tests/", "-q"]
    print(f"[Tor] fuehre aus: {' '.join(befehl)} (in {BACKEND})", flush=True)
    ergebnis = subprocess.run(befehl, cwd=str(BACKEND))
    return ergebnis.returncode


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--wartezeit", type=int, default=900)
    ap.add_argument("--auch-ohne-sperre", action="store_true",
                    help="nur ausfuehren, nicht sperren (Notfall)")
    a = ap.parse_args(argv)
    if not PYTHON.exists():
        print(f"[Tor] Pruefbefehl nicht gefunden: {PYTHON}")
        return 2
    if a.auch_ohne_sperre:
        return pruefen()
    if not sperre_holen(a.wartezeit):
        return 2
    try:
        return pruefen()
    finally:
        sperre_freigeben()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())