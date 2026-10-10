r"""Termux-Sicherung vom PC aus beauftragen, mitlesen, holen, pruefen. (08.10.2026)

Wunsch Sebastian: am Handy nichts tippen. Ablauf mit EINEM Befehl am PC:

1. Kabel-Check: Handy da, oeffentlicher Schluessel liegt im Download-Ordner.
2. Auftrag legen: ``/sdcard/Download/termux-sicherung/AUFTRAG`` (Inhalt = Kennung).
3. Sebastian tippt am Handy das Agent-Widget. ``termux/agent-start`` ruft
   ``termux/sicherung-auftrag.sh`` auf, das den Auftrag abarbeitet.
4. Dieses Werkzeug liest ``lauf_<kennung>.log`` mit und zeigt die Zeilen (nur
   Pfade und Zahlen) bis ``EXIT=<code>``.
5. Bei Erfolg: Sicherungsordner per ``adb pull`` nach ``~/termux-sicherung/``
   holen (vorhanden = nicht erneut holen) und mit ``sicherung_pruefen.py`` pruefen.

Am Handy wird nichts geloescht; am PC wird nur in ``~/termux-sicherung/`` geschrieben.

Aufruf (PowerShell, aus ``personal_ai_agent``)::

    & .\backend\.venv\Scripts\python.exe tools\handy\sicherung_auftrag.py

Exit: 0 Sicherung geholt und GRUEN · 1 kein Handy/adb · 2 Schluessel fehlt am
Handy · 3 Sicherung am Handy gescheitert · 4 Zeit abgelaufen · 5 Pruefung ROT ·
6 ein Auftrag laeuft schon
"""
from __future__ import annotations

import argparse
import datetime
import importlib.util
import os
import re
import subprocess
import sys
import tempfile
import time

HIER = os.path.dirname(os.path.abspath(__file__))
HANDY_ORDNER = "/sdcard/Download/termux-sicherung"
HANDY_SCHLUESSEL = "/sdcard/Download/sicherung_empfaenger.txt"
STANDARD_LOKAL = os.path.join(os.path.expanduser("~"), "termux-sicherung")


