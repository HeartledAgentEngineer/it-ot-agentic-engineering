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
  * Bildindex:        ``bild_index.db`` (Bildsuche; Beschreibungen als Vektoren,
                      Ketten-Schritt 7) — Bilder, mit Vektor, mit Beschreibung,
                      Modell/Dimension/Token/Kosten aus dem eigenen ``meta``,
                      dazu der Abgleich gegen die Beschreibungsdateien:
                      „beschrieben, aber ohne Vektor im Index\" ist die eine
                      offene Richtung (die Bildsuche waere unvollstaendig),
                      „im Index, aber nicht beschrieben\" die andere. Nur Zahlen —
                      keine Beschreibungstexte, keine Ordner, keine Vektoren.
                      Der Bildindex stand bisher in KEINEM Nachweis, obwohl er der
                      Schluss der Kette ist.
  * Anlaesse:         ``ordner_ereignisse.jsonl`` (Ketten-Schritt 5: Anlass aus
                      EXIF/Dateiname/Ordnerjahr, Gebuendelung nach >18 h Pause) —
                      Anlaesse, Datei-Kennungen, Videos, wie viele Anlaesse ein
                      Datum tragen und woher es kommt (Quellen-Schluessel aus
                      ``quellen.datum``), die Jahresspanne und die Deckung gegen
                      die Plan-Fotos. Diese Stufe traegt „Anlaesse einer Person"
                      und das Erzaehlen und stand bisher in KEINEM Nachweis. Nur
                      Zahlen — keine Titel, keine Themen, keine Kategorien.
  * Orte (GeoNames): ``orte.jsonl`` (Ketten-Schritt 3b, ``orte_zuordnen.py``:
                      je Bild Land/Region/naechster Ort + Aufnahmedatum, offline;
                      anhaengend und idempotent) — Zeilen, Bilder (Kennungen),
                      doppelte Zeilen (ein nicht-idempotenter Lauf wuerde
                      auffallen), Laender/Regionen/Orte als ANZAHL, Zeilen mit
                      Datum und die Deckung gegen die Plan-Fotos. Diese Stufe
                      traegt die Auskunft „wo war das?" und die Ortsnamen fuer
                      die Erzaehlung und stand bisher in KEINEM Nachweis — wie
                      OSM, Bildindex und Anlaesse. Nur Zahlen: keine Ortsnamen,
                      keine Koordinaten.
  * Erzaehl-Anlaesse: ``ereignisse.jsonl`` (Anlaesse der Sammlung) und
                      ``fotobuch_ereignisse.jsonl`` (Fotobuch-Seiten) — genau die
                      beiden Dateien, die ``erzaehl_service._ereignisse_laden()``
                      zusammen mit ``ordner_ereignisse.jsonl`` liest, um
                      Geschichten anzuhaengen. Nur die dritte hatte bisher einen
                      Nachweis; fehlt eine der beiden, fehlen dem Erzaehlen ihre
                      Anlaesse, ohne dass es auffiele. Gezaehlt werden Anlaesse,
                      Datei-Kennungen, Zeilen ohne Kennung (der Dienst verwirft
                      sie still), Datum + Quellen-Schluessel, Jahresspanne und die
                      Deckung gegen die Plan-Fotos. Nur Zahlen — keine Titel,
                      keine Buchseiten, keine Texte.
  * Beziehungen:      ``beziehungen.jsonl`` (15.051 Aussagen „wer war mit wem
                      wo" — Anlass, Datum, Unterart, beteiligte Personen) und die
                      Uebersicht ``beziehungen.json`` (Kennzahlen). Beide liest
                      der Dienst ``beziehungen_service`` (Antwortstufe N28) — und
                      beide standen in KEINEM Nachweis. Gezaehlt werden Aussagen,
                      Anlaesse, Tage, Unterarten, Personen-Eintraege (bestaetigt /
                      mit Kennung), Kategorien, Datumsspanne; die Uebersicht wird
                      gegen die gemessene Zeilenzahl gestellt (Kennzahlen und
                      Datei muessen zusammenpassen). Nur Zahlen — keine Namen,
                      keine Chat-Namen, keine Themen, keine Ordner.
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
import sqlite3
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
# Der Bildindex (Ketten-Schritt 7): Beschreibungen als Vektoren fuer die Bildsuche.
# Er stand bisher in keinem Nachweis — und ist der Schluss der Kette.
STANDARD_BILDINDEX = "bild_index.db"
BILDINDEX_TABELLE = "bilder"
# Die Neuausrichtung: gedreht_plan.json listet die Bilder, die neu gedreht und
# neu erkannt wurden (personen_vektoren_gedreht_neu.jsonl). Diese Stufe stand in
# KEINEM Nachweis — 51 Bilder fehlten dort zwei Tage unbemerkt (50 davon ueber
# 8 MB; gleiche Ursache wie bei Papas 24: KACHEL_MAX_BYTES = 8 MB vor dem Fix
# vom 10.10.). Der Nachweis prueft die Stufe jetzt genauso wie die Plaene.
STANDARD_GEDREHT_PLAN = "gedreht_plan.json"
STANDARD_GEDREHT_VEKTOREN = "personen_vektoren_gedreht_neu.jsonl"
# Die Anlaesse (Ketten-Schritt 5): je Anlass ein Datum und die Bild-Kennungen,
# aus EXIF/Dateiname/Ordnerjahr/Planjahr gebuendelt. Sie tragen die Funktionen
# „Anlaesse einer Person" (person_auskunft) und das Erzaehlen. Diese Stufe stand
# in KEINEM Nachweis — gebaut am 10.10. (2.268 Anlaesse ueber den Union-Plan),
# aber niemandem auffaellig, wenn die Datei fehlt oder halb ist. Der Nachweis
# prueft sie jetzt wie die uebrigen Stufen (nur Zahlen, keine Titel).
STANDARD_ANLAESSE = "ordner_ereignisse.jsonl"
# Die Ortsnamen (Ketten-Schritt 3b): je Bild eine Zeile aus den offline
# GeoNames-Daten — Land, Region, naechster Ort, Aufnahmedatum (orte_zuordnen.py,
# anhaengend und idempotent: vorhandene bild_id wird uebersprungen). Diese Stufe
# stand in KEINEM Nachweis, obwohl sie die Auskunft „wo war das?" und die
# Ortsnamen fuer die Erzaehlung traegt — dieselbe Luecke wie bei OSM, Bildindex
# und Anlaessen. Der Nachweis prueft sie jetzt wie die uebrigen Stufen: nur
# Zahlen und Zaehlungen von Land/Region/Ort — keine Namen, keine Koordinaten.
STANDARD_ORTE_NAMEN = "orte.jsonl"
# Die beiden uebrigen Erzaehl-Quellen: ``ereignisse.jsonl`` (Anlaesse der
# Sammlung aus ``ereignisse_bauen.py``, 2.127 Anlaesse) und
# ``fotobuch_ereignisse.jsonl`` (Fotobuch-Seiten aus ``fotobuch_lesen.py``).
# ``erzaehl_service._ereignisse_laden()`` liest genau diese beiden PLUS
# ``ordner_ereignisse.jsonl`` — und nur die dritte hatte einen Nachweis. Fehlt
# ``ereignisse.jsonl``, fehlen dem Erzaehlen 2.127 Anlaesse, und es merkt heute
# niemand (dieselbe Luecke wie bei OSM, Bildindex, Anlaessen und Ortsnamen).
STANDARD_ERZAHL_QUELLEN = ("ereignisse.jsonl", "fotobuch_ereignisse.jsonl")
# Die Beziehungen (N27e/N28): ``beziehungen.jsonl`` (15.051 Aussagen „wer war
# mit wem wo" — je Zeile Anlass, Datum, Unterart und die beteiligten Personen)
# und die kleine ``beziehungen.json`` (Kennzahlen). Beide liest der Dienst
# ``beziehungen_service`` (Antwortstufe N28, ``router/beziehungen.py`` und das
# Chat-Werkzeug) — und BEIDE standen in KEINEM Nachweis. Faellt die Aussagen-
# Datei weg oder halbiert sie sich, schweigt die Auskunft „wer war mit wem wo",
# und es merkt heute niemand (dieselbe Luecke wie bei OSM, Bildindex, Anlaessen,
# Ortsnamen und den Erzaehl-Quellen). Der Nachweis zaehlt sie mit: nur Zahlen —
# keine Namen, keine Chat-Namen, keine Themen, keine Ordner.
STANDARD_BEZEIHUNGEN = "beziehungen.jsonl"
STANDARD_BEZEIHUNGEN_UEBERSICHT = "beziehungen.json"
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


def _ganze_zahl(wert: Any) -> int:
    """Wert als ganze Zahl — sonst 0 (nichts geraten, nie ein Wurf)."""
    if isinstance(wert, bool):
        return 0
    try:
        return int(wert)
    except (TypeError, ValueError):
        return 0


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


# ── Ortsnamen (GeoNames) ────────────────────────────────────────────────────

def ortsnamen_lesen(pfad: str) -> Dict[str, Any]:
    """``orte.jsonl`` zaehlen — nur Zahlen, keine Ortsnamen, keine Koordinaten.

    Je Bild eine Zeile aus den offline GeoNames-Daten (Ketten-Schritt 3b,
    ``orte_zuordnen.py``): Land, Region, naechster Ort, Aufnahmedatum. Der
    Zuordner haengt an und ueberspringt vorhandene ``bild_id`` — deshalb wird
    hier auch auf Dubletten geprueft (mehr Zeilen als Kennungen = der idempotente
    Lauf wurde umgangen). Gezaehlt werden nur Zahlen sowie die ANZAHL
    verschiedener Laender/Regionen/Orte und Aufnahmetage — nie ein Name.
    """
    e: Dict[str, Any] = {"fehlt": True, "zeilen": 0, "kaputt": 0, "kennungen": set(),
                         "doppelt": 0, "mit_datum": 0, "tage": 0, "laender": 0,
                         "regionen": 0, "orte": 0, "ohne_ort": 0}
    if not os.path.isfile(pfad):
        return e
    e["fehlt"] = False
    gesehen: Set[str] = set()
    laender: Set[str] = set()
    regionen: Set[str] = set()
    orte: Set[str] = set()
    tage: Set[str] = set()
    for zeile in _jsonl(pfad):
        if not isinstance(zeile, dict):
            e["kaputt"] += 1
            continue
        e["zeilen"] += 1
        k = _kennung(zeile.get("bild_id"))
        if k:
            if k in gesehen:
                e["doppelt"] += 1
            gesehen.add(k)
            e["kennungen"].add(k)
        for feld, sammlung in (("land", laender), ("region", regionen), ("ort", orte)):
            wert = str(zeile.get(feld) or "").strip()
            if wert:
                sammlung.add(wert)
        if not str(zeile.get("ort") or "").strip():
            e["ohne_ort"] += 1
        aufnahme = str(zeile.get("aufnahme") or "").strip()
        if aufnahme:
            e["mit_datum"] += 1
            tage.add(aufnahme[:10])
    e.update(laender=len(laender), regionen=len(regionen), orte=len(orte),
             tage=len(tage))
    return e


# ── Anlaesse (Ereignis-Datei) ───────────────────────────────────────────────

def anlaesse_lesen(pfad: str) -> Dict[str, Any]:
    """Anlaesse zaehlen — nur Zahlen und Quellen-Schluessel, nie Titel/Themen.

    Felder: ``fehlt``, ``anlaesse``, ``kaputt``, ``ohne_kennung``, ``kennungen``
    (Datei-Kennungen als Text), ``videos``, ``mit_datum``, ``datum_quellen``
    (Zaehler der Schluessel aus ``quellen.datum``, z. B. ``exif``/``dateiname``)
    sowie ``jahr_min``/``jahr_max``. Kaputte Zeilen zaehlen, statt zu werfen.

    ``ohne_kennung`` zaehlt Zeilen ohne brauchbare ``kennung``: der Erzaehl-Dienst
    (``erzaehl_service._datei_ereignisse_laden``) verwirft solche Zeilen still —
    ein Anlass ohne Kennung verschwindet damit aus den Geschichten, ohne dass es
    auffiele. Dieselbe Datei bedient drei Quellen, deshalb steht die Pruefung hier.
    """
    e: Dict[str, Any] = {"fehlt": True, "anlaesse": 0, "kaputt": 0, "ohne_kennung": 0,
                         "kennungen": set(), "videos": 0, "mit_datum": 0,
                         "datum_quellen": {}, "jahr_min": None, "jahr_max": None}
    if not os.path.isfile(pfad):
        return e
    e["fehlt"] = False
    for zeile in _jsonl(pfad):
        if not isinstance(zeile, dict):
            e["kaputt"] += 1
            continue
        e["anlaesse"] += 1
        if not _kennung(zeile.get("kennung")):
            e["ohne_kennung"] += 1
        for roh in zeile.get("datei_kennungen") or []:
            k = _kennung(roh)
            if k:
                e["kennungen"].add(k)
        try:
            e["videos"] += int(zeile.get("videos") or 0)
        except (TypeError, ValueError):
            pass
        if zeile.get("datum"):
            e["mit_datum"] += 1
        quellen = (zeile.get("quellen") or {}).get("datum")
        if isinstance(quellen, dict):
            schluessel = list(quellen)
        elif isinstance(quellen, str) and quellen.strip():
            # Die Sammlungs-Anlaesse nennen die Quelle als TEXT
            # ("sortierplan.json:anlaesse") statt als Zaehler-Dict. Ohne diesen
            # Zweig stuende dort "keine Quellenangabe", obwohl die Quelle dasteht.
            schluessel = [quellen.split(":")[0].strip()]
        else:
            schluessel = []
        for name in schluessel:
            if name:
                e["datum_quellen"][name] = e["datum_quellen"].get(name, 0) + 1
        jahr_wert = zeile.get("jahr")
        try:
            jahr = int(jahr_wert) if jahr_wert is not None else 0
        except (TypeError, ValueError):
            jahr = 0
        if jahr:
            e["jahr_min"] = jahr if e["jahr_min"] is None else min(e["jahr_min"], jahr)
            e["jahr_max"] = jahr if e["jahr_max"] is None else max(e["jahr_max"], jahr)
    return e


# ── Beziehungen („wer war mit wem wo") ──────────────────────────────────────

def beziehungen_lesen(pfad: str) -> Dict[str, Any]:
    """``beziehungen.jsonl`` zaehlen — nur Zahlen, NIE einen Personennamen.

    Felder: ``fehlt``, ``zeilen``, ``kaputt``, ``anlaesse`` (verschiedene
    ``anlass_id``), ``ereignis_kennungen`` (verschiedene ``ereignis_kennung``),
    ``tage`` (verschiedene ``datum``), ``unterarten`` (Zaehler),
    ``personen_eintraege``, ``personen_bestaetigt``, ``personen_mit_kennung``,
    ``kategorien`` (Anzahl), ``mit_datum``, ``jahr_min``/``jahr_max``.

    Die Datei traegt Namen (``personen[].name``, ``beleg.chat_name``), Themen
    und Zielordner — NICHTS davon wird gelesen oder ausgegeben, nur gezaehlt.
    Eine kaputte Zeile zaehlt, statt zu werfen. ``personen_mit_kennung`` zaehlt
    Eintraege mit brauchbarer ``kennung``: ohne Kennung ist eine Aussage nicht
    an ein Gesicht gebunden.
    """
    e: Dict[str, Any] = {"fehlt": True, "zeilen": 0, "kaputt": 0, "anlaesse": set(),
                         "ereignis_kennungen": set(), "tage": set(), "unterarten": {},
                         "personen_eintraege": 0, "personen_bestaetigt": 0,
                         "personen_mit_kennung": 0, "kategorien": set(),
                         "mit_datum": 0, "jahr_min": None, "jahr_max": None}
    if not os.path.isfile(pfad):
        return e
    e["fehlt"] = False
    for zeile in _jsonl(pfad):
        if not isinstance(zeile, dict):
            e["kaputt"] += 1
            continue
        e["zeilen"] += 1
        anlass = _kennung(zeile.get("anlass_id"))
        if anlass:
            e["anlaesse"].add(anlass)
        ereignis = _kennung(zeile.get("ereignis_kennung"))
        if ereignis:
            e["ereignis_kennungen"].add(ereignis)
        datum = _kennung(zeile.get("datum"))
        if datum:
            e["mit_datum"] += 1
            e["tage"].add(datum)
            jahr = _ganze_zahl(datum[:4])
            if jahr:
                e["jahr_min"] = jahr if e["jahr_min"] is None else min(e["jahr_min"], jahr)
                e["jahr_max"] = jahr if e["jahr_max"] is None else max(e["jahr_max"], jahr)
        unterart = _kennung(zeile.get("unterart"))
        if unterart:
            e["unterarten"][unterart] = e["unterarten"].get(unterart, 0) + 1
        kategorie = _kennung(zeile.get("kategorie"))
        if kategorie:
            e["kategorien"].add(kategorie)
        personen = zeile.get("personen")
        if isinstance(personen, list):
            for person in personen:
                if not isinstance(person, dict):
                    continue
                e["personen_eintraege"] += 1
                if person.get("bestaetigt") is True:
                    e["personen_bestaetigt"] += 1
                if _kennung(person.get("kennung")):
                    e["personen_mit_kennung"] += 1
    return e


def beziehungen_uebersicht_lesen(pfad: str) -> Dict[str, Any]:
    """``beziehungen.json`` lesen — nur Kennzahlen, nie ein Wurf.

    Felder: ``fehlt``, ``kaputt`` (kein lesbares JSON), ``art``, ``anzahl``
    (Zaehler je Unterart), ``summe`` (Summe der Unterarten — die Zahl, die die
    Datei als „Aussagen" meint), ``kontakte``, ``personen_kennungen``,
    ``datum_von``/``datum_bis``, ``stand``. Die Uebersicht traegt keine Namen
    und keine Themen — gelesen werden nur Zahlen und Textfelder wie ``art``.
    """
    leer: Dict[str, Any] = {"fehlt": True, "kaputt": False, "art": None, "anzahl": {},
                            "summe": 0, "kontakte": 0, "personen_kennungen": 0,
                            "datum_von": None, "datum_bis": None, "stand": None}
    if not os.path.isfile(pfad):
        return leer
    daten: Any = None
    try:
        with open(pfad, "r", encoding="utf-8") as datei:
            daten = json.load(datei)
    except (OSError, ValueError):
        daten = None
    if not isinstance(daten, dict):
        return dict(leer, fehlt=False, kaputt=True)
    anzahl_roh = daten.get("anzahl")
    anzahl: Dict[str, int] = {}
    if isinstance(anzahl_roh, dict):
        for name, wert in anzahl_roh.items():
            anzahl[str(name)] = _ganze_zahl(wert)
    return {"fehlt": False, "kaputt": False, "art": _kennung(daten.get("art")) or None,
            "anzahl": anzahl, "summe": sum(anzahl.values()),
            "kontakte": _ganze_zahl(daten.get("anzahl_kontakte")),
            "personen_kennungen": _ganze_zahl(daten.get("anzahl_personen_kennungen")),
            "datum_von": _kennung(daten.get("datum_von")) or None,
            "datum_bis": _kennung(daten.get("datum_bis")) or None,
            "stand": _kennung(daten.get("stand")) or None}


# ── Bildindex (Bildsuche) ───────────────────────────────────────────────────

def _zahl_aus(wert: Any) -> Optional[float]:
    """Eine Zahl aus dem ``meta``-Text — oder ``None`` (nichts geraten)."""
    try:
        return float(str(wert).strip())
    except (TypeError, ValueError):
        return None


def bildindex_lesen(pfad: str) -> Dict[str, Any]:
    """``bild_index.db`` zaehlen — nur Zahlen, nur lesend, keine Inhalte.

    Der Index traegt je Bild eine Beschreibung und einen Vektor (Ketten-
    Schritt 7, Grundlage der Bildsuche). Gelesen werden nur ``fileid`` und je
    Bild, ob ein Vektor da ist und ob die Beschreibung nicht leer ist — der
    Text selbst, der Ordner und die Vektoren werden NIE gelesen oder
    ausgegeben. Fehlt die Datei (oder ist sie keine gueltige Datenbank),
    meldet das Ergebnis ehrlich ``fehlt`` statt zu werfen.
    """
    if not os.path.isfile(pfad):
        return {"fehlt": True}
    try:
        verbindung = sqlite3.connect(f"file:{pfad}?mode=ro", uri=True)
    except sqlite3.Error as problem:
        return {"fehlt": True, "fehler": problem.__class__.__name__}
    kennungen: Set[str] = set()
    bilder = mit_vektor = mit_beschreibung = 0
    meta: Dict[str, str] = {}
    try:
        for zeile in verbindung.execute(
                f"SELECT fileid, beschreibung, vektor FROM {BILDINDEX_TABELLE}"):
            kennung = _kennung(zeile[0])
            if not kennung:
                continue
            bilder += 1
            kennungen.add(kennung)
            if zeile[2] is not None:
                mit_vektor += 1
            if str(zeile[1] or "").strip():
                mit_beschreibung += 1
        try:
            meta = {str(z[0]): str(z[1]) for z in
                    verbindung.execute("SELECT schluessel, wert FROM meta")}
        except sqlite3.Error:
            meta = {}
    except sqlite3.Error as problem:
        return {"fehlt": True, "fehler": problem.__class__.__name__}
    finally:
        verbindung.close()
    return {"bilder": bilder, "mit_vektor": mit_vektor,
            "mit_beschreibung": mit_beschreibung, "kennungen": kennungen,
            "meta": meta}


def _bildindex_kopf(meta: Dict[str, str]) -> str:
    """Die ``meta``-Angaben des Index als eine Zeile — nur Zahlen und Namen
    des Modells (kein Inhalt, kein Pfad)."""
    teile: List[str] = []
    if meta.get("modell"):
        teile.append(meta["modell"])
    if meta.get("dimension"):
        teile.append(meta["dimension"] + " Dimensionen")
    token = _zahl_aus(meta.get("tokens_gezaehlt"))
    if token:
        teile.append(_z(int(token)) + " Token")
    kosten = _zahl_aus(meta.get("kosten_usd"))
    if kosten:
        teile.append(_usd(kosten) + " USD")
    if meta.get("stand"):
        teile.append("Stand " + meta["stand"])
    return "; ".join(teile)


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
            bild_index: Optional[str] = STANDARD_BILDINDEX,
            gedreht_plan: Optional[str] = STANDARD_GEDREHT_PLAN,
            gedreht_vektoren: Optional[str] = STANDARD_GEDREHT_VEKTOREN,
            anlaesse: Optional[str] = STANDARD_ANLAESSE,
            erzaehl_quellen=STANDARD_ERZAHL_QUELLEN,
            orte_namen: Optional[str] = STANDARD_ORTE_NAMEN,
            beziehungen: Optional[str] = STANDARD_BEZEIHUNGEN,
            beziehungen_uebersicht: Optional[str] = STANDARD_BEZEIHUNGEN_UEBERSICHT,
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
    if gedreht_plan:
        gdp = plan_lesen(os.path.join(basis, gedreht_plan))
        if gdp.get("fehlt"):
            zeilen.append(f"Rotierte Bilder ({gedreht_plan}): fehlt - Neuausrichtung nicht pruefbar")
        else:
            rotiert = gdp["fotos"] | gdp["videos"]
            if not gedreht_vektoren:
                zeilen.append(f"Rotierte Bilder ({gedreht_plan}): {_z(len(rotiert))} Bilder "
                              f"(Vektordatei nicht geprueft)")
            else:
                gdv = foto_vektoren_lesen(os.path.join(basis, gedreht_vektoren))
                if gdv.get("fehlt"):
                    zeilen.append(f"Rotierte Bilder ({gedreht_plan}): {_z(len(rotiert))} Bilder; "
                                  f"{gedreht_vektoren} fehlt - neue Zeilen nicht pruefbar")
                    luecken.append(f"{gedreht_vektoren} fehlt (rotierte Bilder ohne neue Zeile)")
                else:
                    neu = gdv["bilder"]
                    mit = len(rotiert & neu)
                    ohne = len(rotiert - neu)
                    zeilen.append(f"Rotierte Bilder ({gedreht_plan}): {_z(len(rotiert))} Bilder, "
                                  f"davon {_z(mit)} mit neuer Vektorzeile ({_anteil(mit, len(rotiert))}), "
                                  f"ohne {_z(ohne)}")
                    if ohne:
                        luecken.append(f"{gedreht_plan}: {_z(ohne)} Bilder ohne neue Vektorzeile")
    ausserhalb = len(alle_bilder - plan_fotos)
    zeilen.append(f"Vektorzeilen ausserhalb aller Plaene: {_z(ausserhalb)}; "
                  f"Beschreibungen ausserhalb aller Plaene: {_z(len(beschrieben - plan_fotos))}")
    zeilen.append("")

    if anlaesse:
        an = anlaesse_lesen(os.path.join(basis, anlaesse))
        if an.get("fehlt"):
            zeilen.append(f"Anlaesse ({anlaesse}): fehlt - Anlass aus EXIF/Dateiname nicht "
                          f"gebaut (ereignisse_ordner_bauen.py)")
            luecken.append(f"{anlaesse} fehlt (Anlaesse nicht gebaut)")
        else:
            k = an["kennungen"]
            in_anlaessen = len(plan_fotos & k)
            zeilen.append(f"Anlaesse ({anlaesse}): {_z(an['anlaesse'])} Anlaesse, "
                          f"{_z(len(k))} Datei-Kennungen, davon {_z(an['videos'])} Videos"
                          + (f", {_z(an['kaputt'])} kaputte Zeilen" if an["kaputt"] else "")
                          + (f", {_z(an['ohne_kennung'])} ohne Kennung" if an["ohne_kennung"] else ""))
            quellen = ", ".join(f"{name} {_z(n)}" for name, n in sorted(an["datum_quellen"].items()))
            zeilen.append(f"  Datum: {_z(an['mit_datum'])} von {_z(an['anlaesse'])} Anlaessen "
                          f"tragen eines"
                          + (f" ({quellen})" if quellen else " (keine Quellenangabe)"))
            if an["jahr_min"]:
                zeilen.append(f"  Jahre: {an['jahr_min']}-{an['jahr_max']}")
            if plan_fotos:
                zeilen.append(f"  Deckung: {_z(in_anlaessen)} von {_z(len(plan_fotos))} "
                              f"Plan-Fotos liegen in einem Anlass ({_anteil(in_anlaessen, len(plan_fotos))})")
        zeilen.append("")

    if erzaehl_quellen:
        vorhanden = 0
        for name in erzaehl_quellen:
            eq = anlaesse_lesen(os.path.join(basis, name))
            if eq.get("fehlt"):
                zeilen.append(f"Erzaehl-Anlaesse ({name}): fehlt - Anlaesse nicht gebaut "
                              f"(dem Erzaehlen fehlt diese Quelle)")
                luecken.append(f"{name} fehlt (Erzaehl-Anlaesse nicht gebaut)")
                continue
            vorhanden += 1
            k = eq["kennungen"]
            zeilen.append(f"Erzaehl-Anlaesse ({name}): {_z(eq['anlaesse'])} Anlaesse, "
                          f"{_z(len(k))} Datei-Kennungen"
                          + (f", {_z(eq['kaputt'])} kaputte Zeilen" if eq["kaputt"] else "")
                          + (f", {_z(eq['ohne_kennung'])} ohne Kennung (wird nicht erzaehlt)"
                             if eq["ohne_kennung"] else ""))
            if eq["mit_datum"]:
                quellen = ", ".join(f"{q} {_z(n)}" for q, n in sorted(eq["datum_quellen"].items()))
                zeilen.append(f"  Datum: {_z(eq['mit_datum'])} von {_z(eq['anlaesse'])} tragen eines"
                              + (f" ({quellen})" if quellen else " (keine Quellenangabe)"))
            if eq["jahr_min"]:
                zeilen.append(f"  Jahre: {eq['jahr_min']}-{eq['jahr_max']}")
            if plan_fotos:
                drin = len(plan_fotos & k)
                zeilen.append(f"  Deckung: {_z(drin)} von {_z(len(plan_fotos))} Plan-Fotos "
                              f"liegen in einem Anlass ({_anteil(drin, len(plan_fotos))})")
            if eq["ohne_kennung"]:
                luecken.append(f"{name}: {_z(eq['ohne_kennung'])} Anlaesse ohne Kennung "
                               f"(werden nicht erzaehlt)")
        zeilen.append(f"  Erzaehl-Dienst: {_z(vorhanden)} von {_z(len(erzaehl_quellen))} dieser "
                      f"Quellen vorhanden (dazu {anlaesse or 'ordner_ereignisse.jsonl'})")
        if not vorhanden:
            luecken.append("keine Erzaehl-Anlaesse vorhanden (Geschichten ohne Anlass)")
        zeilen.append("")

    if beziehungen:
        bz = beziehungen_lesen(os.path.join(basis, beziehungen))
        if bz.get("fehlt"):
            zeilen.append(f"Beziehungen ({beziehungen}): fehlt - die Auskunft \"wer war mit wem wo\" "
                          f"hat keine Quelle (beziehungen_ableiten.py)")
            luecken.append(f"{beziehungen} fehlt (Beziehungen nicht abgeleitet)")
        else:
            unterarten = ", ".join(f"{name} {_z(n)}" for name, n in sorted(bz["unterarten"].items()))
            zeilen.append(f"Beziehungen ({beziehungen}): {_z(bz['zeilen'])} Aussagen, "
                          f"{_z(len(bz['anlaesse']))} Anlaesse, {_z(len(bz['tage']))} Tage, "
                          f"{_z(len(bz['kategorien']))} Kategorien"
                          + (f", {_z(bz['kaputt'])} kaputte Zeilen" if bz["kaputt"] else ""))
            zeilen.append(f"  Unterarten: {unterarten or 'keine'}")
            zeilen.append(f"  Personen-Eintraege: {_z(bz['personen_eintraege'])}, davon "
                          f"{_z(bz['personen_bestaetigt'])} bestaetigt, "
                          f"{_z(bz['personen_mit_kennung'])} mit Kennung")
            if bz["jahr_min"]:
                zeilen.append(f"  Datum: {_z(bz['mit_datum'])} von {_z(bz['zeilen'])} tragen eines; "
                              f"Jahre {bz['jahr_min']}-{bz['jahr_max']}")
        if beziehungen_uebersicht:
            ub = beziehungen_uebersicht_lesen(os.path.join(basis, beziehungen_uebersicht))
            if ub.get("fehlt"):
                zeilen.append(f"  Uebersicht ({beziehungen_uebersicht}): fehlt - die Kennzahlen der "
                              f"Antwortstufe fehlen")
                luecken.append(f"{beziehungen_uebersicht} fehlt (Beziehungs-Kennzahlen fehlen)")
            elif ub.get("kaputt"):
                zeilen.append(f"  Uebersicht ({beziehungen_uebersicht}): nicht lesbar (kein JSON)")
                luecken.append(f"{beziehungen_uebersicht} nicht lesbar")
            else:
                arten = ", ".join(f"{name} {_z(n)}" for name, n in sorted(ub["anzahl"].items()))
                zeilen.append(f"  Uebersicht ({beziehungen_uebersicht}): nennt {_z(ub['summe'])} "
                              f"Aussagen ({arten or 'keine Arten'}); Kontakte {_z(ub['kontakte'])}, "
                              f"Kennungen {_z(ub['personen_kennungen'])}"
                              + (f"; {ub['datum_von']} bis {ub['datum_bis']}" if ub["datum_von"] else ""))
                if not bz.get("fehlt") and ub["summe"] and ub["summe"] != bz["zeilen"]:
                    zeilen.append(f"    Abweichung: Uebersicht nennt {_z(ub['summe'])}, gemessen "
                                  f"{_z(bz['zeilen'])} - Datei und Kennzahlen passen nicht zusammen")
                    luecken.append(f"{beziehungen}: {_z(bz['zeilen'])} Aussagen, Uebersicht nennt "
                                   f"{_z(ub['summe'])} (nicht reproduzierbar)")
        zeilen.append("")

    if bild_index:
        bi = bildindex_lesen(os.path.join(basis, bild_index))
        if bi.get("fehlt"):
            zeilen.append(f"Bildindex (Bildsuche): {bild_index} fehlt - die Beschreibungen "
                          f"sind nicht eingebettet (bild_index_einbetten.py)")
            luecken.append(f"{bild_index} fehlt (Bildsuche nicht eingebettet)")
        else:
            zeilen.append(f"Bildindex (Bildsuche): {bild_index}: {_z(bi['bilder'])} Bilder, "
                          f"{_z(bi['mit_vektor'])} mit Vektor, "
                          f"{_z(bi['mit_beschreibung'])} mit Beschreibung")
            kopf = _bildindex_kopf(bi.get("meta") or {})
            if kopf:
                zeilen.append("  " + kopf)
            ohne_vektor = beschrieben - bi["kennungen"]
            ohne_eintrag = bi["kennungen"] - beschrieben
            zeilen.append(f"  Beschrieben, aber ohne Vektor im Index: {_z(len(ohne_vektor))}; "
                          f"im Index, aber nicht beschrieben: {_z(len(ohne_eintrag))}")
            if ohne_vektor:
                luecken.append(f"{bild_index}: {_z(len(ohne_vektor))} beschriebene Fotos ohne "
                               f"Vektor (Bildsuche unvollstaendig)")
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

    if orte_namen:
        on = ortsnamen_lesen(os.path.join(basis, orte_namen))
        if on.get("fehlt"):
            zeilen.append(f"Orte (GeoNames): {orte_namen} fehlt - Ortsnamen nicht zugeordnet "
                          f"(orte_zuordnen.py)")
            luecken.append(f"{orte_namen} fehlt (Ortsnamen nicht zugeordnet)")
        else:
            eintraege = len(on["kennungen"])
            zeilen.append(f"Orte (GeoNames): {orte_namen}: {_z(on['zeilen'])} Zeilen, "
                          f"{_z(eintraege)} Bilder"
                          + (f", {_z(on['doppelt'])} doppelt" if on["doppelt"] else "")
                          + (f", {_z(on['kaputt'])} kaputte Zeilen" if on["kaputt"] else ""))
            zeilen.append(f"  Namen: {_z(on['laender'])} Laender, {_z(on['regionen'])} Regionen, "
                          f"{_z(on['orte'])} Orte; ohne Ortsnamen {_z(on['ohne_ort'])}")
            zeilen.append(f"  Aufnahme: {_z(on['mit_datum'])} von {_z(on['zeilen'])} Zeilen "
                          f"tragen ein Datum ({_z(on['tage'])} verschiedene Tage)")
            if plan_fotos:
                drin = len(plan_fotos & on["kennungen"])
                zeilen.append(f"  Deckung: {_z(drin)} von {_z(len(plan_fotos))} Plan-Fotos "
                              f"haben einen Ortsnamen ({_anteil(drin, len(plan_fotos))})")
            if on["doppelt"]:
                luecken.append(f"{orte_namen}: {_z(on['doppelt'])} doppelte Zeilen "
                               f"(anhaengender Lauf nicht idempotent)")
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
