"""Gruppen-Dateien per Kabel aufs Handy legen (01.10.2026, Plan Foto-Gedaechtnis Schritt 2).

Gegenstueck zu ``uebergabe_uebernehmen.py`` am Handy: der PC legt die zwei
Dateien, die das Quiz „Personen benennen" braucht, in den freigegebenen
Download-Ordner; die App uebernimmt sie beim naechsten Start nach
``~/foto_sortierung`` (agent-ensure.sh bzw. start-termux.sh, sha256 hart).

  personen_gruppen/personen_beispiele.json   (Gruppen, Beispiel-Gesichter)
  personen_gruppen/gesicht_zuordnung.jsonl   (welches Gesicht in welcher Gruppe)

Beide enthalten KEINE Gesichtsvektoren (nur Kennungen, Rahmen, Datum) —
Entscheidung Sebastian 30.09.2026: diese Daten duerfen aufs Handy.

Sicherheit: nur ``adb push`` (anlegen/ersetzen im Download-Ordner) und
``adb shell stat`` (Groesse pruefen). Nichts wird geloescht, nichts gelesen
ausser Groesse und Name. Ohne ``--senden`` wird nur gezeigt, was geschaehe.

Aufruf:
    python tools/handy/gruppen_aufs_handy.py --senden
Exit 0 = gesendet (oder Trockenlauf), 1 = Uebertragung fehlgeschlagen,
2 = Datei fehlt / kein Geraet / Aufruffehler.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from typing import Callable, List, Tuple

STANDARD_BASIS = os.path.join(os.path.expanduser("~"), "foto_sortierung", "personen_gruppen")
STANDARD_ZIEL = "/sdcard/Download"
DATEIEN = ("personen_beispiele.json", "gesicht_zuordnung.jsonl")

Ausfuehren = Callable[[List[str]], Tuple[int, str]]


def _ausfuehren(befehl: List[str]) -> Tuple[int, str]:
    try:
        lauf = subprocess.run(befehl, capture_output=True, text=True, timeout=600)
    except (OSError, subprocess.TimeoutExpired) as problem:
        return 127, problem.__class__.__name__
    return lauf.returncode, (lauf.stdout or "") + (lauf.stderr or "")


def geraet_da(ausfuehren: Ausfuehren, adb: str = "adb") -> bool:
    code, aus = ausfuehren([adb, "devices"])
    if code != 0:
        return False
    zeilen = [z.split() for z in aus.splitlines()[1:] if z.strip()]
    return any(len(z) >= 2 and z[1] == "device" for z in zeilen)


def senden(basis: str, ziel: str, ausfuehren: Ausfuehren = _ausfuehren, adb: str = "adb",
           wirklich: bool = False) -> Tuple[int, List[str]]:
    zeilen: List[str] = []
    fehlend = [n for n in DATEIEN if not os.path.isfile(os.path.join(basis, n))]
    if fehlend:
        zeilen.append("Fehlt am PC: " + ", ".join(fehlend) +
                      " - zuerst tools/foto_sortierung/personen_gruppieren.py --schreiben")
        return 2, zeilen
    if not wirklich:
        for n in DATEIEN:
            zeilen.append(f"wuerde senden: {n} ({os.path.getsize(os.path.join(basis, n)):,} Bytes)"
                          .replace(",", "."))
        zeilen.append("Trockenlauf - mit --senden wirklich uebertragen.")
        return 0, zeilen
    if not geraet_da(ausfuehren, adb):
        zeilen.append("Kein Handy am Kabel (adb devices) - USB-Debugging an? Kabel steckt?")
        return 2, zeilen
    fehler = 0
    for n in DATEIEN:
        quelle = os.path.join(basis, n)
        groesse = os.path.getsize(quelle)
        code, _ = ausfuehren([adb, "push", quelle, f"{ziel}/{n}"])
        c2, aus = ausfuehren([adb, "shell", "stat", "-c", "%s", f"{ziel}/{n}"])
        angekommen = aus.strip() if c2 == 0 else ""
        if code == 0 and angekommen == str(groesse):
            zeilen.append(f"gesendet: {n} ({groesse:,} Bytes, Groesse am Handy gleich)".replace(",", "."))
        else:
            fehler += 1
            zeilen.append(f"FEHLER: {n} - push {code}, Groesse am Handy {angekommen or '?'} statt {groesse}")
    if fehler:
        return 1, zeilen
    zeilen.append("Fertig. Am Handy einmal das Termux-Widget 'agent' antippen (oder Termux "
                  "beenden und Hey Agent oeffnen) - dann uebernimmt die App die Dateien.")
    return 0, zeilen


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Gruppen-Dateien per Kabel aufs Handy legen.")
    parser.add_argument("--basis", default=STANDARD_BASIS)
    parser.add_argument("--ziel", default=STANDARD_ZIEL)
    parser.add_argument("--adb", default="adb")
    parser.add_argument("--senden", action="store_true", help="wirklich uebertragen")
    args = parser.parse_args(argv)
    if not args.ziel.startswith("/sdcard/"):
        print("Ziel muss im freigegebenen Speicher liegen (/sdcard/...).")
        return 2
    code, zeilen = senden(args.basis, args.ziel, adb=args.adb, wirklich=args.senden)
    print("\n".join(zeilen))
    return code


if __name__ == "__main__":
    sys.exit(main())
