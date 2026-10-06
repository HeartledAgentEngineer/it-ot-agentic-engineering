"""Vorlese-Schluessel (OPENROUTER_TTS_KEY) vom PC aufs Handy legen (06.10.2026).

Warum:
  Fuers Vorlesen gibt es einen eigenen OpenRouter-Schluessel — OpenRouter weist
  die Kosten je Schluessel aus, so ist sichtbar, was das Vorlesen kostet. Hermes
  hat ihn in seiner Konfiguration (``%LOCALAPPDATA%\\hermes\\.env``, Variable
  ``OPENROUTER_TTS_KEY``); der Agent am Handy braucht ihn in ``backend/.env``.
  Ueber Git darf er nicht wandern (das Repo ist oeffentlich), und in den
  Termux-Heimordner kommt man per Kabel nicht. Deshalb derselbe Weg wie beim
  pCloud-Zugang: dieses Werkzeug legt ``vorlese_schluessel.txt`` in den
  Download-Ordner des Handys, beim naechsten App-Start uebernimmt
  ``termux/schluessel-uebernehmen.sh`` ihn in die .env und loescht die Datei.

Regeln:
  * Der Wert wird NIE ausgegeben — weder auf der Konsole noch in einer Datei
    ausser der einen Uebergabedatei. Gemeldet werden nur Zustaende.
  * Gelesen wird aus der Quelle genau EIN Variablenname.
  * Die lokale Zwischendatei liegt im Temp-Ordner und wird in jedem Fall
    wieder entfernt (auch bei Fehlern).
  * Trockenlauf ist Standard: ohne ``--senden`` wird nur geprueft.
  * Kein Netz ausser dem lokalen ``adb``.

Aufruf (aus dem Projektordner)::

    backend/.venv/Scripts/python.exe tools/handy/vorlese_schluessel_senden.py
    backend/.venv/Scripts/python.exe tools/handy/vorlese_schluessel_senden.py --senden --neustart

``--neustart`` startet Termux ueber die App neu und wartet, bis die
Uebergabedatei verschwunden ist (= uebernommen).

Exit: 0 ok, 1 Uebertragung/Uebernahme fehlgeschlagen, 2 Aufruf/Schutz
(Quelle fehlt, Variable fehlt, Wert unplausibel).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import time
from typing import Callable, List, Optional

NAME = "OPENROUTER_TTS_KEY"
ZIEL = "/sdcard/Download/vorlese_schluessel.txt"
WARTEN_S = 120


def standard_quelle() -> str:
    basis = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")
    return os.path.join(basis, "hermes", ".env")


def wert_lesen(pfad: str, name: str = NAME) -> str:
    """Genau eine Variable aus einer .env lesen; fehlt sie: ''. Wirft nie."""
    try:
        with open(pfad, encoding="utf-8", errors="replace") as datei:
            for zeile in datei:
                zeile = zeile.strip()
                if not zeile or zeile.startswith("#") or "=" not in zeile:
                    continue
                kennung, _, wert = zeile.partition("=")
                kennung = kennung.strip()
                if kennung.startswith("export "):
                    kennung = kennung[len("export "):].strip()
                if kennung == name:
                    return wert.strip().strip('"').strip("'")
    except OSError:
        return ""
    return ""


def plausibel(wert: str) -> bool:
    """Sieht der Wert wie ein OpenRouter-Schluessel aus? (ohne ihn zu zeigen)"""
    return wert.startswith("sk-or-") and len(wert) >= 24 and not any(z.isspace() for z in wert)


def _adb(ausfuehren: Callable, adb: str, argumente: List[str]) -> subprocess.CompletedProcess:
    return ausfuehren([adb] + argumente, capture_output=True, text=True, timeout=60)


def main(argv: Optional[List[str]] = None, ausfuehren: Callable = subprocess.run,
         schlafen: Callable[[float], None] = time.sleep) -> int:
    zerleger = argparse.ArgumentParser(description="Vorlese-Schluessel aufs Handy legen (Wert wird nie gezeigt).")
    zerleger.add_argument("--quelle", default=standard_quelle(), help="Hermes-.env (Standard: %%LOCALAPPDATA%%\\hermes\\.env)")
    zerleger.add_argument("--senden", action="store_true", help="wirklich ans Handy legen (sonst nur pruefen)")
    zerleger.add_argument("--neustart", action="store_true", help="danach Termux ueber die App neu starten und Uebernahme pruefen")
    zerleger.add_argument("--adb", default="adb")
    args = zerleger.parse_args(argv)

    if not os.path.isfile(args.quelle):
        print(f"Quelle fehlt: {args.quelle}")
        return 2
    wert = wert_lesen(args.quelle)
    if not wert:
        print(f"{NAME} steht nicht in {args.quelle}.")
        return 2
    if not plausibel(wert):
        print(f"{NAME} in {args.quelle} sieht nicht wie ein OpenRouter-Schlüssel aus (beginnt nicht mit sk-or-). Nichts gesendet.")
        return 2
    print(f"{NAME} gefunden in {args.quelle}: ja (Wert wird nicht angezeigt).")
    if not args.senden:
        print("Trockenlauf — zum Übertragen: --senden (am besten mit --neustart).")
        return 0

    griff, tmp = tempfile.mkstemp(prefix="vorlese_", suffix=".txt")
    try:
        with os.fdopen(griff, "w", encoding="utf-8", newline="\n") as datei:
            datei.write(f"{NAME}={wert}\n")
        groesse = os.path.getsize(tmp)
        lauf = _adb(ausfuehren, args.adb, ["push", tmp, ZIEL])
        if lauf.returncode != 0:
            print(f"Übertragung fehlgeschlagen (adb Exit {lauf.returncode}). Handy am Kabel und entsperrt?")
            return 1
        probe = _adb(ausfuehren, args.adb, ["shell", "stat", "-c", "%s", ZIEL])
        if probe.returncode != 0 or (probe.stdout or "").strip() != str(groesse):
            print("Übertragung nicht bestätigt (Größe am Handy weicht ab). Bitte erneut senden.")
            return 1
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    print(f"Auf dem Handy abgelegt: {ZIEL} — wird beim nächsten App-Start in backend/.env übernommen und dort gelöscht.")

    if not args.neustart:
        return 0
    _adb(ausfuehren, args.adb, ["shell", "am", "force-stop", "com.termux"])
    _adb(ausfuehren, args.adb, ["shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", "heyagent://start"])
    print("Termux über die App neu gestartet — warte auf die Übernahme …")
    for _ in range(WARTEN_S // 5):
        schlafen(5)
        noch_da = _adb(ausfuehren, args.adb, ["shell", "ls", ZIEL])
        if noch_da.returncode != 0:
            print("Übernommen: die Übergabedatei ist weg (Termux hat sie in backend/.env eingetragen und gelöscht).")
            return 0
    print(f"Nach {WARTEN_S} s liegt die Übergabedatei noch da — App einmal öffnen bzw. Termux starten, dann erneut prüfen.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
