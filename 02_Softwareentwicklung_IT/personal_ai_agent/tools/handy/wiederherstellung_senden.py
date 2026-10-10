r"""Termux-Sicherung fuer die Wiederherstellung aufs Handy schicken (10.10.2026).

Gegenstueck zu ``termux/wiederherstellen.sh``. Die Sicherung ist an Sebastians
Hauptschluessel verschluesselt; dessen privater Teil bleibt am PC. Dieses Werkzeug:

1. legt ``wiederherstellen.sh`` in ``/sdcard/Download/termux-sicherung/``,
2. liest den oeffentlichen Einmal-Schluessel, den ``wiederherstellen.sh vorbereiten``
   im neuen Termux erzeugt hat,
3. schickt jeden Teil (``home.tar.age``, ``distro_*.tar.age``) als Strom:
   ``age -d`` (Hauptschluessel) -> ``age -r`` (Einmal-Schluessel) -> ``adb exec-in``.
   Klartext gibt es nur im Arbeitsspeicher des PCs, nie auf einem Datentraeger.
4. prueft unterwegs die sha256 der Quelle gegen ``MANIFEST.txt`` und am Ende die
   sha256 der Datei auf dem Handy, schreibt ``MANIFEST.txt`` und zuletzt ``FERTIG``.

Nie ueberschreiben: Gibt es den Zielordner schon, entsteht ``..._2`` usw. Liegt
schon eine vollstaendige Sendung fuer denselben Einmal-Schluessel da, passiert nichts.

Aufruf (PowerShell, aus ``personal_ai_agent``)::

    & .\backend\.venv\Scripts\python.exe tools\handy\wiederherstellung_senden.py

Probelauf ohne Handy: ``--lokal-ziel <ordner> --empfaenger age1...``.

Exit: 0 fertig · 1 kein Handy/adb · 2 Hauptschluessel oder age fehlt ·
3 Einmal-Schluessel fehlt am Handy · 4 Sicherung fehlt/unvollstaendig ·
5 Pruefsumme falsch · 6 Uebertragung scheiterte
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import threading

HIER = os.path.dirname(os.path.abspath(__file__))
PROJEKT = os.path.dirname(os.path.dirname(HIER))
SKRIPT = os.path.join(PROJEKT, "termux", "wiederherstellen.sh")
HANDY_ABLAGE = "/sdcard/Download/termux-sicherung"
HANDY_EMPFAENGER = f"{HANDY_ABLAGE}/einmal_empfaenger.txt"
STANDARD_LOKAL = os.path.join(os.path.expanduser("~"), "termux-sicherung")
EMPFAENGER_MUSTER = re.compile(r"age1[0-9a-z]{50,}")
STUECK = 1 << 20


class TransferFehler(Exception):
    pass


def adb_echt(argumente, eingabe=None):
    try:
        e = subprocess.run(["adb", *argumente], input=eingabe, capture_output=True, timeout=600)
    except (OSError, subprocess.TimeoutExpired) as problem:
        return 1, f"adb nicht ausfuehrbar ({problem.__class__.__name__})"
    return e.returncode, (e.stdout or b"").decode("utf-8", "replace")


def standard_schluessel() -> str:
    spez = importlib.util.spec_from_file_location("sicherung_pruefen", os.path.join(HIER, "sicherung_pruefen.py"))
    assert spez is not None and spez.loader is not None
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul.STANDARD_SCHLUESSEL


def neueste_sicherung(basis: str):
    """Neuester Ordner mit ``FERTIG`` und ``MANIFEST.txt`` (Name = Stand, sortierbar)."""
    try:
        namen = sorted(os.listdir(basis), reverse=True)
    except OSError:
        return None
    for name in namen:
        ordner = os.path.join(basis, name)
        if os.path.isfile(os.path.join(ordner, "FERTIG")) and os.path.isfile(os.path.join(ordner, "MANIFEST.txt")):
            return ordner
    return None


def manifest_lesen(ordner: str) -> dict:
    """``{name: sha256}`` der verschluesselten Teile aus ``MANIFEST.txt``."""
    teile = {}
    with open(os.path.join(ordner, "MANIFEST.txt"), encoding="utf-8") as datei:
        for zeile in datei:
            name = zeile.split(" ", 1)[0]
            summe = re.search(r"sha256=([0-9a-f]{64})", zeile)
            if name.endswith(".tar.age") and summe:
                teile[name] = summe.group(1)
    return teile


def teil_senden(quelle: str, entschluesseln, verschluesseln, ziel, starten=subprocess.Popen):
    """Strom ``quelle -> entschluesseln -> verschluesseln -> ziel``.

    Gibt ``(sha256_quelle, sha256_neu, groesse_neu)`` zurueck; wirft TransferFehler,
    wenn eine Stufe scheitert.
    """
    alt, neu = hashlib.sha256(), hashlib.sha256()
    p1 = starten(entschluesseln, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    p2 = starten(verschluesseln, stdin=p1.stdout, stdout=subprocess.PIPE)
    p3 = starten(ziel, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL)
    assert p1.stdin and p1.stdout and p2.stdout and p3.stdin
    eingang, zwischen, ausgang, ablage = p1.stdin, p1.stdout, p2.stdout, p3.stdin
    zwischen.close()        # gehoert jetzt p2; so bekommt p1 ein Rohrende, wenn p2 abbricht
    fehler = []

    def fuettern():
        try:
            with open(quelle, "rb") as datei:
                while True:
                    stueck = datei.read(STUECK)
                    if not stueck:
                        break
                    alt.update(stueck)
                    eingang.write(stueck)
        except Exception as problem:            # z. B. BrokenPipe, wenn age abbricht
            fehler.append(problem.__class__.__name__)
        finally:
            try:
                eingang.close()
            except OSError:
                pass

    faden = threading.Thread(target=fuettern, daemon=True)
    faden.start()
    groesse = 0
    try:
        while True:
            stueck = ausgang.read(STUECK)
            if not stueck:
                break
            neu.update(stueck)
            groesse += len(stueck)
            ablage.write(stueck)
    except OSError as problem:
        fehler.append(problem.__class__.__name__)
    finally:
        try:
            ablage.close()
        except OSError:
            pass
    faden.join()
    codes = (p1.wait(), p2.wait(), p3.wait())
    if fehler or any(codes):
        raise TransferFehler(f"Stufen {codes}, Fehler {fehler or '-'}")
    return alt.hexdigest(), neu.hexdigest(), groesse


class HandyZiel:
    """Schreibt per ``adb exec-in`` in einen Ordner auf dem Handy."""

    def __init__(self, adb, adb_befehl="adb"):
        self.adb, self.adb_befehl = adb, adb_befehl

    def da(self, pfad):
        return self.adb(["shell", f"ls {pfad}"])[0] == 0

    def lesen(self, pfad):
        code, text = self.adb(["shell", f"cat {pfad} 2>/dev/null"])
        return text if code == 0 else ""

    def anlegen(self, ordner):
        return self.adb(["shell", f"mkdir -p {ordner}"])[0] == 0

    def befehl(self, pfad):
        return [self.adb_befehl, "exec-in", f"cat > {pfad}"]

    def schreiben(self, pfad, inhalt: bytes):
        return self.adb(["exec-in", f"cat > {pfad}"], eingabe=inhalt)[0] == 0

    def sha256(self, pfad):
        code, text = self.adb(["shell", f"sha256sum {pfad}"])
        return text.split(" ", 1)[0].strip() if code == 0 else ""


class LokalZiel:
    """Probelauf: dasselbe, aber in einen Ordner am PC."""

    def da(self, pfad):
        return os.path.exists(pfad)

    def lesen(self, pfad):
        try:
            with open(pfad, encoding="utf-8") as datei:
                return datei.read()
        except OSError:
            return ""

    def anlegen(self, ordner):
        os.makedirs(ordner, exist_ok=True)
        return True

    def befehl(self, pfad):
        return [sys.executable, "-c",
                "import shutil,sys; shutil.copyfileobj(sys.stdin.buffer, open(sys.argv[1], 'xb'))", pfad]

    def schreiben(self, pfad, inhalt: bytes):
        with open(pfad, "xb") as datei:
            datei.write(inhalt)
        return True

    def sha256(self, pfad):
        h = hashlib.sha256()
        with open(pfad, "rb") as datei:
            for stueck in iter(lambda: datei.read(STUECK), b""):
                h.update(stueck)
        return h.hexdigest()


def ziel_waehlen(ziel, wurzel: str, stand: str, empfaenger: str):
    """-> (ordner, schon_fertig). Nie einen vorhandenen Ordner wiederverwenden,
    ausser er ist fuer denselben Einmal-Schluessel schon vollstaendig."""
    for n in range(1, 20):
        ordner = f"{wurzel}/wiederherstellung_{stand}" + ("" if n == 1 else f"_{n}")
        if not ziel.da(ordner):
            return ordner, False
        if ziel.da(f"{ordner}/FERTIG") and ziel.lesen(f"{ordner}/EMPFAENGER.txt").strip() == empfaenger:
            return ordner, True
    raise TransferFehler("zu viele alte Sendungen - bitte am Handy aufraeumen")


def main(argv=None, adb=adb_echt, starten=subprocess.Popen) -> int:
    for strom in (sys.stdout, sys.stderr):
        try:
            strom.reconfigure(errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass
    zerleger = argparse.ArgumentParser(description="Termux-Sicherung fuer die Wiederherstellung senden.")
    zerleger.add_argument("--sicherung", default=None, help="Sicherungsordner (Standard: neuester)")
    zerleger.add_argument("--schluessel", default=None, help="privater Hauptschluessel")
    zerleger.add_argument("--nur-skript", action="store_true", help="nur wiederherstellen.sh aufs Handy legen")
    zerleger.add_argument("--lokal-ziel", default=None, help="Probelauf in diesen Ordner statt aufs Handy")
    zerleger.add_argument("--empfaenger", default=None, help="Einmal-Schluessel (nur mit --lokal-ziel)")
    args = zerleger.parse_args(argv)

    if args.lokal_ziel:
        ziel, wurzel = LokalZiel(), args.lokal_ziel.rstrip("/\\").replace("\\", "/")
        empfaenger = (args.empfaenger or "").strip()
    else:
        code, text = adb(["devices"])
        if code != 0 or not re.search(r"\tdevice\b", text):
            print("Abbruch: kein Handy am Kabel (adb devices). USB-Debugging an?")
            return 1
        ziel, wurzel = HandyZiel(adb), HANDY_ABLAGE
        ziel.anlegen(wurzel)
        with open(SKRIPT, "rb") as datei:
            inhalt = datei.read().replace(b"\r\n", b"\n")
        if not ziel.schreiben(f"{wurzel}/wiederherstellen.sh", inhalt):
            print("Abbruch: wiederherstellen.sh liess sich nicht aufs Handy legen.")
            return 1
        print(f"wiederherstellen.sh liegt in {wurzel}/")
        if args.nur_skript:
            print("Im neuen Termux: termux-setup-storage, pkg install age, dann")
            print(f"  bash {wurzel}/wiederherstellen.sh vorbereiten")
            return 0
        empfaenger = ziel.lesen(HANDY_EMPFAENGER).strip()
    treffer = EMPFAENGER_MUSTER.search(empfaenger)
    if not treffer:
        print("Abbruch: kein Einmal-Schluessel. Im neuen Termux zuerst:")
        print(f"  bash {HANDY_ABLAGE}/wiederherstellen.sh vorbereiten")
        return 3
    empfaenger = treffer.group(0)

    schluessel = args.schluessel or standard_schluessel()
    age = shutil.which("age")
    if not age or not os.path.isfile(schluessel):
        print("Abbruch: age oder der private Hauptschluessel fehlt am PC.")
        return 2
    sicherung = args.sicherung or neueste_sicherung(STANDARD_LOKAL)
    if not sicherung or not os.path.isfile(os.path.join(sicherung, "FERTIG")):
        print("Abbruch: keine vollstaendige Sicherung gefunden (Ordner mit FERTIG).")
        return 4
    teile = manifest_lesen(sicherung)
    if "home.tar.age" not in teile:
        print("Abbruch: MANIFEST.txt nennt kein home.tar.age.")
        return 4
    stand = os.path.basename(os.path.normpath(sicherung))

    try:
        ordner, fertig = ziel_waehlen(ziel, wurzel, stand, empfaenger)
    except TransferFehler as problem:
        print(f"Abbruch: {problem}")
        return 6
    if fertig:
        print(f"Liegt schon vollstaendig in {ordner} - nichts zu tun.")
        return 0
    ziel.anlegen(ordner)
    print(f"Sende Sicherung {stand} nach {ordner} (Einmal-Schluessel {empfaenger[:12]}...)")

    zeilen = [f"stand={stand}"]
    for name, soll in sorted(teile.items()):
        quelle = os.path.join(sicherung, name)
        print(f"  {name}: {os.path.getsize(quelle) // 1048576} MB ...", flush=True)
        try:
            ist_alt, ist_neu, groesse = teil_senden(
                quelle, [age, "-d", "-i", schluessel], [age, "-r", empfaenger],
                ziel.befehl(f"{ordner}/{name}"), starten=starten)
        except TransferFehler as problem:
            print(f"Abbruch: {name} scheiterte ({problem}). Kein FERTIG - Sendung ist unvollstaendig.")
            return 6
        if ist_alt != soll:
            print(f"Abbruch: {name} am PC beschaedigt (sha256 passt nicht zu MANIFEST.txt).")
            return 5
        if ziel.sha256(f"{ordner}/{name}") != ist_neu:
            print(f"Abbruch: {name} kam nicht vollstaendig an (sha256 am Ziel falsch).")
            return 5
        print(f"    angekommen, {groesse // 1048576} MB, Pruefsumme ok")
        zeilen.append(f"{name} groesse={groesse} sha256={ist_neu}")

    for liste in ("pakete_manuell.txt", "pip_alt.txt"):      # nur Paketnamen, unverschluesselt
        pfad = os.path.join(sicherung, liste)
        if os.path.isfile(pfad):
            with open(pfad, "rb") as datei:
                ziel.schreiben(f"{ordner}/{liste}", datei.read())
    ziel.schreiben(f"{ordner}/EMPFAENGER.txt", (empfaenger + "\n").encode())
    ziel.schreiben(f"{ordner}/MANIFEST.txt", ("\n".join(zeilen) + "\n").encode())
    ziel.schreiben(f"{ordner}/FERTIG", (stand + "\n").encode())
    print("Fertig. Im neuen Termux jetzt:")
    print(f"  bash {HANDY_ABLAGE}/wiederherstellen.sh einspielen")
    return 0


if __name__ == "__main__":
    sys.exit(main())
