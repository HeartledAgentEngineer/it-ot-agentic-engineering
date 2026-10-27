"""Messwerkzeug: Wo unterscheiden sich PC und Handy bei der Gesichtserkennung —
und wie viele Kaestchen zeigt das Detailbild? (15.10.2026)

Anlass: Auftrag „Gesichter im Detailbild bearbeiten" (Sebastian, 15.10.2026).
Dort steht unter Punkt 1: auf einem Familienfoto mit vier Personen wurde im
Bearbeitungsmodus **ein einziges** Gesicht eingerahmt, und darunter die
Arbeitsanweisung „Zu klaeren (belegt, nicht vermutet)":

* Mit welchen Einstellungen laeuft die Erkennung am Handy, wo stehen sie
  (Datei:Zeile)?
* Findet der PC auf demselben Bild mehr Gesichter?
* Warum findet das Handy weniger?

**Dieses Werkzeug misst die erste und die dritte Frage beantwortbare Haelfte.**
Es liest ausschliesslich Text-Dateien (Code) und die gespeicherte
Gesichtsdatei — es **oeffnet kein Bild**, ruft **kein Netz** und **kein Modell**,
**schreibt nichts**, gibt **keine Personennamen** und **keine Kennungen von
Personen** aus, sondern nur Zahlen und Datei:Zeile.

Gemessen wird:

* **Einstellungen beider Erkennungswege** aus dem echten Code, mit Datei:Zeile:
  Score-Schwelle, NMS-Schwelle, TopK und die tatsaechlich gesetzte
  Eingabegroesse des Detektors. Damit ist die naheliegende Vermutung
  „das Handy erkennt nur auf 320x320" pruefbar statt geraten.
* **Anzeige im Detailbild** aus dem echten Code, mit Datei:Zeile: welcher
  Endpunkt die Kaestchen liefert, welcher Dienst sie auswaehlt, welche Filter
  Gesichter verbergen — und wo der Editor genau EINEN Rahmen bekommt
  (Referenz-Nachbearbeitung) statt der ganzen Liste.
* **Zahlen am gespeicherten Bestand** (``gesicht_zuordnung.jsonl``): Gesichter
  je Bild, Bilder mit genau einem Gesicht, Rahmenbreiten, Scores. Das ist die
  Zahl hinter „nur ein Kaestchen".
* **Ein einzelnes Bild** (``--bild <kennung>``): wie viele Gesichter es im
  Bestand hat und wie viele davon die Anzeige verbirgt. Damit laesst sich das
  Familienfoto in Sekunden nachpruefen, sobald seine Kennung bekannt ist.

Aufruf (aus dem Projektordner ``personal_ai_agent``)::

    backend\\.venv\\Scripts\\python.exe tools\\foto_sortierung\\gesicht_wege_messen.py
    backend\\.venv\\Scripts\\python.exe tools\\foto_sortierung\\gesicht_wege_messen.py --bild 108041949695

Fehlt eine Datei, wird das ehrlich gemeldet — kein Abbruch, keine geratene Zahl.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import statistics
import sys
from pathlib import Path

PROJEKT = Path(__file__).resolve().parents[2]
FACE_INFER = PROJEKT / "backend" / "face_infer.py"
PC_WEG = PROJEKT / "tools" / "foto_sortierung" / "gesicht_erkennen.py"
ROUTER_GRUPPEN = PROJEKT / "backend" / "app" / "router" / "gruppen.py"
SERVICE_QUIZ = PROJEKT / "backend" / "app" / "services" / "gruppen_quiz.py"
FRONTEND = PROJEKT / "frontend" / "app.js"

STANDARD_ORDNER = Path.home() / "foto_sortierung"
STANDARD_ZUORDNUNG = "personen_gruppen/gesicht_zuordnung.jsonl"
# Diese beiden Dateien liegen (Stand 15.10.2026) NUR am Handy; fehlen sie am PC,
# werden die von der Anzeige verborgenen Gesichter ehrlich als „nicht zaehlbar"
# gemeldet statt geschaetzt.
AUSSCHLUSS_DATEI = "ausgeschlossen.json"
STAND_DATEINAME = "gruppen_quiz_stand.json"

# Grobe Aufloesung: unter dieser Rahmenbreite (Pixel) ist ein Ausschnitt klein
# (dieselbe Grenze, die der Rausch-Bericht „grob aufgeloest" nennt).
SCHMAL_PX = 64
SEHR_SCHMAL_PX = 32
SCORE_UNSICHER = 0.80


# ── Zahlenformat (deutsch, damit der Bericht lesbar bleibt) ──────────────────

def _zahl(wert) -> str:
    """Ganze Zahl mit Punkt als Tausendertrenner."""
    return f"{int(wert):,}".replace(",", ".")


def _komma(wert, stellen: int = 1) -> str:
    """Kommazahl mit deutschem Komma."""
    return f"{float(wert):.{stellen}f}".replace(".", ",")


def _anteil(teil, ganzes) -> str:
    if not ganzes:
        return "0,0 %"
    return _komma(100.0 * teil / ganzes, 1) + " %"


# ── Teil 1: Einstellungen beider Erkennungswege (aus dem echten Code) ────────

def code_zeilen(pfad: Path, muster: str) -> list:
    """Alle Zeilen einer Textdatei, die auf ``muster`` passen — als (Zeile, Text).

    Gibt bei fehlender Datei eine leere Liste zurueck (der Aufrufer meldet das).
    """
    if not pfad.is_file():
        return []
    treffer = []
    sucher = re.compile(muster)
    with open(pfad, encoding="utf-8", errors="replace") as datei:
        for nummer, zeile in enumerate(datei, start=1):
            if sucher.search(zeile):
                treffer.append((nummer, zeile.rstrip()))
    return treffer


def funktions_bereich(pfad: Path, start_muster: str, ende_muster: str = r"^def "):
    """Die Zeilen einer Funktion als (Nummer, Text) — ab ``start_muster`` bis zur
    naechsten Zeile, die auf ``ende_muster`` passt (Standard: naechstes ``def``).

    Damit lassen sich Treffer auf EINE Funktion begrenzen statt im ganzen Modul.
    """
    if not pfad.is_file():
        return []
    treffer, drin, sucher, ender = [], False, re.compile(start_muster), re.compile(ende_muster)
    with open(pfad, encoding="utf-8", errors="replace") as datei:
        for nummer, zeile in enumerate(datei, start=1):
            if not drin:
                if sucher.search(zeile):
                    drin = True
                else:
                    continue
            elif ender.search(zeile):
                break
            treffer.append((nummer, zeile.rstrip()))
    return treffer


def _konstante(pfad: Path, name: str):
    """Zahl aus einer Zuweisung ``NAME = 0.6`` lesen — (Wert, Zeile) oder None."""
    for nummer, zeile in code_zeilen(pfad, rf"^\s*{re.escape(name)}\s*="):
        rechts = zeile.split("=", 1)[1].strip()
        rechts = rechts.split("#")[0].strip()
        try:
            return float(rechts), nummer
        except ValueError:
            return rechts, nummer
    return None


def einstellungen_lesen(face_infer: Path = FACE_INFER, pc_weg: Path = PC_WEG) -> dict:
    """Die wirksamen Detektor-Einstellungen beider Wege, je mit Datei:Zeile."""
    return {
        "handy": {
            "pfad": str(face_infer),
            "da": face_infer.is_file(),
            "score": _konstante(face_infer, "SCORE_THR"),
            "nms": _konstante(face_infer, "NMS_THR"),
            "topk": _konstante(face_infer, "TOPK"),
            "bau": code_zeilen(face_infer, r"FaceDetectorYN\.create"),
            "eingabe": code_zeilen(face_infer, r"\.setInputSize\("),
            "detektion": code_zeilen(face_infer, r"^\s*ok, faces = det\.detect"),
        },
        "pc": {
            "pfad": str(pc_weg),
            "da": pc_weg.is_file(),
            "score": _konstante(pc_weg, "SCORE_SCHWELLE"),
            "nms": _konstante(pc_weg, "NMS_SCHWELLE"),
            "topk": _konstante(pc_weg, "TOPK"),
            "bau": code_zeilen(pc_weg, r"FaceDetectorYN\.create"),
            "eingabe": code_zeilen(pc_weg, r"\.setInputSize\("),
            "detektion": code_zeilen(pc_weg, r"^\s*_, rohgesichter = detektor\.detect"),
        },
    }


def einstellungen_gleich(einstellungen: dict) -> bool:
    """Score/NMS/TopK beider Wege gleich? (Vergleich der Zahlen, nicht der Texte.)"""
    a, b = einstellungen.get("handy") or {}, einstellungen.get("pc") or {}
    for feld in ("score", "nms", "topk"):
        wa, wb = a.get(feld), b.get(feld)
        if not wa or not wb:
            return False
        if float(wa[0]) != float(wb[0]):
            return False
    return True


def einstellungen_bericht(einstellungen: dict) -> list:
    """Berichtszeilen zu beiden Wegen (nur Zahlen und Datei:Zeile)."""
    zeilen = []
    for rolle, schluessel in (("Handy/Backend", "handy"), ("PC (Gesichterlauf)", "pc")):
        weg = einstellungen.get(schluessel) or {}
        if not weg.get("da"):
            zeilen.append(f"  {rolle}: Datei nicht gefunden ({weg.get('pfad')}) — nicht messbar")
            continue
        name = os.path.basename(weg["pfad"])
        teile = []
        for feld, beschriftung in (("score", "Score"), ("nms", "NMS"), ("topk", "TopK")):
            wert = weg.get(feld)
            if wert:
                gerundet = (f"{wert[0]:g}" if isinstance(wert[0], float) else str(wert[0]))
                teile.append(f"{beschriftung} {gerundet} ({name}:{wert[1]})")
        zeilen.append(f"  {rolle}: " + " · ".join(teile))
        for nummer, text in weg.get("eingabe") or []:
            anzeige = re.sub(r"\s+", " ", text.strip())[:90]
            zeilen.append(f"    gesetzte Eingabegroesse: {name}:{nummer} — {anzeige}")
        for nummer, text in weg.get("bau") or []:
            anzeige = re.sub(r"\s+", " ", text.strip())[:90]
            zeilen.append(f"    Detektor gebaut: {name}:{nummer} — {anzeige}")
        if not weg.get("eingabe"):
            zeilen.append(f"    Achtung: keine Zeile setInputSize gefunden — es gilt die "
                          f"Voreinstellung des Detektors")
    zeilen.append("  Vergleich: " + ("Score, NMS und TopK sind in BEIDEN Wegen gleich."
                                     if einstellungen_gleich(einstellungen)
                                     else "die Wege unterscheiden sich bei Score/NMS/TopK."))
    return zeilen


# ── Teil 2: Anzeige im Detailbild (aus dem echten Code) ─────────────────────

# Funktionen, in deren Rumpf die Filterzeilen der Detailbild-Auswahl stehen.
FILTER_FUNKTIONEN = (r"^def gesichter_auf_bild", r"^def _sicht_quellen", r"^def _bild_sicht")


def anzeige_orte(router: Path = ROUTER_GRUPPEN, service: Path = SERVICE_QUIZ,
                 frontend: Path = FRONTEND) -> list:
    """Die tragenden Code-Stellen der Anzeige, je (Datei, Zeile, Text)."""
    stellen = []
    for pfad, muster, was in (
        (router, r'@router\.get\("/bild-gesichter"\)', "Endpunkt GET /api/gruppen/bild-gesichter"),
        (router, r"gruppen_quiz\.gesichter_auf_bild", "Aufruf des Dienstes"),
        (service, r"^def gesichter_auf_bild", "Dienst, der die Kaestchen auswaehlt"),
        (frontend, r"zeigeBildVollbild\(imgEl, gesichter, opts\);", "Editor bekommt die LISTE "
                                                                  "(Quiz: alle Gesichter)"),
        (frontend, r"zeigeBildVollbild\(bild, \[gesicht\]", "Editor bekommt genau EINEN Rahmen "
                                                          "(Referenz-Nachbearbeitung)"),
    ):
        for nummer, text in code_zeilen(pfad, muster):
            stellen.append((os.path.relpath(pfad, PROJEKT).replace(os.sep, "/"), nummer,
                            re.sub(r"\s+", " ", text.strip())[:80], was))
    # Die Filter gelten in den Funktionen, die die Kaestchen eines Bildes auswaehlen
    # (nicht im ganzen Modul) — deshalb hier auf ihre Rumpfe begrenzt. Seit dem Bild-Editor
    # (B1, 26.10.2026) liegt die Auswahl in ``_bild_sicht`` (gemeinsame zusammengefuehrte Sicht
    # fuer bild-gesichter, "Bilder mit X" und Erzaehlen), ihre Quellen in ``_sicht_quellen``.
    rumpf = []
    for start in FILTER_FUNKTIONEN:
        rumpf.extend(funktions_bereich(service, start))
    for muster, was in (
        (r"ausgeschlossen_lesen\(\)|_stand_lesen\(\)", "gelesene Filterquellen"),
        (r"not in fremd|not in aus", "Filterzeile: verbirgt ausgeschlossene und "
                                     "„kenne ich nicht\""),
    ):
        for nummer, text in rumpf:
            if re.search(muster, text):
                stellen.append((os.path.relpath(service, PROJEKT).replace(os.sep, "/"), nummer,
                                re.sub(r"\s+", " ", text.strip())[:80], was))
    return stellen


def anzeige_bericht(stellen: list) -> list:
    zeilen = []
    if not stellen:
        return ["  Keine der erwarteten Code-Stellen gefunden — bitte von Hand nachsehen."]
    for datei, nummer, _text, was in stellen:
        zeilen.append(f"  {was}: {datei}:{nummer}")
    return zeilen


# ── Teil 3: Zahlen am gespeicherten Bestand ─────────────────────────────────

def bestand_lesen(pfad: Path) -> dict:
    """Gesichter je Bild und ihre Masse zaehlen — nur Zahlen, kein Inhalt.

    Liest die JSONL-Zeilen Zeile fuer Zeile; kaputte Zeilen werden gezaehlt,
    nicht geworfen. Verliert nie eine Datei aus dem Blick (Ausgabe enthaelt
    ``fehlt``), sondern meldet sie ehrlich.
    """
    ergebnis = {"fehlt": False, "pfad": str(pfad), "zeilen": 0, "kaputt": 0,
                "bilder": 0, "je_bild": collections.Counter(), "breiten": [],
                "scores": [], "ohne_gruppe": 0, "aus_video": 0, "ohne_masse": 0}
    if not pfad.is_file():
        ergebnis["fehlt"] = True
        return ergebnis
    with open(pfad, encoding="utf-8", errors="replace") as datei:
        for zeile in datei:
            zeile = zeile.strip()
            if not zeile:
                continue
            try:
                eintrag = json.loads(zeile)
            except ValueError:
                ergebnis["kaputt"] += 1
                continue
            if not isinstance(eintrag, dict):
                ergebnis["kaputt"] += 1
                continue
            ergebnis["zeilen"] += 1
            kennung = eintrag.get("bild_id")
            ergebnis["je_bild"][str(kennung)] += 1
            bbox = eintrag.get("bbox") or []
            if len(bbox) >= 4:
                try:
                    ergebnis["breiten"].append(float(bbox[2]))
                except (TypeError, ValueError):
                    ergebnis["ohne_masse"] += 1
            else:
                ergebnis["ohne_masse"] += 1
            try:
                ergebnis["scores"].append(float(eintrag.get("score")))
            except (TypeError, ValueError):
                pass
            if eintrag.get("kennung") in (None, "", "null"):
                ergebnis["ohne_gruppe"] += 1
            if eintrag.get("video_id"):
                ergebnis["aus_video"] += 1
    ergebnis["bilder"] = len(ergebnis["je_bild"])
    return ergebnis


def _quantil(werte: list, anteil: float) -> float:
    if not werte:
        return 0.0
    sortiert = sorted(werte)
    stelle = min(len(sortiert) - 1, max(0, int(len(sortiert) * anteil)))
    return sortiert[stelle]


def bestand_zahlen(zahlen: dict) -> dict:
    """Aus der Rohzaehlung die Berichtszahlen ableiten."""
    verteilung = zahlen.get("je_bild") or {}
    anzahl_bilder = {
        "genau_ein": sum(1 for n in verteilung.values() if n == 1),
        "genau_zwei": sum(1 for n in verteilung.values() if n == 2),
        "genau_drei": sum(1 for n in verteilung.values() if n == 3),
        "vier_oder_mehr": sum(1 for n in verteilung.values() if n >= 4),
        "groesstes": max(verteilung.values()) if verteilung else 0,
    }
    breiten = zahlen.get("breiten") or []
    scores = zahlen.get("scores") or []
    return {
        "gesichter": zahlen.get("zeilen", 0),
        "bilder": zahlen.get("bilder", 0),
        "kaputt": zahlen.get("kaputt", 0),
        "bilder_genau_ein": anzahl_bilder["genau_ein"],
        "bilder_genau_zwei": anzahl_bilder["genau_zwei"],
        "bilder_genau_drei": anzahl_bilder["genau_drei"],
        "bilder_vier_oder_mehr": anzahl_bilder["vier_oder_mehr"],
        "groesstes_bild": anzahl_bilder["groesstes"],
        "breite_median": statistics.median(breiten) if breiten else 0.0,
        "breite_p10": _quantil(breiten, 0.10),
        "breite_p90": _quantil(breiten, 0.90),
        "schmal": sum(1 for w in breiten if w < SCHMAL_PX),
        "sehr_schmal": sum(1 for w in breiten if w < SEHR_SCHMAL_PX),
        "ohne_masse": zahlen.get("ohne_masse", 0),
        "score_median": statistics.median(scores) if scores else 0.0,
        "score_unsicher": sum(1 for s in scores if s < SCORE_UNSICHER),
        "ohne_gruppe": zahlen.get("ohne_gruppe", 0),
        "aus_video": zahlen.get("aus_video", 0),
    }


def bestand_bericht(zahlen: dict, kennzahlen: dict) -> list:
    if zahlen.get("fehlt"):
        return [f"  Datei fehlt: {zahlen.get('pfad')} — Bestand nicht messbar"]
    zeilen = [
        f"  {_zahl(kennzahlen['gesichter'])} Gesichter auf "
        f"{_zahl(kennzahlen['bilder'])} Bildern"
        + (f" · {_zahl(kennzahlen['kaputt'])} unlesbare Zeilen" if kennzahlen["kaputt"] else ""),
        f"  Bilder mit genau einem Gesicht: {_zahl(kennzahlen['bilder_genau_ein'])}"
        f" ({_anteil(kennzahlen['bilder_genau_ein'], kennzahlen['bilder'])})"
        f" · zwei: {_zahl(kennzahlen['bilder_genau_zwei'])}"
        f" · drei: {_zahl(kennzahlen['bilder_genau_drei'])}"
        f" · vier oder mehr: {_zahl(kennzahlen['bilder_vier_oder_mehr'])}"
        f" · groesstes Bild: {_zahl(kennzahlen['groesstes_bild'])} Gesichter",
        f"  Rahmenbreite (px): Median {_komma(kennzahlen['breite_median'])}"
        f" · 10 % {_komma(kennzahlen['breite_p10'])}"
        f" · 90 % {_komma(kennzahlen['breite_p90'])}"
        f" · schmaler als {SCHMAL_PX} px: {_zahl(kennzahlen['schmal'])}"
        f" ({_anteil(kennzahlen['schmal'], kennzahlen['gesichter'])})"
        f" · schmaler als {SEHR_SCHMAL_PX} px: {_zahl(kennzahlen['sehr_schmal'])}",
        f"  Score: Median {_komma(kennzahlen['score_median'], 3)}"
        f" · unter {_komma(SCORE_UNSICHER, 2)}: {_zahl(kennzahlen['score_unsicher'])}"
        f" ({_anteil(kennzahlen['score_unsicher'], kennzahlen['gesichter'])})",
        f"  ohne Gruppe: {_zahl(kennzahlen['ohne_gruppe'])}"
        f" · aus Videos: {_zahl(kennzahlen['aus_video'])}"
        + (f" · ohne Masse: {_zahl(kennzahlen['ohne_masse'])}"
           if kennzahlen["ohne_masse"] else ""),
    ]
    return zeilen


# ── Teil 4: ein einzelnes Bild (die Nachpruefung des Familienfotos) ─────────

def bild_zaehlen(pfad: Path, kennung: str, ausgeschlossen: set = None,
                 fremd: set = None) -> dict:
    """Gesichter EINES Bildes zaehlen und wie viele die Anzeige verbirgt.

    ``ausgeschlossen`` = Gesichts-Kennungen, die der Nutzer weggenommen hat;
    ``fremd`` = Gruppen, die als „kenne ich nicht" markiert sind. Fehlen die
    Listen (sie liegen am Handy), bleibt ``verborgen`` ehrlich ``None``.
    """
    ergebnis = {"bild": str(kennung), "gesichter": 0, "ohne_gruppe": 0,
                "verborgen": None, "schmal": 0, "unsicher": 0,
                "breiten": [], "kaputt": 0, "datei_fehlt": False, "namen": []}
    if not pfad.is_file():
        ergebnis["datei_fehlt"] = True
        return ergebnis
    ausgeschlossen = set(ausgeschlossen or ())
    fremd = set(fremd or ())
    zaehlbar = ausgeschlossen or fremd
    verborgen = 0 if zaehlbar else None
    with open(pfad, encoding="utf-8", errors="replace") as datei:
        for zeile in datei:
            zeile = zeile.strip()
            if not zeile:
                continue
            try:
                eintrag = json.loads(zeile)
            except ValueError:
                ergebnis["kaputt"] += 1
                continue
            if not isinstance(eintrag, dict):
                ergebnis["kaputt"] += 1
                continue
            if str(eintrag.get("bild_id")) != str(kennung):
                continue
            ergebnis["gesichter"] += 1
            gruppe = eintrag.get("kennung")
            if gruppe in (None, "", "null"):
                ergebnis["ohne_gruppe"] += 1
            bbox = eintrag.get("bbox") or []
            if len(bbox) >= 4:
                try:
                    breite = float(bbox[2])
                    ergebnis["breiten"].append(breite)
                    if breite < SCHMAL_PX:
                        ergebnis["schmal"] += 1
                except (TypeError, ValueError):
                    pass
            try:
                if float(eintrag.get("score")) < SCORE_UNSICHER:
                    ergebnis["unsicher"] += 1
            except (TypeError, ValueError):
                pass
            if verborgen is not None:
                gid = str(eintrag.get("gid") or "")
                if gid and gid in ausgeschlossen:
                    verborgen += 1
                elif gruppe not in (None, "", "null") and str(gruppe) in fremd and gid not in ausgeschlossen:
                    verborgen += 1
    ergebnis["verborgen"] = verborgen
    return ergebnis


def bild_bericht(zahlen: dict) -> list:
    if zahlen.get("datei_fehlt"):
        return [f"  Datei fehlt — Bild nicht nachpruefbar"]
    zeilen = [
        f"  Bild {zahlen['bild']}: {_zahl(zahlen['gesichter'])} Gesichter im Bestand"
        f" · davon ohne Gruppe: {_zahl(zahlen['ohne_gruppe'])}",
        f"  Rahmenbreite: " + ("keine" if not zahlen["breiten"] else
                               f"schmalste {_komma(min(zahlen['breiten']))} px · "
                               f"breiteste {_komma(max(zahlen['breiten']))} px")
        + f" · schmaler als {SCHMAL_PX} px: {_zahl(zahlen['schmal'])}"
        + f" · Score unter {_komma(SCORE_UNSICHER, 2)}: {_zahl(zahlen['unsicher'])}",
    ]
    if zahlen.get("verborgen") is None:
        zeilen.append("  Von der Anzeige verborgene Gesichter: NICHT zaehlbar — die Filterlisten "
                      "(ausgeschlossen, gruppen_quiz_stand) liegen nur am Handy.")
    else:
        sichtbar = zahlen["gesichter"] - zahlen["verborgen"]
        zeilen.append(f"  Von der Anzeige verborgene Gesichter: {_zahl(zahlen['verborgen'])}"
                      f" · sichtbar: {_zahl(max(0, sichtbar))}")
    return zeilen


# ── Bericht / Kommandozeile ────────────────────────────────────────────────

def bericht(zuordnung: Path, face_infer: Path = FACE_INFER, pc_weg: Path = PC_WEG,
            bilder=()) -> list:
    """Alle Berichtszeilen bauen (Generator-frei, damit leicht pruefbar)."""
    zeilen = ["Gesichtserkennung: Wege und Anzeige (nur gelesen, nur Zahlen)", ""]

    einstellungen = einstellungen_lesen(face_infer, pc_weg)
    zeilen.append("Einstellungen der beiden Erkennungswege (aus dem Code, Datei:Zeile)")
    zeilen += einstellungen_bericht(einstellungen)
    zeilen.append("")

    zeilen.append("Anzeige der Kaestchen im Detailbild (aus dem Code, Datei:Zeile)")
    zeilen += anzeige_bericht(anzeige_orte())
    zeilen.append("")

    zahlen = bestand_lesen(zuordnung)
    kennzahlen = bestand_zahlen(zahlen)
    zeilen.append(f"Bestand ({zuordnung})")
    zeilen += bestand_bericht(zahlen, kennzahlen)
    zeilen.append("")

    if bilder:
        zeilen.append("Einzelne Bilder (Nachpruefung)")
        for kennung in bilder:
            zeilen += bild_bericht(bild_zaehlen(zuordnung, kennung))
        zeilen.append("")
    return zeilen


def main(argv=None) -> int:
    zerleger = argparse.ArgumentParser(
        description="Erkennungswege und Kaestchen der Gesichts-Anzeige messen "
                    "(nur lesen, nur Zahlen, nichts schreiben).")
    zerleger.add_argument("--zuordnung", default=str(STANDARD_ORDNER / STANDARD_ZUORDNUNG),
                          help="Pfad der gesicht_zuordnung.jsonl (Standard: ~/foto_sortierung)")
    zerleger.add_argument("--face-infer", default=str(FACE_INFER),
                          help="Pfad des Handy-Wegs (backend/face_infer.py)")
    zerleger.add_argument("--pc-weg", default=str(PC_WEG),
                          help="Pfad des PC-Wegs (tools/foto_sortierung/gesicht_erkennen.py)")
    zerleger.add_argument("--bild", nargs="*", default=None,
                          help="Bildkennung(en), die einzeln nachgezaehlt werden sollen")
    args = zerleger.parse_args(argv)

    for zeile in bericht(Path(args.zuordnung), Path(args.face_infer), Path(args.pc_weg),
                         tuple(args.bild or ())):
        print(zeile)
    return 0


if __name__ == "__main__":
    sys.exit(main())
