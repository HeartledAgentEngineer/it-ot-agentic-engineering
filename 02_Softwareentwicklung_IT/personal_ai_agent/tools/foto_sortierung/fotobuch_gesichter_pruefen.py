"""Sind die Fotobuch-Fotos in der Gesichtererkennung und in den Gruppen? (06.10.2026)

Anlass: In der Erzähl-Diashow zeigen die Fotobuch-Seiten „niemand erkannt" —
am Handy gezählt: 0 von 849 Fotobuch-Fotos haben eine Gesichter-Gruppe. Dieses
Werkzeug findet heraus, an welcher Stelle der Kette sie fehlen:

  1. Gesichtererkennung (Vektordateien ``personen_vektoren*.jsonl`` /
     ``video_vektoren*.jsonl``): hat das Foto eine Zeile, und wurden Gesichter
     gefunden?
  2. Gruppierung (``personen_gruppen/gesicht_zuordnung.jsonl``): hängt das
     Foto an einer Gruppe?

Datenschutz: nur lesend, kein Netz, kein Modell. Ausgegeben werden NUR Zahlen —
keine Datei-Kennungen, keine Namen, keine Titel.

Aufruf (PowerShell, aus dem Projektordner)::

    & backend\\.venv\\Scripts\\python.exe tools\\foto_sortierung\\fotobuch_gesichter_pruefen.py

Exit: 0 geprüft, 2 Fotobuch-Datei fehlt.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from typing import Dict, List, Optional, Set

STANDARD_BASIS = os.path.join(os.path.expanduser("~"), "foto_sortierung")
FOTOBUCH = "fotobuch_ereignisse.jsonl"
ZUORDNUNG = os.path.join("personen_gruppen", "gesicht_zuordnung.jsonl")
VEKTOR_MUSTER = ("personen_vektoren*.jsonl", "video_vektoren*.jsonl")
_BILD_ID = re.compile(r'"bild_id"\s*:\s*"([^"]+)"')


def fotobuch_fotos(pfad: str) -> Set[str]:
    """Alle Datei-Kennungen der Fotobuch-Seiten (als Text). Kaputte Zeilen zählen nicht."""
    fotos: Set[str] = set()
    with open(pfad, encoding="utf-8") as datei:
        for zeile in datei:
            try:
                eintrag = json.loads(zeile)
            except ValueError:
                continue
            if isinstance(eintrag, dict):
                for k in eintrag.get("datei_kennungen") or []:
                    if k is not None and str(k).strip():
                        fotos.add(str(k).strip())
    return fotos


def vektoren_zaehlen(pfad: str, fotos: Set[str]) -> Dict[str, int]:
    """Fotobuch-Fotos mit Zeile in einer Vektordatei, davon mit Gesichtern, Gesichter gesamt.

    Schnell: die Kennung steht vorn in der Zeile; nur Treffer werden ganz gelesen.
    Video-Standbilder (``<id>#t=…``) zählen für ihre Video-Kennung.
    """
    mit_zeile: Set[str] = set()
    mit_gesicht: Set[str] = set()
    gesichter = 0
    with open(pfad, encoding="utf-8", errors="replace") as datei:
        for zeile in datei:
            treffer = _BILD_ID.search(zeile[:300])
            if not treffer:
                continue
            kennung = treffer.group(1).split("#", 1)[0]
            if kennung not in fotos:
                continue
            mit_zeile.add(kennung)
            try:
                anzahl = len(json.loads(zeile).get("gesichter") or [])
            except (ValueError, AttributeError):
                anzahl = 0
            if anzahl:
                mit_gesicht.add(kennung)
                gesichter += anzahl
    return {"mit_zeile": len(mit_zeile), "mit_gesicht": len(mit_gesicht), "gesichter": gesichter}


def zuordnung_zaehlen(pfad: str, fotos: Set[str]) -> Dict[str, int]:
    """Fotobuch-Fotos mit mindestens einer Gruppe; Zahl der verschiedenen Gruppen."""
    mit_gruppe: Set[str] = set()
    gruppen: Set[str] = set()
    with open(pfad, encoding="utf-8") as datei:
        for zeile in datei:
            try:
                z = json.loads(zeile)
            except ValueError:
                continue
            if not isinstance(z, dict) or not z.get("kennung"):
                continue
            kennung = str(z.get("video_id") or z.get("bild_id") or "").split("#", 1)[0]
            if kennung in fotos:
                mit_gruppe.add(kennung)
                gruppen.add(str(z["kennung"]))
    return {"mit_gruppe": len(mit_gruppe), "gruppen": len(gruppen)}


def befund(gesamt: int, erkannt: int, mit_gesicht: int, gruppiert: int) -> str:
    """Ein Satz: wo die Kette reißt."""
    if gesamt == 0:
        return "Das Fotobuch enthält keine Fotos mit Datei-Kennung."
    if erkannt == 0:
        return ("Die Fotobuch-Fotos waren NICHT in der Gesichtererkennung. Nächster Schritt: "
                "Gesichtererkennung für diese Fotos laufen lassen, dann neu gruppieren und ans Handy senden.")
    if mit_gesicht == 0:
        return "Die Fotos waren in der Erkennung, aber es wurden keine Gesichter gefunden (Schwelle/Scans prüfen)."
    if gruppiert == 0:
        return ("Gesichter wurden gefunden, hängen aber an keiner Gruppe. Nächster Schritt: neu gruppieren "
                "(diese Vektordatei mit --vektoren einbeziehen) und ans Handy senden.")
    if erkannt < gesamt:
        return (f"Teilweise: {gesamt - erkannt} Fotos fehlen noch in der Erkennung; "
                f"{gruppiert} Fotos hängen schon an Gruppen. Fehlende nachholen, dann neu gruppieren.")
    return "Erkannt und gruppiert. Fehlen die Personen am Handy, ist dort ein älterer Stand — neu senden."


REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLAN = "fotobuch_plan.json"


def plan_schreiben(fotos: Set[str], pfad: str) -> int:
    """Auswahlliste fuer ``gesicht_erkennen.py --plan`` (Format ``{"zuege": [{"fileid"}]}``).

    Nur ausserhalb des Repos (Datei-Kennungen sind privat). Abgeleitete Datei:
    wird bei jedem Aufruf neu geschrieben (atomar), ist also mehrfach aufrufbar.
    """
    ziel = os.path.normcase(os.path.abspath(pfad))
    if os.path.commonpath([ziel, os.path.normcase(REPO)]) == os.path.normcase(REPO):
        raise SystemExit(f"Ziel liegt im Repo – abgelehnt: {pfad}")
    zuege = [{"fileid": f, "jahr": None} for f in sorted(fotos)]
    tmp = pfad + ".tmp"
    with open(tmp, "w", encoding="utf-8") as datei:
        json.dump({"quelle": FOTOBUCH, "zuege": zuege}, datei)
    os.replace(tmp, pfad)
    return len(zuege)


def main(argv: Optional[List[str]] = None) -> int:
    zerleger = argparse.ArgumentParser(description="Fotobuch-Fotos in Erkennung/Gruppen? Nur Zahlen.")
    zerleger.add_argument("--basis", default=STANDARD_BASIS)
    zerleger.add_argument("--plan-schreiben", action="store_true",
                          help=f"zusaetzlich <basis>/{PLAN} fuer gesicht_erkennen.py --plan schreiben")
    args = zerleger.parse_args(argv)

    buch = os.path.join(args.basis, FOTOBUCH)
    if not os.path.isfile(buch):
        print(f"Fotobuch-Datei fehlt: {buch}")
        return 2
    fotos = fotobuch_fotos(buch)
    print(f"Fotobuch: {len(fotos)} Fotos mit Datei-Kennung")
    if args.plan_schreiben:
        pfad = os.path.join(args.basis, PLAN)
        print(f"Auswahlliste für die Gesichtererkennung geschrieben: {pfad} ({plan_schreiben(fotos, pfad)} Fotos)")

    erkannt_zahl = 0
    beste_mit_gesicht = 0
    dateien: List[str] = sorted({p for m in VEKTOR_MUSTER for p in glob.glob(os.path.join(args.basis, m))})
    for pfad in dateien:
        z = vektoren_zaehlen(pfad, fotos)
        print(f"  Erkennung {os.path.basename(pfad)}: {z['mit_zeile']} Fotos mit Zeile, "
              f"{z['mit_gesicht']} mit Gesichtern ({z['gesichter']} Gesichter)")
        erkannt_zahl = max(erkannt_zahl, z["mit_zeile"])
        beste_mit_gesicht = max(beste_mit_gesicht, z["mit_gesicht"])
    if not dateien:
        print("  Keine Vektordateien gefunden.")

    zuordnung = os.path.join(args.basis, ZUORDNUNG)
    gruppiert = 0
    if os.path.isfile(zuordnung):
        g = zuordnung_zaehlen(zuordnung, fotos)
        gruppiert = g["mit_gruppe"]
        print(f"  Gruppen (gesicht_zuordnung.jsonl): {g['mit_gruppe']} Fotos an {g['gruppen']} Gruppen")
    else:
        print("  gesicht_zuordnung.jsonl fehlt")
    print("Befund: " + befund(len(fotos), erkannt_zahl, beste_mit_gesicht, gruppiert))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