def adb_echt(argumente) -> tuple:
    """``adb <argumente>`` -> ``(code, ausgabe)``; fehlt adb, Code 127."""
    try:
        lauf = subprocess.run(["adb", *argumente], capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return 127, "adb nicht gefunden"
    return lauf.returncode, (lauf.stdout or "") + (lauf.stderr or "")


def geraet_da(adb) -> bool:
    code, ausgabe = adb(["devices"])
    return code == 0 and any(z.rstrip().endswith("\tdevice") for z in ausgabe.splitlines()[1:])


def datei_da(adb, pfad: str) -> bool:
    code, ausgabe = adb(["shell", f"ls {pfad}"])
    return code == 0 and "No such file" not in ausgabe


def auftrag_legen(adb, kennung: str) -> bool:
    """Auftragsdatei aufs Handy legen. Lokale Zwischendatei nur im Temp-Ordner."""
    adb(["shell", f"mkdir -p {HANDY_ORDNER}"])
    with tempfile.TemporaryDirectory() as ordner:
        pfad = os.path.join(ordner, "AUFTRAG")
        with open(pfad, "w", encoding="utf-8", newline="\n") as datei:
            datei.write(kennung + "\n")
        code, _ = adb(["push", pfad, f"{HANDY_ORDNER}/AUFTRAG"])
    return code == 0


def mitlesen(adb, kennung: str, melden=print, schlafen=time.sleep, max_sekunden=5400,
             takt=5) -> tuple:
    """Log bis ``EXIT=<code>`` mitlesen -> ``(code, handy_ziel)``; Zeitablauf -> ``(None, ziel)``."""
    log = f"{HANDY_ORDNER}/lauf_{kennung}.log"
    gezeigt, ziel, gewartet = 0, None, 0
    while gewartet <= max_sekunden:
        code, text = adb(["shell", f"cat {log} 2>/dev/null"])
        zeilen = text.splitlines() if code == 0 else []
        for zeile in zeilen[gezeigt:]:
            melden("  | " + zeile)
            treffer = re.match(r"^Sicherung nach (\S+)", zeile)
            if treffer:
                ziel = treffer.group(1)
            ende = re.match(r"^EXIT=(\d+)", zeile)
            if ende:
                return int(ende.group(1)), ziel
        gezeigt = max(gezeigt, len(zeilen))
        schlafen(takt)
        gewartet += takt
    return None, ziel


def holen(adb, handy_ziel: str, lokal_basis: str) -> str:
    """Sicherungsordner holen; ist er lokal schon da, wird nicht erneut geholt."""
    lokal = os.path.join(lokal_basis, handy_ziel.rstrip("/").rsplit("/", 1)[-1])
    if os.path.isdir(lokal):
        return lokal
    os.makedirs(lokal_basis, exist_ok=True)
    code, ausgabe = adb(["pull", handy_ziel, lokal_basis])
    if code != 0:
        raise RuntimeError(f"adb pull scheiterte: {ausgabe.strip()[:200]}")
    return lokal


def _pruefer():
    spez = importlib.util.spec_from_file_location(
        "sicherung_pruefen", os.path.join(HIER, "sicherung_pruefen.py"))
    assert spez is not None and spez.loader is not None
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul.main


def main(argv=None, adb=adb_echt, schlafen=time.sleep, pruefen=None) -> int:
    zerleger = argparse.ArgumentParser(description="Termux-Sicherung per Widget-Start beauftragen.")
    zerleger.add_argument("--lokal", default=STANDARD_LOKAL)
    zerleger.add_argument("--max-minuten", type=int, default=90)
    zerleger.add_argument("--kennung", default=datetime.datetime.now().strftime("%Y%m%d%H%M%S"))
    zerleger.add_argument("--fortsetzen", action="store_true",
                          help="laufenden Auftrag --kennung weiter mitlesen, keinen neuen legen")
    args = zerleger.parse_args(argv)
    # Handy-Log kann Zeichen enthalten, die die Windows-Konsole (cp1252) nicht kennt
    # (Befund 10.10.2026: Absturz beim Mitlesen) -> ersetzen statt abbrechen.
    for strom in (sys.stdout, sys.stderr):
        try:
            strom.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass

    if not geraet_da(adb):
        print("Abbruch: kein Handy am Kabel (adb devices). USB-Debugging an?")
        return 1
    if not datei_da(adb, HANDY_SCHLUESSEL):
        print(f"Abbruch: oeffentlicher Schluessel fehlt am Handy ({HANDY_SCHLUESSEL}).")
        return 2
    if args.fortsetzen:
        print(f"Auftrag {args.kennung}: lese weiter mit.")
    else:
        if datei_da(adb, f"{HANDY_ORDNER}/AUFTRAG.laeuft"):
            print("Abbruch: am Handy laeuft schon eine Sicherung (AUFTRAG.laeuft).")
            print("Mitlesen: --fortsetzen --kennung <Kennung>")
            return 6
        if not auftrag_legen(adb, args.kennung):
            print("Abbruch: Auftrag liess sich nicht aufs Handy legen.")
            return 1
        print(f"Auftrag {args.kennung} liegt am Handy.")
        print(">>> Jetzt am Handy das Agent-Widget antippen. <<<")
        print("    Der Agent startet erst nach der Sicherung (einige Minuten). Mitlesen:")
    code, handy_ziel = mitlesen(adb, args.kennung, schlafen=schlafen,
                                max_sekunden=args.max_minuten * 60)
    if code is None:
        print(f"Zeit abgelaufen ({args.max_minuten} min). Wurde das Widget getippt?")
        print("Der Auftrag bleibt liegen und wird beim naechsten Widget-Start erledigt.")
        return 4
    if code != 0 or not handy_ziel:
        print(f"Sicherung am Handy gescheitert (EXIT={code}). Nicht deinstallieren.")
        return 3

    print("Sicherung fertig, wird geholt ...")
    try:
        lokal = holen(adb, handy_ziel, args.lokal)
    except RuntimeError as problem:
        print(f"Abbruch: {problem}")
        return 1
    print(f"Geholt nach {lokal}. Pruefung:")
    ergebnis = (pruefen or _pruefer())([lokal])
    return 0 if ergebnis == 0 else 5


if __name__ == "__main__":
    sys.exit(main())
