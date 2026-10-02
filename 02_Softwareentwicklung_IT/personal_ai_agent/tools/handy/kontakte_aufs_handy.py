"""Telefonbuch -> kontakte.json -> Handy (02.10.2026, Issue #3 Teil A, „Weg B: PC per Kabel").

Warum:
  Am Profil einer Person (Quiz „Personen benennen") sollen Telefonnummern und
  Geburtstag aus dem Telefonbuch hängen — EIN Personenbestand, kein zweites
  Adressbuch. Das Android-Telefonbuch ist mit Google-Kontakte abgeglichen und
  bleibt die Quelle; das Profil verweist nur per Kennung (Android ``contact_id``)
  darauf. Am Handy selbst geht das Lesen heute nicht: Termux kommt aus dem Play
  Store, Termux:API aus F-Droid — verschieden signiert, ``termux-contact-list``
  antwortet nicht. Später kann die Hey-Agent-App (eigene App, Berechtigung
  „Kontakte lesen") dieselbe Datei schreiben; am Backend ändert sich dann nichts.

Format (``~/foto_sortierung/kontakte.json``, nie im Repo)::

    {"stand": "...", "quelle": "telefonbuch-adb",
     "kontakte": [{"id": "123", "name": "...", "nummern": ["+49..."],
                   "geburtstag": "1990-05-04" | "--05-04" | null}]}

Ablauf:
  * Ohne Schalter: Trockenlauf — liest per ADB und zeigt NUR Zahlen.
  * ``--schreiben``: schreibt die Datei (atomar, alte Fassung als ``.vorher``).
  * ``--senden``: zusätzlich nach ``/sdcard/Download`` legen (push + Größenprobe);
    die App übernimmt sie beim nächsten Start (agent-ensure.sh / start-termux.sh).

Datenschutz: Ausgabe nur Zählungen, nie Namen oder Nummern. Kein Netz außer dem
lokalen ``adb``, kein Sprachmodell, Ziel im Repo -> Exit 2.
Exit: 0 = ok, 2 = Aufruf-/Schutzfehler, 3 = Telefonbuch nicht lesbar, 1 = Übertragung fehlgeschlagen.
"""
from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import os
import re
import subprocess
import sys
from typing import Callable, Dict, List, Optional, Tuple

HIER = os.path.dirname(os.path.abspath(__file__))
PROJEKT = os.path.dirname(os.path.dirname(HIER))
STANDARD_AUSGABE = os.path.join(os.path.expanduser("~"), "foto_sortierung", "kontakte.json")
STANDARD_ZIEL = "/sdcard/Download"
DATEINAME = "kontakte.json"

# Wie tools/whatsapp/zuordnung_bauen.py, aber mit contact_id (stabiler Verweis).
TELEFON_QUERY = ("content query --uri content://com.android.contacts/data/phones "
                 "--projection contact_id:display_name:data1")
EVENT_QUERY = ("content query --uri content://com.android.contacts/data "
               "--projection contact_id:display_name:data1:data2:mimetype "
               "--where \"mimetype='vnd.android.cursor.item/contact_event'\"")
MIMETYPE_EVENT = "vnd.android.cursor.item/contact_event"
EVENT_TYP_GEBURTSTAG = 3

Ausfuehren = Callable[[List[str]], Tuple[int, str]]


def _zuordnung():
    """Die Zerleger aus zuordnung_bauen.py wiederverwenden (eine Quelle)."""
    pfad = os.path.join(PROJEKT, "tools", "whatsapp", "zuordnung_bauen.py")
    spez = importlib.util.spec_from_file_location("zuordnung_bauen", pfad)
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


def _ausfuehren(befehl: List[str]) -> Tuple[int, str]:
    try:
        lauf = subprocess.run(befehl, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=180)
    except (OSError, subprocess.TimeoutExpired) as problem:
        return 127, problem.__class__.__name__
    return lauf.returncode, (lauf.stdout or "") + ("" if lauf.returncode == 0 else (lauf.stderr or ""))


# ── Reine Funktionen ────────────────────────────────────────────────────────

def nummer_saeubern(nummer: str) -> str:
    """Leerzeichen, Klammern, Bindestriche weg; führendes + bleibt."""
    n = re.sub(r"[^\d+]", "", nummer or "")
    return ("+" + n.replace("+", "")) if n.startswith("+") else n.replace("+", "")


def geburtstag_text(datum: str) -> Optional[str]:
    """``YYYY-MM-DD`` bleibt (mit Jahr), ``--MM-DD`` bleibt (ohne Jahr), sonst None."""
    d = (datum or "").strip()
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", d) or re.fullmatch(r"--(\d{2})-(\d{2})", d)
    if not m:
        return None
    teile = [int(x) for x in m.groups()]
    monat, tag = teile[-2], teile[-1]
    if not (1 <= monat <= 12 and 1 <= tag <= 31):
        return None
    return d


