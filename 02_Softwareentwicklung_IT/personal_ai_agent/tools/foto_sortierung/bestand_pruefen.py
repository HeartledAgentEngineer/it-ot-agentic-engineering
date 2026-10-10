"""Bestand pruefen — unabhaengiger Nachweis in Zahlen (01.10.2026).

Warum:
  Sebastian will nicht glauben muessen, was ein Agent ueber die Nachtlaeufe
  meldet („ist wirklich alles beschrieben, sind alle Gesichter fertig und
  gruppiert?"). Dieses Werkzeug zaehlt selbst nach — nur lesend, nur Zahlen.

Was verglichen wird (je Sortierplan, Fotos und Videos getrennt):
  * Gesichter Fotos:  Plan-Fotos  <->  Zeilen in den Vektordateien (``bild_id``)
  * Gesichter Videos: Plan-Videos <->  ``*.videos_fertig`` + Video-Vektorzeilen
  * Beschreibungen:   Plan-Fotos  <->  jede Beschreibungsdatei ueber ``fileid``;
                      Standard sind ``bild_beschreibungen.jsonl`` (Altspeicher),
                      ``bild_beschreibungen_papa_reich.jsonl`` (Papas Fotos,
                      reiche Fassung — eigener Lauf, weil Papas Plan andere
                      Feldnamen traegt), ``bild_beschreibungen_reich.jsonl``
                      (reiche Fassung der Sammlung) und
                      ``bild_beschreibungen_rest_reich.jsonl`` (Nachzuegler).
                      Die frueher gemeldeten 3 + 5 Luecken der Einzelplaene sind
                      in Wahrheit versorgt — nur eine Deckung ueber ALLE Quellen
                      sagt, ob wirklich ein Foto fehlt.
  * Gesamtplan:       ``sortierplan_reich_gesamt.json`` (Union aller Plaene)
                      <->  alle Beschreibungsdateien zusammen. Beantwortet die
                      Frage „ist der ganze Bestand beschrieben?" in einer Zeile;
                      der Plan mischt die Feldnamen (``von_name`` bei Sammlung/
                      Sortierplan, ``name`` bei Papas Plan) — hier wird deshalb
                      wie im Beschreibungs-Werkzeug BEIDE Formen gelesen.
                      Fehlende Fotos werden nicht nur gezaehlt, sondern mit
                      Kennung und Grund benannt (``--luecken-details``, Standard
                      20): ``keine Vektorzeile`` (kein Gesichtslauf), ``ohne
                      Bildmasse`` (Vektorzeile ohne Breite/Hoehe — das Bild war
                      beim Beschreibungslauf nicht ladbar) oder ``Bild geladen,
                      kein Beschreibungseintrag`` (offener Rest). Zusaetzlich
                      wird vermerkt, wenn derselbe Dateiname im Plan mehrfach
                      vorkommt (Dublette, nur die Zahl — nie der Name).
  * Gruppen:          ``personen_gruppen/personen_beispiele.json`` und
                      ``gesicht_zuordnung.jsonl`` (fehlen sie, lief der
                      Gruppierer nur trocken) — mit Abdeckung: wie viele der
                      groessten Gruppen enthalten 50/80/90 % aller Gesichter.
  * Orte (OSM):       ``bild_orte.csv`` (eine Zeile je Bild, aus den
                      OpenStreetMap-Karten) — Zeilen, Bilder mit/ohne GPS,
                      Bilder im Flug, mit Ortsname/Landmarke/Strasse/Hausnummer,
                      dazu die Zahl der ausgewerteten Kartengebiete
                      (``osm/csv/<gebiet>``). Damit ist der Karten-Zweig
                      (Schritt 3c der Papas-Kette) genauso nachpruefbar wie die
                      uebrigen Stufen — er stand bisher in KEINEM Nachweis.
                      Nur Zahlen: keine Ortsnamen, keine Koordinaten.
  Standard-Plaene: ``sortierplan.json``, ``sortierplan_bildervideos.json`` und
  ``sortierplan_papa.json`` (Papas 6.336 Amazon-Fotos); Standard-Vektordateien
  entsprechend inkl. ``personen_vektoren_papa.jsonl``. Ohne Papa in dieser Liste
  blieb sein ganzer Bestand ungeprueft — die fruehere Annahme „erkennt Papa
  ueber die Kennungen automatisch\" traf nicht zu (Befund 10.10.2026).
  Jede Vektor-/Beschreibungsdatei wird ueber die Kennungen SELBST den Plaenen
  zugeordnet — es kommt nicht darauf an, welche Datei zu welchem Plan gehoert.
  Kennungen werden immer als Text verglichen (Plaene: Zahl, Vektorzeilen: Text).

Ausgabe: nur Zaehlungen und Dateinamen (ohne Pfad). Keine Namen, keine
Beschreibungen, keine Koordinaten, keine Vektoren. Es wird nichts geschrieben.

Aufruf:
    python tools/foto_sortierung/bestand_pruefen.py
    python tools/foto_sortierung/bestand_pruefen.py --basis D:/foto_sortierung
Exit-Code 0 (Bericht), 2 = Basisordner fehlt.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

STANDARD_BASIS = os.path.join(os.path.expanduser("~"), "foto_sortierung")
# Papas Plan traegt die Feldnamen name/ordner und fehlte hier ganz — sein
# Bestand (6.336 Fotos) blieb damit ungeprueft (Befund 10.10.2026).
STANDARD_PLAENE = ("sortierplan.json", "sortierplan_bildervideos.json", "sortierplan_papa.json")
STANDARD_FOTO_VEKTOREN = ("personen_vektoren_n0929_voll.jsonl",
                          "personen_vektoren_n0929_bildervideos.jsonl",
                          "personen_vektoren_papa.jsonl")
STANDARD_VIDEO_VEKTOREN = ("video_vektoren_bildervideos.jsonl", "video_vektoren_upload.jsonl")
# Mehrere Beschreibungsquellen: Altspeicher, Papas reiche Fassung (eigener
# Lauf, eigene Datei — der Altspeicher enthaelt Papa nicht), die reiche Fassung
# der Sammlung und der Nachzuegler-Lauf.
STANDARD_BESCHREIBUNGEN = ("bild_beschreibungen.jsonl", "bild_beschreibungen_papa_reich.jsonl",
                           "bild_beschreibungen_reich.jsonl", "bild_beschreibungen_rest_reich.jsonl")
# Union aller Plaene — die einzige Stelle, an der sich „ist wirklich jedes Foto
# beschrieben?" fuer den GESAMTEN Bestand ablesen laesst (10.10.2026).
STANDARD_GESAMTPLAN = "sortierplan_reich_gesamt.json"
# Eine Zeile je Bild, aus den OSM-Karten (orte_aus_karte.py --zuordnen).
STANDARD_BILD_ORTE = "bild_orte.csv"
# Je Gebiet ein Unterordner mit osm_orte.csv + osm_adressen.csv.
KARTEN_CSV_ORDNER = os.path.join("osm", "csv")
KARTEN_ORTE = "osm_orte.csv"
KARTEN_ADRESSEN = "osm_adressen.csv"
GRUPPEN_ORDNER = "personen_gruppen"
VIDEO_ENDUNGEN = (".mp4", ".mov", ".3gp", ".mkv", ".avi", ".m4v")
FERTIG_ENDUNG = ".videos_fertig"


# ── Lesen (nur lesend, nie ein Wurf bei kaputten Zeilen) ─────────────────────

def _kennung(wert: Any) -> str:
    if isinstance(wert, bool) or wert is None:
        return ""
    return str(wert).strip()


def plan_lesen(pfad: str) -> Dict[str, Any]:
    """-> {"fotos": set, "videos": set, "ohne_name": int, "eintraege": int} oder fehlt."""
    if not os.path.isfile(pfad):
        return {"fehlt": True}
    try:
        with open(pfad, encoding="utf-8") as datei:
            daten = json.load(datei)
    except (OSError, ValueError) as problem:
        return {"fehlt": True, "fehler": problem.__class__.__name__}
    zuege = daten.get("zuege") if isinstance(daten, dict) else daten
    fotos: Set[str] = set()
    videos: Set[str] = set()
    eintraege = 0
    for zug in zuege if isinstance(zuege, list) else []:
        if not isinstance(zug, dict):
            continue
        k = _kennung(zug.get("fileid"))
        if not k:
            continue
        eintraege += 1
        name = zug.get("von_name") or zug.get("name") or ""
        if isinstance(name, str) and name.strip().lower().endswith(VIDEO_ENDUNGEN):
            videos.add(k)
        else:
            fotos.add(k)
    return {"fotos": fotos, "videos": videos, "eintraege": eintraege}


def _jsonl(pfad: str) -> Iterable[Optional[dict]]:
    with open(pfad, encoding="utf-8", errors="replace") as datei:
        for zeile in datei:
            if not zeile.strip():
                continue
            try:
                obj = json.loads(zeile)
            except ValueError:
                yield None
                continue
            yield obj if isinstance(obj, dict) else None


def masse_da(zeile: dict) -> bool:
    """Traegt die Vektorzeile echte Bildmasse?

    0 oder fehlend heisst: das Bild war beim Lauf nicht ladbar (keine Vorschau
    in pCloud, defekte Datei). Genau diese Zeilen erklaeren einen Teil der
    fehlenden Beschreibungen — deshalb wird das je Bild festgehalten.
    """
    def zahl(wert: Any) -> int:
        try:
            return int(wert or 0)
        except (TypeError, ValueError):
            return 0
    return zahl(zeile.get("breite")) > 0 and zahl(zeile.get("hoehe")) > 0


def foto_vektoren_lesen(pfad: str) -> Dict[str, Any]:
    """Foto-Vektorzeilen zaehlen: Bilder, Fehler, Bilder mit Gesicht, Gesichter."""
    if not os.path.isfile(pfad):
        return {"fehlt": True}
    bilder: Set[str] = set()
    mit_gesicht: Set[str] = set()
    mit_fehler: Set[str] = set()
    mit_massen: Set[str] = set()
    gesichter = kaputt = doppelt = video_zeilen = 0
    for z in _jsonl(pfad):
        if z is None:
            kaputt += 1
            continue
        k = _kennung(z.get("bild_id"))
        if not k:
            kaputt += 1
            continue
        if "#t=" in k:
            video_zeilen += 1
            continue
        if k in bilder:
            doppelt += 1
        bilder.add(k)
        g = z.get("gesichter") if isinstance(z.get("gesichter"), list) else []
        if z.get("fehler"):
            mit_fehler.add(k)
        if masse_da(z):
            mit_massen.add(k)
        if g:
            mit_gesicht.add(k)
            gesichter += len(g)
    return {"bilder": bilder, "mit_gesicht": mit_gesicht, "mit_fehler": mit_fehler,
            "mit_massen": mit_massen, "gesichter": gesichter, "kaputt": kaputt,
            "doppelt": doppelt, "video_zeilen": video_zeilen}


def video_vektoren_lesen(pfad: str) -> Dict[str, Any]:
    """Fertige Videos: Fortschrittsdatei + Video-ids aus den Standbild-Zeilen."""
    fertig: Set[str] = set()
    mit_zeilen: Set[str] = set()
    gesichter = 0
    vorhanden = False
    if os.path.isfile(pfad + FERTIG_ENDUNG):
        vorhanden = True
        with open(pfad + FERTIG_ENDUNG, encoding="utf-8", errors="replace") as datei:
            fertig.update(_kennung(z) for z in datei if _kennung(z))
    if os.path.isfile(pfad):
        vorhanden = True
        for z in _jsonl(pfad):
            if z is None:
                continue
            k = _kennung(z.get("bild_id"))
            if "#t=" in k:
                mit_zeilen.add(k.split("#t=", 1)[0])
                g = z.get("gesichter")
                gesichter += len(g) if isinstance(g, list) else 0
    if not vorhanden:
        return {"fehlt": True}
    return {"fertig": fertig | mit_zeilen, "mit_gesicht": mit_zeilen, "gesichter": gesichter}


def beschreibungen_lesen(pfad: str) -> Dict[str, Any]:
    if not os.path.isfile(pfad):
        return {"fehlt": True}
    kennungen: Set[str] = set()
    zeilen = kaputt = leer = 0
    kosten = 0.0
    for z in _jsonl(pfad):
        if z is None:
            kaputt += 1
            continue
        zeilen += 1
        k = _kennung(z.get("fileid"))
        if not k:
            kaputt += 1
            continue
        if not str(z.get("beschreibung") or "").strip():
            leer += 1
            continue
        kennungen.add(k)
        try:
            kosten += float(z.get("kosten_usd") or 0)
        except (TypeError, ValueError):
            pass
    return {"kennungen": kennungen, "zeilen": zeilen, "kaputt": kaputt, "leer": leer,
            "kosten": kosten}


def gesamtplan_lesen(pfad: str) -> Dict[str, Any]:
    """Union-Plan lesen: Fotos, Videos, Eintraege ohne Namen, ohne Kennung.

    Der Gesamtplan mischt die Feldnamen der Quell-Plaene (``von_name``/
    ``von_ordner`` bei Sammlung und Sortierplan, ``name``/``ordner`` bei Papas
    Plan). Wer nur ``von_name`` liest, verliert Papas 6.336 Fotos still — genau
    der Fehler vom 10.10.2026 (Changelog union-plan-feldnamen). Hier wird
    deshalb wie im Beschreibungs-Werkzeug BEIDE Formen gelesen; Eintraege ohne
    Namen (z. B. Fotobuch-Scans) und ohne Kennung werden gezaehlt, nicht
    verschluckt.
    """
    if not os.path.isfile(pfad):
        return {"fehlt": True}
    try:
        with open(pfad, encoding="utf-8") as datei:
            daten = json.load(datei)
    except (OSError, ValueError) as problem:
        return {"fehlt": True, "fehler": problem.__class__.__name__}
    zuege = daten.get("zuege") if isinstance(daten, dict) else daten
    zuege = zuege if isinstance(zuege, list) else []
    fotos: Set[str] = set()
    videos: Set[str] = set()
    ohne_namen = ohne_kennung = 0
    namen: Dict[str, Set[str]] = {}
    for zug in zuege:
        if not isinstance(zug, dict):
            continue
        k = _kennung(zug.get("fileid"))
        if not k:
            ohne_kennung += 1
            continue
        name = zug.get("von_name") or zug.get("name") or ""
        if not (isinstance(name, str) and name.strip()):
            ohne_namen += 1
            continue
        namen.setdefault(name.strip().lower(), set()).add(k)
        (videos if name.strip().lower().endswith(VIDEO_ENDUNGEN) else fotos).add(k)
    # Kennungen, deren Dateiname im Plan mehrfach vorkommt = Dubletten-Kandidaten
    # (derselbe Name in zwei Ordnern, zwei verschiedene fileids). Nur die Zahl
    # bzw. die Kennungen werden gemeldet, nie der Name selbst.
    namen_doppelt: Set[str] = set()
    for kennungen in namen.values():
        if len(kennungen) > 1:
            namen_doppelt |= kennungen
    return {"eintraege": len(zuege), "fotos": fotos, "videos": videos,
            "ohne_namen": ohne_namen, "ohne_kennung": ohne_kennung,
            "namen_doppelt": namen_doppelt}


def luecken_details(fehlende: Iterable[str], alle_bilder: Set[str], mit_massen: Set[str],
                    namen_doppelt: Optional[Set[str]] = None,
                    max_kennungen: int = 20) -> Tuple[List[str], Dict[str, int]]:
    """Fehlende Fotos mit Kennung und Grund benennen statt nur zu zaehlen.

    Gruende (mechanisch aus den vorhandenen Dateien abgeleitet, nichts geraten):
      * ``keine Vektorzeile``  — kein Gesichtslauf/keine Zeile fuer dieses Bild
      * ``ohne Bildmasse``     — Vektorzeile ohne Breite/Hoehe: das Bild war
                                 nicht ladbar (keine Vorschau, defekte Datei)
      * ``Bild geladen``       — Zeile mit Massen da, aber kein
                                 Beschreibungseintrag (offener Rest)
    Dazu der Hinweis ``Name mehrfach im Plan`` (Dublette), wenn derselbe
    Dateiname bei mehreren Kennungen steht — es wird nur die Kennung genannt,
    nie der Name selbst.

    -> (Zeilen, Zaehler je Grund)
    """
    namen_doppelt = namen_doppelt or set()
    liste = sorted(fehlende)
    zaehler = {"ohne_vektorzeile": 0, "ohne_masse": 0, "kein_eintrag": 0, "name_doppelt": 0}
    zeilen: List[str] = []
    for k in liste:
        if k not in alle_bilder:
            grund = "keine Vektorzeile (kein Gesichtslauf fuer dieses Bild)"
            zaehler["ohne_vektorzeile"] += 1
        elif k not in mit_massen:
            grund = "ohne Bildmasse (Bild nicht ladbar, keine Vorschau)"
            zaehler["ohne_masse"] += 1
        else:
            grund = "Bild geladen, kein Beschreibungseintrag"
            zaehler["kein_eintrag"] += 1
        if k in namen_doppelt:
            grund += "; Name mehrfach im Plan (Dublette)"
            zaehler["name_doppelt"] += 1
        if max_kennungen and len(zeilen) < max_kennungen:
            zeilen.append(f"    {k}: {grund}")
    if max_kennungen and len(liste) > max_kennungen:
        zeilen.append(f"    ... und {_z(len(liste) - max_kennungen)} weitere")
    return zeilen, zaehler


def _grund_zeile(zaehler: Dict[str, int]) -> str:
    return ("Ursachen: " + _z(zaehler["ohne_vektorzeile"]) + " ohne Vektorzeile, "
            + _z(zaehler["ohne_masse"]) + " ohne Bildmasse, "
            + _z(zaehler["kein_eintrag"]) + " ohne Beschreibungseintrag; "
            + _z(zaehler["name_doppelt"]) + " mit mehrfach vorkommendem Namen")


def abdeckung(groessen: List[int], anteile=(0.5, 0.8, 0.9)) -> Dict[float, int]:
    """Wie viele der groessten Gruppen braucht es fuer 50/80/90 % aller Gesichter?"""
    sortiert = sorted((g for g in groessen if g > 0), reverse=True)
    gesamt = sum(sortiert)
    ergebnis: Dict[float, int] = {}
    if not gesamt:
        return {a: 0 for a in anteile}
    summe = 0
    offen = list(anteile)
    for i, g in enumerate(sortiert, 1):
        summe += g
        while offen and summe >= offen[0] * gesamt:
            ergebnis[offen.pop(0)] = i
    return ergebnis


def gruppen_lesen(basis: str) -> Dict[str, Any]:
    ordner = os.path.join(basis, GRUPPEN_ORDNER)
    beispiele = os.path.join(ordner, "personen_beispiele.json")
    zuordnung = os.path.join(ordner, "gesicht_zuordnung.jsonl")
    if not os.path.isfile(beispiele):
        return {"fehlt": True}
    try:
        with open(beispiele, encoding="utf-8") as datei:
            daten = json.load(datei)
    except (OSError, ValueError) as problem:
        return {"fehlt": True, "fehler": problem.__class__.__name__}
    gruppen = [g for g in (daten.get("gruppen") or []) if isinstance(g, dict)]
    groessen = [int(g.get("groesse") or 0) for g in gruppen]
    erg: Dict[str, Any] = {
        "stand": str(daten.get("stand") or "?"), "gruppen": len(gruppen),
        "gesichter_in_gruppen": sum(groessen), "abdeckung": abdeckung(groessen),
        "ab_50": sum(1 for g in groessen if g >= 50), "ab_10": sum(1 for g in groessen if g >= 10),
        "unter_10": sum(1 for g in groessen if g < 10),
        "mit_zwilling": sum(1 for g in gruppen if g.get("zwilling_kandidaten")),
        "benannt": sum(1 for g in gruppen if g.get("name")),
    }
    if os.path.isfile(zuordnung):
        zeilen = mit = 0
        for z in _jsonl(zuordnung):
            if z is None:
                continue
            zeilen += 1
            mit += 1 if z.get("kennung") else 0
        erg.update(zuordnung_zeilen=zeilen, zuordnung_mit_gruppe=mit)
    return erg


# ── Orte (OpenStreetMap) ────────────────────────────────────────────────────

def orte_lesen(pfad: str) -> Dict[str, Any]:
    """``bild_orte.csv`` zaehlen — eine Zeile je Bild, nur Zahlen.

    Der Zuordner schreibt je Bild eine Zeile. Ohne GPS steht dort ehrlich
    ``ohne GPS`` (Bild bleibt drin, statt weggelassen); Bilder aus dem Flugzeug
    tragen die Art ``flug``. Gezaehlt werden nur Zahlen — keine Ortsnamen,
    keine Strassen, keine Koordinaten.
    """
    if not os.path.isfile(pfad):
        return {"fehlt": True}
    zeilen = mit_gps = ohne_gps = flug = 0
    mit_ort = mit_landmarke = mit_strasse = mit_hausnummer = 0
    kaputt = 0
    try:
        with open(pfad, encoding="utf-8-sig", newline="") as datei:
            for satz in csv.DictReader(datei):
                if not isinstance(satz, dict):
                    kaputt += 1
                    continue
                zeilen += 1
                art = (satz.get("landmarke_art") or "").strip().lower()
                hinweis = (satz.get("hinweise") or "").strip().lower()
                if art == "flug":
                    flug += 1
                elif hinweis == "ohne gps":
                    ohne_gps += 1
                else:
                    mit_gps += 1
                if (satz.get("ort_osm") or "").strip():
                    mit_ort += 1
                if (satz.get("landmarke") or "").strip():
                    mit_landmarke += 1
                if (satz.get("adresse") or "").strip():
                    mit_strasse += 1
                if (satz.get("hausnummer") or "").strip():
                    mit_hausnummer += 1
    except (OSError, csv.Error, UnicodeDecodeError) as problem:
        return {"fehlt": True, "fehler": problem.__class__.__name__}
    return {"zeilen": zeilen, "mit_gps": mit_gps, "ohne_gps": ohne_gps,
            "flug": flug, "mit_ort": mit_ort, "mit_landmarke": mit_landmarke,
            "mit_strasse": mit_strasse, "mit_hausnummer": mit_hausnummer,
            "kaputt": kaputt}


def karten_gebiete(ordner: str) -> int:
    """Wie viele Kartengebiete haben beide Tabellen (Orte UND Adressen)?

    Je Gebiet ein Unterordner ``osm/csv/<name>``. Ein Gebiet zaehlt nur, wenn
    BEIDE Tabellen da sind — eine halbe Auswertung ist keine fertige.
    """
    if not os.path.isdir(ordner):
        return 0
    anzahl = 0
    for eintrag in sorted(os.listdir(ordner)):
        pfad = os.path.join(ordner, eintrag)
        if (os.path.isdir(pfad) and os.path.isfile(os.path.join(pfad, KARTEN_ORTE))
                and os.path.isfile(os.path.join(pfad, KARTEN_ADRESSEN))):
            anzahl += 1
    return anzahl


def tabellen_zeilen(pfad: str) -> int:
    """Datenzeilen einer Gesamttabelle (ohne Kopfzeile); 0 wenn sie fehlt."""
    if not os.path.isfile(pfad):
        return 0
    anzahl = 0
    with open(pfad, encoding="utf-8-sig", errors="replace") as datei:
        for _ in datei:
            anzahl += 1
    return max(0, anzahl - 1)


# ── Bericht ─────────────────────────────────────────────────────────────────

def _z(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _anteil(teil: int, ganz: int) -> str:
    return f"{(100.0 * teil / ganz):.1f} %".replace(".", ",") if ganz else "–"


def _usd(betrag: float) -> str:
    """USD mit Komma — nur die Zahl, nie der Dateiname (der traegt einen Punkt)."""
    return f"{betrag:.2f}".replace(".", ",")


def pruefen(basis: str, plaene=STANDARD_PLAENE, foto_vektoren=STANDARD_FOTO_VEKTOREN,
            video_vektoren=STANDARD_VIDEO_VEKTOREN,
            beschreibungen=STANDARD_BESCHREIBUNGEN,
            gesamtplan: Optional[str] = STANDARD_GESAMTPLAN,
            bild_orte: Optional[str] = STANDARD_BILD_ORTE,
            luecken_details_max: int = 20) -> Tuple[List[str], List[str]]:
    """-> (Berichtszeilen, Luecken). Nur Zahlen, Kennungen und Dateinamen.

    ``luecken_details_max`` = wie viele fehlende Fotos der Gesamtplan mit
    Kennung und Grund benennt (0 = nur zaehlen, wie frueher).
    """
    zeilen: List[str] = ["Bestandspruefung Fotos - nur Zahlen, nur lesend", ""]
    luecken: List[str] = []

    fv = {n: foto_vektoren_lesen(os.path.join(basis, n)) for n in foto_vektoren}
    vv = {n: video_vektoren_lesen(os.path.join(basis, n)) for n in video_vektoren}
    bq = {n: beschreibungen_lesen(os.path.join(basis, n)) for n in beschreibungen}
    alle_bilder: Set[str] = set().union(*(d["bilder"] for d in fv.values() if not d.get("fehlt")))
    mit_gesicht: Set[str] = set().union(*(d["mit_gesicht"] for d in fv.values() if not d.get("fehlt")))
    mit_fehler: Set[str] = set().union(*(d["mit_fehler"] for d in fv.values() if not d.get("fehlt")))
    mit_massen: Set[str] = set().union(*(d["mit_massen"] for d in fv.values() if not d.get("fehlt")))
    videos_fertig: Set[str] = set().union(*(d["fertig"] for d in vv.values() if not d.get("fehlt")))
    beschrieben: Set[str] = set().union(*(d["kennungen"] for d in bq.values() if not d.get("fehlt")))

    zeilen.append("Dateien:")
    for n, d in fv.items():
        if d.get("fehlt"):
            zeilen.append(f"  {n}: fehlt")
            continue
        zeilen.append(f"  {n}: {_z(len(d['bilder']))} Fotos, {_z(d['gesichter'])} Gesichter, "
                      f"{_z(len(d['mit_fehler']))} mit Fehler, {_z(d['kaputt'])} kaputte Zeilen, "
                      f"{_z(d['doppelt'])} doppelt")
    for n, d in vv.items():
        zeilen.append(f"  {n}: fehlt" if d.get("fehlt") else
                      f"  {n}: {_z(len(d['fertig']))} Videos fertig, {_z(d['gesichter'])} Gesichter")
    for n, d in bq.items():
        zeilen.append(f"  {n}: fehlt" if d.get("fehlt") else
                      f"  {n}: {_z(d['zeilen'])} Zeilen, {_z(len(d['kennungen']))} Fotos, "
                      f"{_z(d['leer'])} leer, {_z(d['kaputt'])} kaputt, Kosten "
                      f"{_usd(d['kosten'])} USD")
    zeilen.append("")

    plan_fotos: Set[str] = set()
    plan_videos: Set[str] = set()
    for name in plaene:
        p = plan_lesen(os.path.join(basis, name))
        if p.get("fehlt"):
            zeilen.append(f"Plan {name}: fehlt")
            continue
        f, v = p["fotos"], p["videos"]
        plan_fotos |= f
        plan_videos |= v
        g_f, g_v, b_f = len(f & alle_bilder), len(v & videos_fertig), len(f & beschrieben)
        zeilen.append(f"Plan {name}: {_z(p['eintraege'])} Eintraege = {_z(len(f))} Fotos + {_z(len(v))} Videos")
        zeilen.append(f"  Gesichter Fotos:  {_z(g_f)} von {_z(len(f))} ({_anteil(g_f, len(f))}), "
                      f"davon {_z(len(f & mit_gesicht))} mit Gesicht, {_z(len(f & mit_fehler))} mit Fehler")
        zeilen.append(f"  Gesichter Videos: {_z(g_v)} von {_z(len(v))} ({_anteil(g_v, len(v))})")
        zeilen.append(f"  Beschreibungen:   {_z(b_f)} von {_z(len(f))} Fotos ({_anteil(b_f, len(f))})")
        if g_f < len(f):
            luecken.append(f"{name}: {_z(len(f) - g_f)} Fotos ohne Gesichtszeile")
        if g_v < len(v):
            luecken.append(f"{name}: {_z(len(v) - g_v)} Videos ohne Gesichter-Lauf")
        if b_f < len(f):
            luecken.append(f"{name}: {_z(len(f) - b_f)} Fotos ohne Beschreibung")
    if gesamtplan:
        gp = gesamtplan_lesen(os.path.join(basis, gesamtplan))
        if gp.get("fehlt"):
            zeilen.append(f"Gesamtplan {gesamtplan}: fehlt - Deckung ueber alle Quellen nicht pruefbar")
        else:
            f = gp["fotos"]
            b_f = len(f & beschrieben)
            ohne = len(f) - b_f
            zeilen.append(f"Gesamtplan {gesamtplan}: {_z(gp['eintraege'])} Eintraege = "
                          f"{_z(len(f))} Fotos + {_z(len(gp['videos']))} Videos + "
                          f"{_z(gp['ohne_namen'])} ohne Namen"
                          f"{' + ' + _z(gp['ohne_kennung']) + ' ohne Kennung' if gp['ohne_kennung'] else ''}")
            zeilen.append(f"  Beschreibungen:   {_z(b_f)} von {_z(len(f))} Fotos ({_anteil(b_f, len(f))}) "
                          f"- in keiner Beschreibungsdatei fehlen {_z(ohne)}")
            if ohne:
                luecken.append(f"{gesamtplan}: {_z(ohne)} Fotos ohne Beschreibung")
                zeilen.append(f"  Fehlende Fotos ({_z(ohne)}), mit Kennung und Grund:")
                detail_zeilen, zaehler = luecken_details(
                    f - beschrieben, alle_bilder, mit_massen,
                    gp.get("namen_doppelt"), luecken_details_max)
                zeilen.extend(detail_zeilen if detail_zeilen else
                              ["    (Einzelheiten abgeschaltet: --luecken-details 0)"])
                zeilen.append("  " + _grund_zeile(zaehler))
    ausserhalb = len(alle_bilder - plan_fotos)
    zeilen.append(f"Vektorzeilen ausserhalb aller Plaene: {_z(ausserhalb)}; "
                  f"Beschreibungen ausserhalb aller Plaene: {_z(len(beschrieben - plan_fotos))}")
    zeilen.append("")

    if bild_orte:
        o = orte_lesen(os.path.join(basis, bild_orte))
        gebiete = karten_gebiete(os.path.join(basis, KARTEN_CSV_ORDNER))
        if o.get("fehlt"):
            zeilen.append(f"Orte (OSM): {bild_orte} fehlt - Kartenauswertung nicht zugeordnet "
                          f"(orte_aus_karte.py --zuordnen); Gebiete mit Tabellen: {_z(gebiete)}")
            luecken.append(f"{bild_orte} fehlt (Kartenauswertung nicht zugeordnet)")
        else:
            zeilen.append(f"Orte (OSM): {bild_orte}: {_z(o['zeilen'])} Zeilen (eine je Bild) = "
                          f"{_z(o['mit_gps'])} mit GPS + {_z(o['ohne_gps'])} ohne GPS + "
                          f"{_z(o['flug'])} im Flug")
            zeilen.append(f"  Ortsname {_z(o['mit_ort'])}, Landmarke {_z(o['mit_landmarke'])}, "
                          f"Strasse {_z(o['mit_strasse'])}, Hausnummer {_z(o['mit_hausnummer'])}"
                          + (f", {_z(o['kaputt'])} kaputte Zeilen" if o["kaputt"] else ""))
            zeilen.append(f"  Karten: {_z(gebiete)} Gebiete mit beiden Tabellen (osm/csv)")
            z_orte = tabellen_zeilen(os.path.join(basis, KARTEN_CSV_ORDNER, KARTEN_ORTE))
            z_adr = tabellen_zeilen(os.path.join(basis, KARTEN_CSV_ORDNER, KARTEN_ADRESSEN))
            if z_orte or z_adr:
                zeilen.append(f"  Gesamttabellen: {_z(z_orte)} Orte, {_z(z_adr)} Adressen")
    zeilen.append("")

    gr = gruppen_lesen(basis)
    if gr.get("fehlt"):
        zeilen.append("Gruppen: personen_gruppen/personen_beispiele.json fehlt - der Gruppierer "
                      "lief nur trocken (Trockenlauf schreibt nichts). Fuer das Quiz: "
                      "personen_gruppieren.py --schreiben")
        luecken.append("Gruppen nicht gespeichert (nur Trockenlauf)")
    else:
        a = gr["abdeckung"]
        zeilen.append(f"Gruppen (Stand {gr['stand']}): {_z(gr['gruppen'])} Gruppen mit "
                      f"{_z(gr['gesichter_in_gruppen'])} Gesichtern, benannt {_z(gr['benannt'])}")
        zeilen.append(f"  Groesse: {_z(gr['ab_50'])} Gruppen >= 50 Gesichter, {_z(gr['ab_10'])} >= 10, "
                      f"{_z(gr['unter_10'])} unter 10; {_z(gr['mit_zwilling'])} mit Zwillingsverdacht")
        zeilen.append(f"  Abdeckung: die groessten {_z(a.get(0.5, 0))} Gruppen = 50 % der Gesichter, "
                      f"{_z(a.get(0.8, 0))} = 80 %, {_z(a.get(0.9, 0))} = 90 %")
        if "zuordnung_zeilen" in gr:
            zeilen.append(f"  Zuordnung: {_z(gr['zuordnung_zeilen'])} Gesichter, davon "
                          f"{_z(gr['zuordnung_mit_gruppe'])} in einer Gruppe "
                          f"({_anteil(gr['zuordnung_mit_gruppe'], gr['zuordnung_zeilen'])}), "
                          f"Rest = Einzelgesichter/Menge")
        else:
            luecken.append("gesicht_zuordnung.jsonl fehlt")
    zeilen.append("")
    zeilen.append("Ergebnis: " + ("alles vollstaendig" if not luecken else f"{len(luecken)} Luecke(n)"))
    zeilen.extend("  - " + l for l in luecken)
    return zeilen, luecken


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Bestand pruefen - nur lesend, nur Zahlen.")
    parser.add_argument("--basis", default=STANDARD_BASIS)
    parser.add_argument("--luecken-details", type=int, default=20, dest="luecken_details",
                        help="wie viele fehlende Fotos mit Kennung und Grund benannt werden "
                             "(0 = nur zaehlen)")
    args = parser.parse_args(argv)
    if not os.path.isdir(args.basis):
        print(f"Ordner fehlt: {args.basis}")
        return 2
    zeilen, _ = pruefen(args.basis, luecken_details_max=args.luecken_details)
    print("\n".join(zeilen))
    return 0


if __name__ == "__main__":
    sys.exit(main())
