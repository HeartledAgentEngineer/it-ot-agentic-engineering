r"""Warum sind die Gruppen ab Platz ~20 gemischt? Nur Zahlen. (08.10.2026)

Anlass: Sebastian hat die 20 groessten Gruppen benannt; danach kamen Gruppen mit
gemischten Personen und Gegenstaenden. Zwei Verdachte, die dieses Werkzeug
gegeneinander misst, bevor irgendetwas neu gerechnet wird:

1. **Gedrehte Fotos** – die Erkennung lief bis ``ad4f09c`` auf doppelt gedrehten
   Bildern (EXIF-Orientierung != 1). Quelle: ``orientierung.jsonl`` aus
   ``orientierung_pruefen.py``.
2. **Niedrige Erkennungssicherheit** – als Gesicht zaehlt alles ab ``score``
   0,6 (``personen_cluster.MIN_SCORE``); Gegenstaende liegen oft darunter von 0,9.

Gelesen wird nur (``gesicht_zuordnung.jsonl`` der Gruppierung und
``orientierung.jsonl``), geschrieben wird nichts. Die Konsole zeigt nur Zahlen
und Gruppen-Kennungen (``Person_1003``) – keine Namen, keine Bild-IDs, keine
Koordinaten.

Aufruf (PowerShell, aus dem Projektordner ``personal_ai_agent``)::

    & .\backend\.venv\Scripts\python.exe tools\foto_sortierung\gruppen_diagnose.py
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import statistics
import sys

STANDARD_BASIS = os.path.join(os.path.expanduser("~"), "foto_sortierung")
STANDARD_ZUORDNUNG = os.path.join(STANDARD_BASIS, "personen_gruppen", "gesicht_zuordnung.jsonl")
STANDARD_ORIENTIERUNG = os.path.join(STANDARD_BASIS, "orientierung.jsonl")
SICHER = 0.9          # ab hier gilt ein Fund als sicheres Gesicht
KLEIN = 0.005         # Gesicht unter 0,5 % der Bildflaeche


def jsonl_lesen(pfad: str):
    """Zeilen einer JSONL-Datei als Dicts; kaputte Zeilen fallen weg."""
    with open(pfad, encoding="utf-8") as datei:
        for zeile in datei:
            try:
                daten = json.loads(zeile)
            except ValueError:
                continue
            if isinstance(daten, dict):
                yield daten


def orientierungen_lesen(pfad: str) -> dict:
    """``{bild_id: orientierung}``; fehlt die Datei, ist alles unbekannt."""
    if not os.path.isfile(pfad):
        return {}
    return {str(d.get("bild_id")): d["orientierung"] for d in jsonl_lesen(pfad)
            if isinstance(d.get("orientierung"), int)}


def merkmale(gesichter, orientierung: dict) -> dict:
    """Kennzahlen einer Menge von Gesichtern (nur Zahlen)."""
    n = len(gesichter)
    if not n:
        return {"gesichter": 0}
    fotos = [g for g in gesichter if not g.get("video_id")]
    bekannt = [g for g in fotos if str(g.get("bild_id")) in orientierung]
    gedreht = [g for g in bekannt if orientierung[str(g.get("bild_id"))] != 1]
    scores = [float(g["score"]) for g in gesichter if isinstance(g.get("score"), (int, float))]
    anteile = [float(g["anteil"]) for g in gesichter if isinstance(g.get("anteil"), (int, float))]
    return {
        "gesichter": n,
        "video": (n - len(fotos)) / n,
        "orientierung_bekannt": len(bekannt) / len(fotos) if fotos else 0.0,
        "gedreht": len(gedreht) / len(bekannt) if bekannt else None,
        "unsicher": sum(1 for s in scores if s < SICHER) / len(scores) if scores else None,
        "score_median": statistics.median(scores) if scores else None,
        "klein": sum(1 for a in anteile if a < KLEIN) / len(anteile) if anteile else None,
    }


def gruppen_bilden(zuordnung) -> tuple:
    """``(gruppen, rauschen)``: Gruppen nach Groesse absteigend, Rauschen = ohne Kennung."""
    je = collections.defaultdict(list)
    rauschen = []
    for g in zuordnung:
        (je[g["kennung"]] if g.get("kennung") else rauschen).append(g)
    reihe = sorted(je.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    return reihe, rauschen


def _p(wert) -> str:
    return "  -  " if wert is None else f"{100 * wert:4.0f} %"


def _s(wert) -> str:
    return " -  " if wert is None else f"{wert:.2f}"


def bericht(reihe, rauschen, orientierung, oben: int, zeigen: int) -> list:
    zeilen = []
    alle = [g for _, m in reihe for g in m]
    m_alle = merkmale(alle + rauschen, orientierung)
    zeilen.append(f"Gesichter: {len(alle) + len(rauschen)} · in Gruppen {len(alle)} · "
                  f"ohne Gruppe {len(rauschen)} · Gruppen {len(reihe)}")
    zeilen.append(f"Orientierung bekannt fuer {_p(m_alle['orientierung_bekannt']).strip()} "
                  "der Foto-Gesichter (Rest: orientierung_pruefen.py noch nicht fertig)")
    zeilen.append("")
    zeilen.append(f"{'Bereich':<22}{'Gesichter':>10}{'gedreht':>9}{'score<0.9':>11}"
                  f"{'Median':>8}{'klein':>8}{'Video':>8}")
    bereiche = [(f"Gruppen 1-{oben}", [g for _, m in reihe[:oben] for g in m]),
                (f"Gruppen {oben + 1}-Ende", [g for _, m in reihe[oben:] for g in m]),
                ("ohne Gruppe", rauschen)]
    for name, menge in bereiche:
        m = merkmale(menge, orientierung)
        if not m["gesichter"]:
            zeilen.append(f"{name:<22}{0:>10}")
            continue
        zeilen.append(f"{name:<22}{m['gesichter']:>10}{_p(m['gedreht']):>9}"
                      f"{_p(m['unsicher']):>11}{_s(m['score_median']):>8}"
                      f"{_p(m['klein']):>8}{_p(m['video']):>8}")
    zeilen.append("")
    zeilen.append(f"Einzelne Gruppen (Platz {oben - 4} bis {oben + zeigen}):")
    zeilen.append(f"{'Platz':>5}  {'Kennung':<13}{'Gesichter':>10}{'gedreht':>9}"
                  f"{'score<0.9':>11}{'Median':>8}{'klein':>8}")
    for platz, (kennung, m_liste) in enumerate(reihe, start=1):
        if platz < oben - 4 or platz > oben + zeigen:
            continue
        m = merkmale(m_liste, orientierung)
        zeilen.append(f"{platz:>5}  {kennung:<13}{m['gesichter']:>10}{_p(m['gedreht']):>9}"
                      f"{_p(m['unsicher']):>11}{_s(m['score_median']):>8}{_p(m['klein']):>8}")
    return zeilen


def main(argv=None) -> int:
    zerleger = argparse.ArgumentParser(description="Gruppen-Qualitaet messen (nur lesen, nur Zahlen).")
    zerleger.add_argument("--zuordnung", default=STANDARD_ZUORDNUNG)
    zerleger.add_argument("--orientierung", default=STANDARD_ORIENTIERUNG)
    zerleger.add_argument("--oben", type=int, default=20,
                          help="so viele groesste Gruppen gelten als 'gut' (Vergleich)")
    zerleger.add_argument("--zeigen", type=int, default=20,
                          help="so viele Gruppen nach Platz --oben einzeln zeigen")
    args = zerleger.parse_args(argv)
    if not os.path.isfile(args.zuordnung):
        print(f"Abbruch: Zuordnungsdatei nicht gefunden: {args.zuordnung}")
        return 1
    reihe, rauschen = gruppen_bilden(jsonl_lesen(args.zuordnung))
    for zeile in bericht(reihe, rauschen, orientierungen_lesen(args.orientierung),
                         max(1, args.oben), max(0, args.zeigen)):
        print(zeile)
    return 0


if __name__ == "__main__":
    sys.exit(main())
