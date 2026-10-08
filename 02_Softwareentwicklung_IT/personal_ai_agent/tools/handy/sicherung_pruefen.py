r"""Termux-Sicherung am PC pruefen, bevor am Handy deinstalliert wird. (08.10.2026)

Gegenstelle zu ``termux/sicherung.sh``. Geprueft wird je Teil (``home``,
``distro_<name>`` fuer jede Linux-Umgebung):

1. ``FERTIG`` ist da (sonst brach die Sicherung ab),
2. Groesse und sha256 stimmen mit ``MANIFEST.txt`` ueberein (Kopie heil),
3. der Teil laesst sich mit dem **privaten** Schluessel entschluesseln, und das
   tar-Archiv darin ist bis zum Ende lesbar,
4. die Zahl der Eintraege im Archiv ist dieselbe, die das Handy beim Sichern
   gezaehlt hat (``eintraege=-1``: vom Handy nicht gezaehlt, z. B. bei
   ``proot-distro backup`` - dann gilt nur 3.).

Entpackt wird nichts: Das Archiv wird nur im Speicher durchgelesen. Die Ausgabe
zeigt nur Zahlen, keine Dateinamen.

Vorher einmal: ``winget install FiloSottile.age`` und das Schluesselpaar mit
``age-keygen -o "$HOME\.age\termux-sicherung.key"`` erzeugen. Der private Schluessel
kommt zusaetzlich in Bitwarden, der oeffentliche (Zeile ``# public key: age1...``)
aufs Handy.

Aufruf (PowerShell, aus ``personal_ai_agent``)::

    & .\backend\.venv\Scripts\python.exe tools\handy\sicherung_pruefen.py "$HOME\termux-sicherung\<stand>"

Exit: 0 alles gruen · 1 Ordner/Schluessel/age fehlt · 3 mindestens ein Teil fehlerhaft
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tarfile

STANDARD_SCHLUESSEL = os.path.join(os.path.expanduser("~"), ".age", "termux-sicherung.key")
BLOCK = 1024 * 1024


def manifest_lesen(pfad: str) -> dict:
    """``MANIFEST.txt`` -> ``{teil: {"groesse", "eintraege", "sha256"}}``."""
    teile = {}
    with open(pfad, encoding="utf-8") as datei:
        for zeile in datei:
            stuecke = zeile.split()
            if not stuecke or not stuecke[0].endswith(".tar.age"):
                continue
            werte = dict(s.split("=", 1) for s in stuecke[1:] if "=" in s)
            teile[stuecke[0]] = {"groesse": int(werte.get("groesse", -1)),
                                 "eintraege": int(werte.get("eintraege", -1)),
                                 "sha256": werte.get("sha256", "")}
    return teile


def sha256_datei(pfad: str) -> str:
    summe = hashlib.sha256()
    with open(pfad, "rb") as datei:
        for stueck in iter(lambda: datei.read(BLOCK), b""):
            summe.update(stueck)
    return summe.hexdigest()


def eintraege_zaehlen(strom) -> int:
    """tar-Strom bis zum Ende lesen (nichts entpacken) und die Eintraege zaehlen.
    ``r|*``: auch gzip/bz2/xz (``proot-distro backup`` kann komprimieren)."""
    anzahl = 0
    with tarfile.open(fileobj=strom, mode="r|*") as archiv:
        for _ in archiv:
            anzahl += 1
    return anzahl


def age_entschluesseler(age: str, schluessel: str):
    """Echter Entschluesseler: ``age -d -i <schluessel> <datei>`` als Strom."""
    def oeffnen(pfad: str):
        prozess = subprocess.Popen([age, "-d", "-i", schluessel, pfad],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        class Strom:
            def read(self, n=-1):
                assert prozess.stdout is not None
                return prozess.stdout.read(n)

            def close(self):
                assert prozess.stdout is not None
                prozess.stdout.close()
                if prozess.wait() != 0:
                    raise RuntimeError("age konnte nicht entschluesseln (falscher Schluessel?)")
        return Strom()
    return oeffnen


def teil_pruefen(ordner: str, name: str, soll: dict, oeffnen) -> list:
    """Fehlerliste fuer einen Teil (leer = gruen)."""
    pfad = os.path.join(ordner, name)
    if not os.path.isfile(pfad):
        return ["Datei fehlt"]
    fehler = []
    groesse = os.path.getsize(pfad)
    if groesse != soll["groesse"]:
        fehler.append(f"Groesse {groesse} statt {soll['groesse']}")
    if sha256_datei(pfad) != soll["sha256"]:
        fehler.append("sha256 weicht ab (Kopie beschaedigt)")
    if fehler:
        return fehler
    strom = oeffnen(pfad)
    try:
        anzahl = eintraege_zaehlen(strom)
    except Exception as problem:  # kaputtes Archiv oder falscher Schluessel
        return [f"nicht lesbar ({problem.__class__.__name__}: {problem})"]
    finally:
        try:
            strom.close()
        except Exception as problem:
            fehler.append(str(problem))
    if soll["eintraege"] >= 0 and anzahl != soll["eintraege"]:
        fehler.append(f"{anzahl} Eintraege statt {soll['eintraege']}")
    return fehler


def pruefen(ordner: str, oeffnen) -> tuple:
    """``(zeilen, gruen)`` fuer den ganzen Sicherungsordner."""
    zeilen = []
    if not os.path.isfile(os.path.join(ordner, "FERTIG")):
        return ["FERTIG fehlt: Die Sicherung am Handy ist nicht bis zum Ende gelaufen."], False
    soll_alle = manifest_lesen(os.path.join(ordner, "MANIFEST.txt"))
    if not soll_alle:
        return ["MANIFEST.txt enthaelt keine Teile."], False
    gruen = True
    for name, soll in sorted(soll_alle.items()):
        fehler = teil_pruefen(ordner, name, soll, oeffnen)
        mb = max(soll["groesse"], 0) // (1024 * 1024)
        if fehler:
            gruen = False
            zeilen.append(f"✗ {name}: " + "; ".join(fehler))
        else:
            zahl = f"{soll['eintraege']} Eintraege, " if soll["eintraege"] >= 0 else ""
            zeilen.append(f"✔ {name}: {zahl}{mb} MB, sha256 ok, entschluesselt, bis zum Ende lesbar")
    zeilen.append("GRUEN: Sicherung vollstaendig und lesbar." if gruen
                  else "ROT: Nicht deinstallieren. Sicherung wiederholen.")
    return zeilen, gruen


def main(argv=None, oeffnen=None) -> int:
    zerleger = argparse.ArgumentParser(description="Termux-Sicherung pruefen (nur lesen).")
    zerleger.add_argument("ordner")
    zerleger.add_argument("--schluessel", default=STANDARD_SCHLUESSEL)
    zerleger.add_argument("--age", default=shutil.which("age") or "age")
    args = zerleger.parse_args(argv)
    if not os.path.isdir(args.ordner):
        print(f"Abbruch: Ordner nicht gefunden: {args.ordner}")
        return 1
    if oeffnen is None:
        if not os.path.isfile(args.schluessel):
            print(f"Abbruch: privater Schluessel fehlt: {args.schluessel}")
            return 1
        if not shutil.which(args.age) and not os.path.isfile(args.age):
            print("Abbruch: age fehlt. Einmal: winget install FiloSottile.age")
            return 1
        oeffnen = age_entschluesseler(args.age, args.schluessel)
    zeilen, gruen = pruefen(args.ordner, oeffnen)
    for zeile in zeilen:
        print(zeile)
    return 0 if gruen else 3


if __name__ == "__main__":
    sys.exit(main())
