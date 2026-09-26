"""Sortierschluessel fuer die pCloud-Fotos — Schritt 1 von Stufe B (Jahr/Thema).

Was dieses Werkzeug tut:
  Es liest ausschliesslich Dateinamen und Groessen im pCloud-Upload-Ordner
  (keine Bilder, kein Download, keine Aenderung an der pCloud) und schreibt
  daraus eine CSV — den Sortierschluessel. Jede Zeile ist eine Datei mit
  Jahr/Monat/Tag, Geraet, Quelle, Groesse und Doppelungs-Kennzeichen.

Warum so und nicht anders:
  * Rekursives Durchlaufen der pCloud laeuft belegt in einen Timeout
    (180 s, Exit 124). Deshalb wird Ebene fuer Ebene gelesen, mit fester
    Tiefenbegrenzung.
  * Die CSV enthaelt private Dateinamen -> sie wird AUSSERHALB des Repos
    abgelegt (~/foto_sortierung/), das Repo sieht nur dieses Skript.
  * Die Spalte `thema` bleibt leer: sie wird in Stufe 2 (Clustering ueber
    Kontaktboegen) gefuellt. Zielstruktur ist `Agent/Fotos/<Jahr>/<Thema>/`.

Regeln des Projekts, die hier gelten:
  * Originale werden NIE verschoben oder umbenannt (Kopie, nicht Verschieben).
  * Bilder werden nie ins Backend kopiert — nur in-memory fuer die Analyse.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import os
import re

WURZEL = "P:/Automatic Upload"

BILDENDUNGEN = (
    ".jpg", ".jpeg", ".png", ".heic", ".heif", ".dng", ".bmp", ".gif",
    ".webp", ".mp4", ".3gp", ".mov", ".avi", ".mkv",
)

# Erst feste Muster, dann die Suche: deckt image_/IMG_/VID/Screenshot_/Oplus_
# und die pCloud-Umbenennungen (6 Ziffern davor) gleichermassen ab.
FESTE_MUSTER = (
    re.compile(r"^(\d{6})_(\d{4})[-_](\d{2})[-_](\d{2})_"),      # 059956_2024-08-09_...
    re.compile(r"^(\d{4})(\d{2})(\d{2})[_-]"),                    # 20190209_161112...
)
SUCHE = re.compile(
    r"(19|20)(\d{2})[-_]?(0[1-9]|1[0-2])[-_]?(0[1-9]|[12]\d|3[01])"
)
EPOCHE = re.compile(r"^(1[0-9]{12})\b")      # Millisekunden seit 1970

# Doppelungen: " (2)", "_Kopie", "-Kopie", "kopie von …"
DOPPEL_MUSTER = re.compile(r"\s*\(\d+\)\s*$|[-_ ]?kopie\b", re.IGNORECASE)


def datum_aus_name(name: str):
    """(Jahr, Monat, Tag) aus dem Dateinamen oder None.

    Kein Raten: nur plausible Werte (Jahr 1990–2027, Monat 1–12, Tag 1–31).
    """
    for muster in FESTE_MUSTER:
        treffer = muster.match(name)
        if treffer:
            gruppen = treffer.groups()
            if len(gruppen) == 4:                     # pCloud: 6 Ziffern + Datum
                jahr, monat, tag = gruppen[1], gruppen[2], gruppen[3]
            else:                                     # OnePlus: Datum direkt vorn
                jahr, monat, tag = gruppen[0], gruppen[1], gruppen[2]
            werte = _plausibel(int(jahr), int(monat), int(tag))
            if werte:
                return werte

    treffer = SUCHE.search(name)
    if treffer:
        jahr = int(treffer.group(1) + treffer.group(2))
        werte = _plausibel(jahr, int(treffer.group(3)), int(treffer.group(4)))
        if werte:
            return werte

    treffer = EPOCHE.match(name)
    if treffer:
        try:
            tag = datetime.date.fromtimestamp(int(treffer.group(1)) / 1000)
            return (tag.year, tag.month, tag.day)
        except (OverflowError, OSError, ValueError):
            return None
    return None


def _plausibel(jahr: int, monat: int, tag: int):
    if 1990 <= jahr <= 2027 and 1 <= monat <= 12 and 1 <= tag <= 31:
        return (jahr, monat, tag)
    return None


def motiv_name(name: str) -> str:
    """Name ohne Doppelungs-Kennzeichen und ohne pCloud-Praefix.

    Damit zaehlen ' (2)' und '_Kopie' nicht als eigenes Motiv — sonst ist jede
    Zahl falsch, die ein Leser nachprueft.
    """
    ohne_endung, endung = os.path.splitext(name)
    kern = DOPPEL_MUSTER.sub("", ohne_endung).strip()
    kern = re.sub(r"^\d{6}_", "", kern)
    return kern.lower() + endung.lower()


def ziel_ordner(jahr: int, thema: str, geraet: str) -> str:
    """Zielstruktur Stufe B: `Agent/Fotos/<Jahr>/<Thema>/<Geraet>`.

    Leeres Thema wird zu `unbestimmt` — ein Ordner, der sagt was er ist,
    statt einer Luecke, die man spaeter fuer einen Fehler haelt.
    """
    thema = (thema or "unbestimmt").strip().replace("/", "-")
    geraet = (geraet or "unbekannt").strip().replace("/", "-")
    return f"Agent/Fotos/{jahr}/{thema}/{geraet}"


def sammle(wurzel: str, max_tiefe: int = 3):
    """Liest die Ordner Ebene fuer Ebene (kein rekursiver Vollscan)."""
    zeilen = []
    fehler = []

    def gehe(ordner: str, geraet: str, tiefe: int):
        if tiefe > max_tiefe:
            return
        try:
            with os.scandir(ordner) as eintraege:
                liste = list(eintraege)
        except OSError as problem:
            fehler.append(f"{ordner}: {problem}")
            return

        for eintrag in liste:
            try:
                if eintrag.is_dir(follow_symlinks=False):
                    gehe(eintrag.path, geraet, tiefe + 1)
                    continue
                if not eintrag.name.lower().endswith(BILDENDUNGEN):
                    continue
                groesse = eintrag.stat(follow_symlinks=False).st_size
            except OSError:
                continue
            datum = datum_aus_name(eintrag.name)
            zeilen.append({
                "jahr": datum[0] if datum else "",
                "monat": datum[1] if datum else "",
                "tag": datum[2] if datum else "",
                "datumquelle": "namen" if datum else "offen",
                "motiv": motiv_name(eintrag.name),
                "datei": eintrag.name,
                "ordner": os.path.dirname(eintrag.path).replace("\\", "/"),
                "geraet": geraet,
                "bytes": groesse,
                "mb": round(groesse / 1024 / 1024, 2),
                "thema": "",
                "doppelung": "",
            })
    # Erste Ebene: der Upload-Ordner enthaelt die Geraete-Ordner.
    for eintrag in sorted(os.scandir(wurzel), key=lambda e: e.name):
        if eintrag.is_dir(follow_symlinks=False):
            gehe(eintrag.path, eintrag.name, 1)
    return zeilen, fehler


def doppelungen_markieren(zeilen):
    """Erster Treffer eines Motivs = Original, alle weiteren = Doppelung."""
    gesehen = {}
    for zeile in sorted(zeilen, key=lambda z: (z["motiv"], z["ordner"], z["datei"])):
        schluessel = zeile["motiv"]
        if schluessel in gesehen:
            zeile["doppelung"] = gesehen[schluessel]
        else:
            gesehen[schluessel] = zeile["datei"]
    return zeilen


def uebersicht(zeilen):
    """Zahlen fuer die Antwort: je Jahr Dateien, Motive, Groesse, offene Daten."""
    je_jahr = {}
    for zeile in zeilen:
        jahr = zeile["jahr"] or "ohne Datum"
        eimer = je_jahr.setdefault(jahr, {"dateien": 0, "motive": set(), "bytes": 0,
                                          "offen": 0, "doppel": 0})
        eimer["dateien"] += 1
        eimer["bytes"] += zeile["bytes"]
        if not zeile["jahr"]:
            eimer["offen"] += 1
        if zeile["doppelung"]:
            eimer["doppel"] += 1
        eimer["motive"].add(zeile["motiv"])

    print(f"{'Jahr':<12}{'Dateien':>9}{'Motive':>8}{'Größe GB':>10}"
          f"{'Doppel':>8}{'ohne Datum':>12}")
    for jahr in sorted(je_jahr, key=lambda j: (j == "ohne Datum", str(j))):
        e = je_jahr[jahr]
        print(f"{jahr:<12}{e['dateien']:>9}{len(e['motive']):>8}"
              f"{e['bytes']/1024/1024/1024:>10.2f}{e['doppel']:>8}{e['offen']:>12}")
    return je_jahr


def main(argv=None) -> int:
    zerleger = argparse.ArgumentParser(description=__doc__)
    zerleger.add_argument("--wurzel", default=WURZEL)
    zerleger.add_argument("--csv", default=os.path.join(
        os.path.expanduser("~"), "foto_sortierung", "sortierschluessel.csv"))
    zerleger.add_argument("--zeitraum", default="",
                          help="z. B. 2022-2026 (leer = alles)")
    args = zerleger.parse_args(argv)

    if not os.path.isdir(args.wurzel):
        print(f"Upload-Ordner nicht erreichbar: {args.wurzel}", flush=True)
        return 2

    print(f"Lese Ebene für Ebene: {args.wurzel} (kein rekursiver Vollscan)",
          flush=True)
    zeilen, fehler = sammle(args.wurzel)
    doppelungen_markieren(zeilen)

    if args.zeitraum:
        von, bis = args.zeitraum.split("-")
        zeilen = [z for z in zeilen
                  if z["jahr"] and int(von) <= int(z["jahr"]) <= int(bis)]

    os.makedirs(os.path.dirname(args.csv), exist_ok=True)
    felder = ["jahr", "monat", "tag", "datumquelle", "thema", "geraet",
              "ordner", "datei", "motiv", "doppelung", "bytes", "mb"]
    with open(args.csv, "w", newline="", encoding="utf-8") as datei:
        schreiber = csv.DictWriter(datei, fieldnames=felder)
        schreiber.writeheader()
        schreiber.writerows(zeilen)

    print()
    uebersicht(zeilen)
    print(f"\nDateien gesamt: {len(zeilen)}"
          f"   mit Datum: {sum(1 for z in zeilen if z['jahr'])}"
          f"   offen: {sum(1 for z in zeilen if not z['jahr'])}")
    print(f"Sortierschluessel: {args.csv}")
    if fehler:
        print(f"Nicht lesbare Ordner: {len(fehler)}")
        for eintrag in fehler[:5]:
            print(f"  {eintrag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