def kontakte_bauen(telefon_roh: str, event_roh: str, zerleger) -> List[Dict]:
    """Rohausgaben -> [{id, name, nummern, geburtstag}], nach Name sortiert."""
    kontakte: Dict[str, Dict] = {}
    for f in zerleger(telefon_roh, ["contact_id", "display_name", "data1"]):
        kid = (f.get("contact_id") or "").strip()
        if not kid.isdigit():
            continue
        k = kontakte.setdefault(kid, {"id": kid, "name": (f.get("display_name") or "").strip(),
                                      "nummern": [], "geburtstag": None})
        nummer = nummer_saeubern(f.get("data1") or "")
        if len(nummer.lstrip("+")) >= 3 and nummer not in k["nummern"]:
            k["nummern"].append(nummer)
    for f in zerleger(event_roh, ["contact_id", "display_name", "data1", "data2", "mimetype"]):
        if (f.get("mimetype") or "") != MIMETYPE_EVENT:
            continue
        try:
            if int(f.get("data2") or "-1") != EVENT_TYP_GEBURTSTAG:
                continue
        except ValueError:
            continue
        kid = (f.get("contact_id") or "").strip()
        datum = geburtstag_text(f.get("data1") or "")
        if not kid.isdigit() or not datum:
            continue
        k = kontakte.setdefault(kid, {"id": kid, "name": (f.get("display_name") or "").strip(),
                                      "nummern": [], "geburtstag": None})
        if not k["geburtstag"] or (len(datum) > len(k["geburtstag"])):   # mit Jahr bevorzugt
            k["geburtstag"] = datum
    return sorted((k for k in kontakte.values() if k["name"]),
                  key=lambda k: (k["name"].casefold(), k["id"]))


def zahlen_bericht(kontakte: List[Dict]) -> str:
    mit_nummer = sum(1 for k in kontakte if k["nummern"])
    mit_gb = sum(1 for k in kontakte if k["geburtstag"])
    mit_jahr = sum(1 for k in kontakte if k["geburtstag"] and not k["geburtstag"].startswith("--"))
    return (f"Kontakte: {len(kontakte)} · mit Nummer: {mit_nummer} · mit Geburtstag: {mit_gb} "
            f"(davon mit Jahr: {mit_jahr})")


def _im_repo(pfad: str) -> bool:
    try:
        return os.path.commonpath([os.path.realpath(pfad), os.path.realpath(PROJEKT)]) == \
            os.path.realpath(PROJEKT)
    except ValueError:
        return False


def schreiben(kontakte: List[Dict], pfad: str, stand: Optional[str] = None) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(pfad)), exist_ok=True)
    if os.path.isfile(pfad):
        with open(pfad, "rb") as alt, open(pfad + ".vorher", "wb") as sicherung:
            sicherung.write(alt.read())
    temp = pfad + ".tmp"
    with open(temp, "w", encoding="utf-8", newline="\n") as datei:
        json.dump({"stand": stand or datetime.datetime.now().isoformat(timespec="seconds"),
                   "quelle": "telefonbuch-adb", "kontakte": kontakte},
                  datei, ensure_ascii=False, indent=1)
        datei.write("\n")
    os.replace(temp, pfad)


def senden(pfad: str, ziel: str, ausfuehren: Ausfuehren, adb: str = "adb") -> Tuple[int, str]:
    groesse = os.path.getsize(pfad)
    code, _ = ausfuehren([adb, "push", pfad, f"{ziel}/{DATEINAME}"])
    c2, aus = ausfuehren([adb, "shell", "stat", "-c", "%s", f"{ziel}/{DATEINAME}"])
    if code == 0 and c2 == 0 and aus.strip() == str(groesse):
        return 0, f"gesendet: {DATEINAME} ({groesse:,} Bytes, Größe am Handy gleich)".replace(",", ".")
    return 1, f"FEHLER: {DATEINAME} - push {code}, Größe am Handy {aus.strip() or '?'} statt {groesse}"


def main(argv=None, ausfuehren: Ausfuehren = _ausfuehren) -> int:
    parser = argparse.ArgumentParser(description="Telefonbuch -> kontakte.json -> Handy (nur Zahlen).")
    parser.add_argument("--ausgabe", default=STANDARD_AUSGABE)
    parser.add_argument("--ziel", default=STANDARD_ZIEL)
    parser.add_argument("--adb", default="adb")
    parser.add_argument("--schreiben", action="store_true", help="kontakte.json schreiben")
    parser.add_argument("--senden", action="store_true", help="schreiben und aufs Handy legen")
    args = parser.parse_args(argv)
    if _im_repo(args.ausgabe):
        print("Ziel liegt im Repo - abgelehnt (Kontakte gehören nie ins Repo).")
        return 2
    if not args.ziel.startswith("/sdcard/"):
        print("Ziel am Handy muss im freigegebenen Speicher liegen (/sdcard/...).")
        return 2
    zerleger = _zuordnung()._zeilen_zerlegen
    c1, telefon = ausfuehren([args.adb, "shell", TELEFON_QUERY])
    c2, events = ausfuehren([args.adb, "shell", EVENT_QUERY])
    if c1 != 0 or c2 != 0:
        print("Telefonbuch nicht lesbar (Handy am Kabel? USB-Debugging an?)")
        return 3
    kontakte = kontakte_bauen(telefon, events, zerleger)
    print(zahlen_bericht(kontakte))
    if not (args.schreiben or args.senden):
        print("Trockenlauf - nichts geschrieben. Mit --schreiben bzw. --senden ausführen.")
        return 0
    if not kontakte:
        print("Keine Kontakte gelesen - nichts geschrieben.")
        return 3
    schreiben(kontakte, args.ausgabe)
    print(f"geschrieben: {DATEINAME} (außerhalb des Repos)")
    if args.senden:
        code, zeile = senden(args.ausgabe, args.ziel, ausfuehren, args.adb)
        print(zeile)
        if code:
            return 1
        print("Fertig. Am Handy Termux beenden und Hey Agent öffnen (oder Widget 'agent') - "
              "dann übernimmt die App die Datei.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
