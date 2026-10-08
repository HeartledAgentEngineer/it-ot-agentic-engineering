r"""Quiz-Namen aus der Termux-Sicherung auf den PC holen. (08.10.2026)

Anlass: Die Gruppen werden am PC neu gebildet (Mindest-Erkennungssicherheit 0,8).
Damit dabei keine zwei benannten Personen zusammengelegt werden, braucht das
Gruppierungswerkzeug die Namen, die Sebastian im Gruppen-Quiz am Handy vergeben
hat (``personen_gruppieren``: verschiedene bestaetigte Namen verschmelzen nie).
Die liegen nur am Handy - und in der verschluesselten Sicherung.

Das Werkzeug liest ``home.tar.age`` als Strom (``age -d``), sucht darin nur

* ``home/foto_sortierung/personen_bestaetigt.json`` ``{"bestaetigt": {kennung: name}}``
* ``home/foto_sortierung/personen_vorgaben.json``   ``{"gleich": [...], "verschieden": [...]}``

und entpackt sonst nichts. Ausgabe: je Name die zugehoerigen Gruppen mit ihrer
Groesse aus ``gesicht_zuordnung.jsonl`` (auf Sebastians ausdruecklichen Wunsch
mit Namen; ``--ohne-namen`` zeigt nur Nummern).

Mit ``--uebernehmen`` werden beide Dateien nach ``~/foto_sortierung/`` geschrieben;
vorhandene Dateien werden vorher als ``*.vorher`` gesichert. Standard: nur zeigen.

Aufruf (PowerShell, aus ``personal_ai_agent``)::

    & .\backend\.venv\Scripts\python.exe tools\handy\namen_aus_sicherung.py "$HOME\termux-sicherung\<stand>"
"""
from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import os
import shutil
import sys
import tarfile

HIER = os.path.dirname(os.path.abspath(__file__))
BASIS = os.path.join(os.path.expanduser("~"), "foto_sortierung")
STANDARD_ZUORDNUNG = os.path.join(BASIS, "personen_gruppen", "gesicht_zuordnung.jsonl")
GESUCHT = {"home/foto_sortierung/personen_bestaetigt.json": "personen_bestaetigt.json",
           "home/foto_sortierung/personen_vorgaben.json": "personen_vorgaben.json"}


def _pruefer():
    spez = importlib.util.spec_from_file_location(
        "sicherung_pruefen", os.path.join(HIER, "sicherung_pruefen.py"))
    assert spez is not None and spez.loader is not None
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


def dateien_holen(strom) -> dict:
    """Aus einem tar-Strom nur die gesuchten Dateien lesen -> ``{dateiname: bytes}``.
    Bricht ab, sobald beide gefunden sind."""
    gefunden = {}
    with tarfile.open(fileobj=strom, mode="r|*") as archiv:
        for eintrag in archiv:
            ziel = GESUCHT.get(eintrag.name.lstrip("./"))
            if ziel and eintrag.isfile():
                datei = archiv.extractfile(eintrag)
                if datei is not None:
                    gefunden[ziel] = datei.read()
            if len(gefunden) == len(GESUCHT):
                break
    return gefunden


def gruppen_groessen(pfad: str) -> dict:
    groessen = collections.Counter()
    if os.path.isfile(pfad):
        with open(pfad, encoding="utf-8") as datei:
            for zeile in datei:
                try:
                    kennung = json.loads(zeile).get("kennung")
                except (ValueError, AttributeError):
                    continue
                if kennung:
                    groessen[kennung] += 1
    return groessen


def uebersicht(bestaetigt: dict, vorgaben: dict, groessen: dict, mit_namen: bool) -> list:
    je_name = collections.defaultdict(list)
    for kennung, name in bestaetigt.items():
        je_name[str(name)].append(kennung)
    zeilen = [f"Benannte Gruppen: {len(bestaetigt)} · verschiedene Namen: {len(je_name)} · "
              f"Regeln gleich: {len(vorgaben.get('gleich') or [])}, "
              f"verschieden: {len(vorgaben.get('verschieden') or [])}", ""]
    reihe = sorted(je_name.items(), key=lambda kv: -sum(groessen.get(k, 0) for k in kv[1]))
    for nummer, (name, kennungen) in enumerate(reihe, start=1):
        kennungen.sort(key=lambda k: -groessen.get(k, 0))
        summe = sum(groessen.get(k, 0) for k in kennungen)
        titel = name if mit_namen else f"Name {nummer}"
        teile = ", ".join(f"{k} ({groessen.get(k, 0)})" for k in kennungen)
        zeilen.append(f"{titel}: {len(kennungen)} Gruppe(n), {summe} Gesichter -> {teile}")
    return zeilen


def uebernehmen(gefunden: dict, ziel: str) -> list:
    os.makedirs(ziel, exist_ok=True)
    geschrieben = []
    for name, inhalt in gefunden.items():
        pfad = os.path.join(ziel, name)
        if os.path.isfile(pfad):
            shutil.copy2(pfad, pfad + ".vorher")
        with open(pfad + ".neu", "wb") as datei:
            datei.write(inhalt)
        os.replace(pfad + ".neu", pfad)
        geschrieben.append(name)
    return geschrieben


def main(argv=None, oeffnen=None) -> int:
    zerleger = argparse.ArgumentParser(description="Quiz-Namen aus der Termux-Sicherung lesen.")
    zerleger.add_argument("ordner", help="Sicherungsordner mit home.tar.age")
    zerleger.add_argument("--zuordnung", default=STANDARD_ZUORDNUNG)
    zerleger.add_argument("--ziel", default=BASIS)
    zerleger.add_argument("--uebernehmen", action="store_true")
    zerleger.add_argument("--ohne-namen", action="store_true")
    zerleger.add_argument("--schluessel", default=None)
    args = zerleger.parse_args(argv)

    teil = os.path.join(args.ordner, "home.tar.age")
    if not os.path.isfile(teil):
        print(f"Abbruch: {teil} fehlt.")
        return 1
    if oeffnen is None:
        sp = _pruefer()
        schluessel = args.schluessel or sp.STANDARD_SCHLUESSEL
        age = shutil.which("age") or "age"
        if not os.path.isfile(schluessel) or not shutil.which(age):
            print("Abbruch: privater Schluessel oder age fehlt.")
            return 1
        oeffnen = sp.age_entschluesseler(age, schluessel)

    strom = oeffnen(teil)
    try:
        gefunden = dateien_holen(strom)
    finally:
        try:
            strom.close()
        except Exception:      # abgebrochener Strom nach vorzeitigem Ende ist kein Fehler
            pass
    if "personen_bestaetigt.json" not in gefunden:
        print("In der Sicherung steht keine personen_bestaetigt.json.")
        return 3
    bestaetigt = (json.loads(gefunden["personen_bestaetigt.json"]).get("bestaetigt") or {})
    vorgaben = json.loads(gefunden.get("personen_vorgaben.json", b"{}") or b"{}")
    for zeile in uebersicht(bestaetigt, vorgaben, gruppen_groessen(args.zuordnung),
                            mit_namen=not args.ohne_namen):
        print(zeile)
    if args.uebernehmen:
        for name in uebernehmen(gefunden, args.ziel):
            print(f"uebernommen: {name}")
    else:
        print("\n(Nur gezeigt. Mit --uebernehmen werden beide Dateien nach ~/foto_sortierung geschrieben.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
