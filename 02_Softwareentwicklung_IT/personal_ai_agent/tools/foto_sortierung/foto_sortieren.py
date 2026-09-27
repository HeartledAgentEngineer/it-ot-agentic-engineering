"""Trockenlauf des Foto-Sortierens (Nachtlauf-Schritt N7, 27.09.2026).

Wozu dieses Werkzeug:
  Die Vorstufen haben den Sortierschluessel gebaut: je Datei ein Datum, ein
  Motiv-Thema (aus 53 Katalog-Eintraegen) und die Anlass-ID
  (``thema_quelle``). N6d hat die Ziel-Kategorien aus Sebastians eigenen
  pCloud-Ordnern geholt (``foto_kategorien.py``), N6e den Event-Abgleich
  (``event_abgleich.py``) gebaut. Dieses Werkzeug macht daraus **einen PLAN**:
  welche Ordner unter ``Agent/Fotos/<Jahr>/<Kategorie>/<Event>`` neu
  entstehen und welche Datei wohin zieht.

Was dieses Werkzeug bewusst NICHT tut:
  Es sortiert **nichts**. Es gibt hier keinen Schreibaufruf gegen die pCloud
  (jeder pCloud-Aufruf ist trocken geschaltet), keinen Manifest-Eintrag,
  keinen Download und keine Vorschaubilder. Das echte Verschieben ist Schritt
  N8. Ein Trockenlauf, der etwas bucht, waere kein Trockenlauf.

Datenschutz (Regel des Auftrags, hier als Code):
  * Die echten Ordnernamen des Nutzers liegen absichtlich **ausserhalb** des
    Repos (``~/foto_sortierung/``). Der Plan und die Konsole duerfen sie
    zeigen — **dieses Modul und seine Tests** nennen nur erfundene Namen.
  * Ausgaben (``--plan``) gehen nur **ausserhalb** des Repos; die Pruefung
    uebernimmt ``foto_kategorien._pruefe_ziel_ausserhalb_repo`` (Ziel im Repo
    = deutsche Meldung und ``SystemExit(2)``, es wird nichts geschrieben).
  * Der pCloud-Schluessel wird **nie** ausgegeben und nie in eine Datei
    geschrieben; ohne Schluessel laeuft der Plan mit ``fileid: null`` weiter.

Eingaben (alle lesend):
  1. ``~/foto_sortierung/sortierschluessel_themen.csv`` — Spalten ``jahr,monat,
     tag,datumquelle,thema,geraet,ordner,datei,motiv,doppelung,bytes,mb,
     thema_quelle`` (``thema_quelle`` = Anlass-ID, ``ordner`` = Quellordner).
  2. ``kategorien.json`` + ``kategorie_zuordnung.json`` ueber
     ``event_abgleich.bestand_und_zuordnung()``.
  3. Nur mit ``--mit-ids`` (Standard an, wenn ein Schluessel da ist): die
     Quellordner per ``service.liste`` auflisten (Dateiname -> ``fileid``).

Fachliche Regeln (so umgesetzt, nicht anders):
  1. **Buendeln:** Zeilen mit ``thema_quelle`` werden zu Anlaessen
     zusammengefasst (Reihenfolge der Dateien = CSV-Reihenfolge). Zeilen ohne
     ``thema_quelle`` werden gezaehlt und uebersprungen (sie sind keinem
     Anlass zuzuordnen).
  2. **Doppelungen:** Zeilen mit gefuellter Spalte ``doppelung`` werden NICHT
     eingeplant (es wird nie geloescht). Gezaehlt wird AUFGESCHLUESSELT:
     ``doppelung_gesamt`` = ALLE Zeilen mit gefuellter ``doppelung``,
     ``doppelung_ohne_anlass`` = davon die Zeilen OHNE Anlass-ID (die ohnehin
     uebersprungen werden) und ``doppelung_uebersprungen`` = davon die Zeilen
     MIT Anlass-ID. Jede Zeile faellt in genau eine dieser beiden Teilmengen —
     nichts zaehlt doppelt.
  3. **Zielkategorie:** ``kategorie_fuer_anlass``; ist das Ergebnis ``None``
     oder fehlt die Kategorie im Bestand (``unterordner_von`` -> ``None``),
     gilt ``ziel_kategorie(SONSTIGES, zuordnung)`` und sonst der Rueckfall
     ``Sonstiges`` — dieser Ordner wird als **neu** geplant.
  4. **Anlass ohne Thema** (Auflage aus N6b): die Event-Ebene wird
     ``event_abgleich.OHNE_THEMA``. Es wird **nie** abgebrochen. Diese Regel
     hat Vorrang vor Regel 5: ein fehlendes Thema ergibt IMMER den
     Rueckfall-Event, auch wenn ein Datum da waere (das Datum steht dann in
     der Anlass-Zeile des Plans, nicht im Ordnernamen).
  5. **Event-Name:** liefert ``vorschlag_fuer`` einen Vorschlag mit
     ``sicher: True``, wird dessen Name genommen (bestehender Ordner wird
     wiederverwendet, ``event_quelle: "vorschlag"`` samt ``stufe``). Sonst
     heisst der neue Ordner ``pfad_saeubern(f"{datum} {thema}")`` aus
     ``anlass_datum`` und ``anlass_thema`` (``event_quelle: "neu"``).
     **Kollision:** zwei verschiedene Anlaesse desselben Jahres derselben
     Kategorie mit gleichem neuen Namen — nach Anlass-ID sortiert behaelt der
     erste den einfachen Namen, jeder weitere bekommt den Anlass-Zusatz aus
     der ID in Klammern (``(02)`` aus ``2022-09-05_Anlass-02``). Dieselbe
     Anlass-ID zweimal ist **ein** Anlass und damit **ein** Ordner.
  6. **Zielpfad:** immer ueber ``foto_kategorien.ziel_pfad(jahr, kategorie,
     event)``. Das Jahr kommt aus dem Anlass (INT-Form des Feldes ``jahr``),
     sonst aus dem Datum; fehlt beides, zaehlt der Anlass als ``ohne_jahr``
     (gezaehlt, uebersprungen, nicht geraten).
  7. **Ordner-Bedarf:** der ganze Pfad ``Agent/Fotos/<Jahr>/<Kategorie>/
     <Event>`` wird als Kette geplant (jeder Teil einzeln, dedupliziert ueber
     alle Anlaesse hinweg): jeder Teil, der im Bestand nicht existiert, als
     ``art: "neu"``, vorhandene als ``art: "vorhanden"``. Kein ``createfolder``
     doppelt — der zweite Lauf ergibt denselben Plan.
  8. **Zuege:** eine Zeile je Datei mit ``thema_quelle, jahr, kategorie,
     event, event_quelle, von_ordner, von_name, ziel_pfad, fileid``, sortiert
     nach ``(jahr, kategorie, event, von_name)`` — reproduzierbar.

Vorbuchungen (warum hier trotzdem pCloud-Code steht):
  Fuer geplante Ordner und (wenn die Kennungen bekannt sind) fuer geplante
  Zuege entstehen **trockene** Vorbuchungen ueber ``pcloud_bewegungen``
  (``ordner_anlegen``, ``zielordner_finden_oder_bauen``, ``datei_verschieben``
  — alle mit ``trocken=True``). Sie senden nichts und schreiben nichts ins
  Manifest; sie zeigen nur, was ein Vollzug senden wuerde. Ist eine
  Eltern-Kennung im Trockenlauf nicht bekannt (die Ziel-Kennungen entstehen
  erst beim Anlegen), gibt es KEINE erfundene Kennung: die Vorbuchung ist
  ``null`` und traegt einen Klartext-Hinweis. Kennungen, die es wirklich gibt,
  kommen aus dem Bestand (``folderid`` der Kategorie) oder aus ``ziel_ids``
  (Parameter fuer den Vollzug N8).

Ausgabe:
  * ``--plan`` (Standard ``~/foto_sortierung/sortierplan.json``), atomar, nur
    ausserhalb des Repos, **nur** mit ``--schreiben`` wirklich geschrieben.
    Inhalt: ``{"stand", "trocken": true, "anlaesse", "ordner", "zuege",
    "zusammenfassung"}`` mit den Zaehlern ``zeilen, anlaesse, zuege,
    doppelung_gesamt, doppelung_ohne_anlass, doppelung_uebersprungen,
    ohne_thema, ohne_jahr, ordner_neu, ordner_vorhanden, events_neu,
    events_wiederverwendet, je_jahr, je_kategorie``.
  * Konsole: die Zahlenuebersicht als Klartext, ``--beispiele N`` Stichproben
    und eine Warnung, wenn ``ohne_jahr`` > 0 ist.
  * **Kein** Manifest-Eintrag: ``manifest.jsonl`` wird nicht angefasst (ein
    Test prueft, dass die Datei nach einem Lauf byte-identisch ist).

Aufruf (Kommandozeile)::

    python tools/foto_sortierung/foto_sortieren.py --beispiele 5
    python tools/foto_sortierung/foto_sortieren.py --mit-ids --beispiele 10
    python tools/foto_sortierung/foto_sortieren.py --schreiben

Ohne ``--schreiben`` wird **nichts** geschrieben (``--ohne-schreiben`` sagt das
ausdruecklich). Als Modul (Tests, Skripte): ``main(argv=[...], service=None)``.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import importlib.util
import json
import os
import re

HIER = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HIER))            # .../personal_ai_agent

# Vorgabepfade: ausserhalb des Repos — dort liegen private Ordnernamen.
STANDARD_BASIS = os.path.join(os.path.expanduser("~"), "foto_sortierung")
STANDARD_CSV = os.path.join(STANDARD_BASIS, "sortierschluessel_themen.csv")
STANDARD_KATEGORIEN = os.path.join(STANDARD_BASIS, "kategorien.json")
STANDARD_ZUORDNUNG = os.path.join(STANDARD_BASIS, "kategorie_zuordnung.json")
STANDARD_PLAN = os.path.join(STANDARD_BASIS, "sortierplan.json")
STANDARD_MANIFEST = os.path.join(STANDARD_BASIS, "manifest.jsonl")

# Die pCloud-Wurzel hat die Kennung 0 (so liest auch ``pcloud_service.liste``).
PCLOUD_WURZEL_ID = 0


def _modul_aus_pfad(pfad: str, name: str):
    """Ein Nachbarmodul per Pfad laden (Muster aus ``foto_kategorien.py``)."""
    spez = importlib.util.spec_from_file_location(name, pfad)
    if spez is None or spez.loader is None:
        raise RuntimeError(f"Modul nicht gefunden: {pfad}")
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


# Die beiden Nachbarmodule aus demselben Ordner: N6d (Kategorien/Pfade) und
# N6e (Vorschlaege, Bestand, Anlass-Lesen).
_kategorien = _modul_aus_pfad(os.path.join(HIER, "foto_kategorien.py"),
                              "foto_kategorien")
_event = _modul_aus_pfad(os.path.join(HIER, "event_abgleich.py"),
                         "event_abgleich")
# Das Sicherheitsnetz der pCloud: hier NUR fuer trockene Vorbuchungen.
_bewegungen = _modul_aus_pfad(
    os.path.join(os.path.dirname(HIER), "pcloud", "pcloud_bewegungen.py"),
    "pcloud_bewegungen")

pfad_saeubern = _kategorien.pfad_saeubern
ziel_pfad = _kategorien.ziel_pfad
ziel_kategorie = _kategorien.ziel_kategorie
SONSTIGES = _kategorien.SONSTIGES
ZIEL_BASIS = _kategorien.ZIEL_BASIS
JAHR_MIN = _kategorien.JAHR_MIN
JAHR_MAX = _kategorien.JAHR_MAX
KategorienFehler = _kategorien.KategorienFehler

OHNE_THEMA = _event.OHNE_THEMA
EventFehler = _event.EventFehler


class SortierFehler(Exception):
    """Fehler dieses Werkzeugs — deutsche Klartextmeldung, kein Absturz."""


# ── Spalten und feste Bezeichner ───────────────────────────────────────────

# Spalten des Sortierschluessels (Reihenfolge wie in der Datei).
SPALTEN = ("jahr", "monat", "tag", "datumquelle", "thema", "geraet", "ordner",
           "datei", "motiv", "doppelung", "bytes", "mb", "thema_quelle")

# Ohne diese Spalten ist der Sortierschluessel nicht lesbar — dann gibt es
# eine Klartextmeldung statt eines stillen Leerplans.
PFLICHTSPALTEN = ("thema_quelle", "ordner", "datei")

QUELLE_VORSCHLAG = "vorschlag"
QUELLE_NEU = "neu"

ART_NEU = "neu"
ART_VORHANDEN = "vorhanden"

EBENE_BASIS = "basis"
EBENE_JAHR = "jahr"
EBENE_KATEGORIE = "kategorie"
EBENE_EVENT = "event"
EBENEN = (EBENE_BASIS, EBENE_JAHR, EBENE_KATEGORIE, EBENE_EVENT)


# ── Kleine Helfer (tolerant lesen, nie raten) ─────────────────────────────

def _text(wert) -> str:
    """Ein Feld als Text lesen — Nicht-Text und ``None`` werden zu ``""``."""
    return wert.strip() if isinstance(wert, str) else ""


def _als_int_oder_none(wert):
    """Eine Zahl tolerant lesen — ``None`` statt Ausnahme, ``bool`` zaehlt nicht."""
    if isinstance(wert, bool):
        return None
    if isinstance(wert, int):
        return wert
    if isinstance(wert, str) and wert.strip():
        try:
            return int(wert.strip())
        except ValueError:
            return None
    return None


def _zahl(n) -> str:
    """Eine Zahl mit deutschen Tausenderpunkten (nur fuer die Ausgabe)."""
    try:
        return f"{int(n):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(n)


# ── 1. Den Sortierschluessel lesen ────────────────────────────────────────

def zeilen_lesen(pfad: str = STANDARD_CSV) -> list[dict]:
    """Die CSV-Zeilen des Sortierschluessels lesen (nur lesend, kein Netz).

    Erwartet die Spalten aus ``SPALTEN``; ``PFLICHTSPALTEN`` muessen vorhanden
    sein, sonst gibt es ``SortierFehler`` mit Klartextmeldung. Gelesen wird mit
    ``utf-8-sig`` (eine BOM im Kopf ist kein Fehler) und ``newline=""`` (der
    ``csv``-Leser soll die Zeilenenden selbst behandeln). Fehlende Datei und
    unlesbare CSV ergeben ebenfalls ``SortierFehler`` — es wird nichts geraten.
    """
    if not isinstance(pfad, str) or not pfad:
        raise SortierFehler("Kein Pfad fuer den Sortierschluessel angegeben.")
    if not os.path.isfile(pfad):
        raise SortierFehler(f"Sortierschluessel nicht gefunden: {pfad}")
    try:
        with open(pfad, encoding="utf-8-sig", newline="") as datei:
            leser = csv.DictReader(datei)
            kopf = [str(spalte) for spalte in (leser.fieldnames or [])]
            fehlend = [spalte for spalte in PFLICHTSPALTEN if spalte not in kopf]
            if fehlend:
                raise SortierFehler(
                    "Sortierschluessel ohne Pflichtspalte(n): "
                    + ", ".join(fehlend)
                    + f". Erwartet werden: {', '.join(SPALTEN)}."
                )
            zeilen: list[dict] = []
            for roh in leser:
                # Ein Feldueberhang erzeugt beim DictReader den Schluessel
                # ``None`` — der ist kein Spaltenname und faellt weg.
                zeilen.append({name: wert for name, wert in roh.items()
                               if isinstance(name, str)})
            return zeilen
    except SortierFehler:
        raise
    except csv.Error as problem:
        raise SortierFehler(
            "Sortierschluessel ist keine lesbare CSV "
            f"({problem.__class__.__name__}): {pfad}"
        ) from None
    except OSError as problem:
        raise SortierFehler(
            f"Sortierschluessel nicht lesbar ({problem.__class__.__name__}): {pfad}"
        ) from None


def quellordner_auflisten(zeilen) -> list[str]:
    """Die verschiedenen Quellordner in Reihenfolge des ersten Auftretens.

    Deterministisch (keine Mengen-Reihenfolge): so bleibt die Liste bei jedem
    Lauf gleich, auch wenn ``set`` intern anders sortieren wuerde.
    """
    gesehen: list[str] = []
    for zeile in zeilen if isinstance(zeilen, list) else []:
        if not isinstance(zeile, dict):
            continue
        ordner = _text(zeile.get("ordner"))
        if ordner and ordner not in gesehen:
            gesehen.append(ordner)
    return gesehen


# ── 2. Zeilen zu Anlaessen buendeln (Regeln 1 und 2) ──────────────────────

def anlaesse_buendeln(zeilen) -> dict:
    """CSV-Zeilen zu Anlaessen buendeln — rein, deterministisch, ohne I/O.

    Rueckgabe::

        {"anlaesse": [{"id", "titel", "jahr", "monat", "tag", "thema",
                       "dateien": [{"von_ordner", "von_name"}, …]}, …],
         "ohne_thema_quelle": int,        # Zeilen ohne Anlass-ID (uebersprungen)
         "doppelung_gesamt": int,         # ALLE Zeilen mit gefuellter Doppelung
         "doppelung_ohne_anlass": int,    # davon: Zeilen OHNE Anlass-ID
         "doppelung_uebersprungen": int}  # davon: Zeilen MIT Anlass-ID

    Regeln:
      * Die Reihenfolge der Anlaesse ist die Reihenfolge des ersten Auftretens
        in der CSV, die Reihenfolge der Dateien eines Anlasses die
        CSV-Reihenfolge — beides deterministisch.
      * Dieselbe Anlass-ID zweimal ergibt **einen** Anlass (und damit einen
        Ordner): die Zeilen werden angehaengt, nicht neu angelegt.
      * Eine Zeile ohne ``thema_quelle`` ist keinem Anlass zuzuordnen und wird
        gezaehlt und uebersprungen (Regel 1) — die Anlass-ID-Pruefung steht
        **zuerst**, solche Zeilen werden also nie eingeplant.
      * Eine Zeile mit gefuellter ``doppelung`` wird nicht eingeplant und
        gezaehlt (Regel 2) — geloescht wird nie etwas. Die Aufschluesselung:
        ``doppelung_gesamt`` zaehlt jede solche Zeile, unabhaengig davon, ob
        eine Anlass-ID da ist; ``doppelung_ohne_anlass`` zaehlt die Teilmenge in
        Zeilen OHNE Anlass-ID (ohnehin uebersprungen), ``doppelung_uebersprungen``
        die Teilmenge in Zeilen MIT Anlass-ID. Die beiden Teilmengen sind
        disjunkt — es zaehlt nichts doppelt.
      * Das Thema kommt aus der ersten Zeile des Anlasses mit gefuelltem
        ``thema`` (je Anlass ist es in diesem Bestand eines).
    """
    anlaesse: list[dict] = []
    nach_id: dict[str, dict] = {}
    ohne_thema_quelle = 0
    doppelung_gesamt = 0
    doppelung_ohne_anlass = 0
    doppelung_uebersprungen = 0

    for zeile in zeilen if isinstance(zeilen, list) else []:
        if not isinstance(zeile, dict):
            continue
        anlass_id = _text(zeile.get("thema_quelle"))
        hat_doppelung = bool(_text(zeile.get("doppelung")))
        if not anlass_id:
            ohne_thema_quelle += 1
            if hat_doppelung:
                # Gezaehlt wird sie (sie steht in der CSV), eingeplant nicht:
                # ohne Anlass-ID gibt es keinen Anlass, zu dem sie gehoerte.
                doppelung_gesamt += 1
                doppelung_ohne_anlass += 1
            continue
        if hat_doppelung:
            doppelung_gesamt += 1
            doppelung_uebersprungen += 1
            continue
        anlass = nach_id.get(anlass_id)
        if anlass is None:
            anlass = {
                "id": anlass_id,
                "titel": anlass_id,
                "jahr": _als_int_oder_none(zeile.get("jahr")),
                "monat": _als_int_oder_none(zeile.get("monat")),
                "tag": _als_int_oder_none(zeile.get("tag")),
                "thema": "",
                "dateien": [],
            }
            nach_id[anlass_id] = anlass
            anlaesse.append(anlass)
        if not anlass["thema"]:
            anlass["thema"] = _text(zeile.get("thema"))
        anlass["dateien"].append({
            "von_ordner": _text(zeile.get("ordner")),
            "von_name": _text(zeile.get("datei")),
        })

    return {"anlaesse": anlaesse,
            "ohne_thema_quelle": ohne_thema_quelle,
            "doppelung_gesamt": doppelung_gesamt,
            "doppelung_ohne_anlass": doppelung_ohne_anlass,
            "doppelung_uebersprungen": doppelung_uebersprungen}


# ── 3. Jahr, Kategorie und Event eines Anlasses (Regeln 3 bis 6) ─────────

def anlass_jahr(anlass):
    """Das Jahr eines Anlasses — ``None``, wenn keines erkennbar ist.

    Zuerst das Feld ``jahr`` (INT-Form), dann das aus dem Datum gelesene Jahr
    (``event_abgleich.anlass_teile`` liest auch den Datums-Block am Anfang von
    ``titel``, z. B. ``2025-06-06_Anlass-03``). Alles ausserhalb von
    ``JAHR_MIN``–``JAHR_MAX`` und unbrauchbare Werte ergeben ``None`` — es wird
    **nicht** geraten (Regel 6).
    """
    jahr = None
    if isinstance(anlass, dict):
        jahr = _als_int_oder_none(anlass.get("jahr"))
    if jahr is None or not JAHR_MIN <= jahr <= JAHR_MAX:
        jahr = _event.anlass_teile(anlass).get("jahr")
    if jahr is None or not JAHR_MIN <= jahr <= JAHR_MAX:
        return None
    return jahr


def ziel_kategorie_und_neu(anlass, bestand, zuordnung) -> tuple[str, bool]:
    """Ziel-Kategorie eines Anlasses und ob ihr Ordner **neu** ist (Regel 3).

    ``(kategorie, neu)``: ``kategorie_fuer_anlass`` liefert den Ordnernamen;
    ist er ``None`` oder kennt der Bestand ihn nicht (``unterordner_von`` gibt
    ``None``), gilt ``ziel_kategorie(SONSTIGES, zuordnung)`` und sonst der
    Rueckfall ``Sonstiges``. ``neu`` heisst: **diesen** Ordnernamen kennt der
    Bestand nicht, der Ordner muss also entstehen (im Plan ``art: "neu"``).
    """
    kategorie = _event.kategorie_fuer_anlass(anlass, zuordnung)
    if kategorie is None or _event.unterordner_von(kategorie, bestand) is None:
        kategorie = ziel_kategorie(SONSTIGES, zuordnung) or SONSTIGES
    return kategorie, _event.unterordner_von(kategorie, bestand) is None


def event_basisname(anlass) -> str:
    """Der neue Event-Name aus Datum und Thema (Regeln 4 und 5).

    ``pfad_saeubern(f"{datum} {thema}")`` mit Datum aus ``anlass_datum`` und
    Thema aus ``anlass_thema``. **Ohne Thema** gilt die Auflage aus N6b
    (Regel 4): der Rueckfall-Event ``Ohne-Thema`` — es wird nie abgebrochen.
    Auch wenn danach kein Name uebrig bleibt, kommt ``Ohne-Thema`` zurueck
    (ein leerer Ordnername waere kein Name).
    """
    if not _event.anlass_thema(anlass):
        return OHNE_THEMA
    datum = _event.anlass_datum(anlass)
    roh = f"{datum} {_event.anlass_thema(anlass)}".strip()
    if not roh:
        return OHNE_THEMA
    return pfad_saeubern(roh)


def event_waehlen(anlass, kategorie, bestand, auch_schwach: bool = False) -> dict:
    """Den Event eines Anlasses waehlen (Regel 5).

    Liefert ``vorschlag_fuer(anlass, unterordner_von(kategorie, bestand),
    auch_schwach=auch_schwach)`` einen **sicheren** Vorschlag, wird dessen Name
    genommen (``event_quelle: "vorschlag"``, bestehender Ordner wird
    wiederverwendet). Sonst gilt der neue Basisname (``event_quelle: "neu"``).

    ``auch_schwach`` ist standardmaessig ``False``: die Stufen ``jahr`` und
    ``spanne`` sind nur ein schwacher Hinweis und werden **nicht** verwendet.
    """
    unterordner = _event.unterordner_von(kategorie, bestand)
    vorschlag = _event.vorschlag_fuer(
        anlass, unterordner if isinstance(unterordner, list) else [],
        auch_schwach=auch_schwach)
    if isinstance(vorschlag, dict) and vorschlag.get("sicher"):
        name = _text(vorschlag.get("name")) or event_basisname(anlass)
        return {"event": name,
                "event_quelle": QUELLE_VORSCHLAG,
                "event_stufe": vorschlag.get("stufe"),
                "event_begruendung": vorschlag.get("begruendung") or ""}
    return {"event": event_basisname(anlass),
            "event_quelle": QUELLE_NEU,
            "event_stufe": None,
            "event_begruendung": "kein sicherer Vorschlag, neuer Ordner"}


def anlass_zusatz(anlass_id) -> str:
    """Der Zusatz aus einer Anlass-ID — die letzten Ziffern (``02`` aus ``…-02``)."""
    treffer = re.search(r"(\d+)\s*$", str(anlass_id or ""))
    return treffer.group(1) if treffer else ""


def kollisionen_aufloesen(ziele) -> list[dict]:
    """Gleiche neue Event-Namen je (Jahr, Kategorie) eindeutig machen (Regel 5).

    Zwei **verschiedene** Anlaesse desselben Jahres derselben Kategorie mit
    gleichem neuen Namen (und ohne Vorschlag) wuerden sonst in denselben Ordner
    laufen — der Plan waere mehrdeutig. Deterministisch nach Anlass-ID sortiert
    behaelt der **erste** den einfachen Namen; jeder weitere bekommt den
    Zusatz aus seiner ID in Klammern (``(02)`` aus ``2022-09-05_Anlass-02``),
    bei fehlendem Zusatz die laufende Nummer in der Gruppe.

    Wiederverwendete Vorschlaege sind **keine** Kollision: sie zeigen bewusst
    auf denselben bestehenden Ordner. Die Ziele werden an Ort und Stelle
    ergaenzt (``kollision: True``) und zurueckgegeben.
    """
    gruppen: dict[tuple, list[tuple[int, dict]]] = {}
    for nummer, ziel in enumerate(ziele if isinstance(ziele, list) else []):
        if not isinstance(ziel, dict) or ziel.get("event_quelle") != QUELLE_NEU:
            continue
        schluessel = (ziel.get("jahr"), ziel.get("kategorie"), ziel.get("event"))
        gruppen.setdefault(schluessel, []).append((nummer, ziel))

    for eintraege in gruppen.values():
        if len(eintraege) < 2:
            continue
        sortiert = sorted(eintraege,
                          key=lambda paar: (str(paar[1].get("id") or ""), paar[0]))
        for lauf, (_, ziel) in enumerate(sortiert[1:], start=2):
            zusatz = anlass_zusatz(ziel.get("id")) or f"{lauf:02d}"
            ziel["event"] = pfad_saeubern(f"{ziel.get('event')} ({zusatz})")
            ziel["kollision"] = True
    return ziele


def ziele_vergeben(anlaesse, bestand, zuordnung,
                   auch_schwach: bool = False) -> dict:
    """Jedem Anlass Jahr, Kategorie und Event zuweisen (Regeln 3 bis 6).

    Rueckgabe ``{"ziele", "ohne_jahr", "ohne_thema"}``:

      * ``ziele`` — je eingeplantem Anlass ein Eintrag mit ``id``, ``jahr``,
        ``kategorie``, ``kategorie_neu``, ``event``, ``event_quelle``,
        ``event_stufe``, ``event_neu``, ``thema``, ``datum`` und ``dateien``.
        Anlaesse **ohne Jahr** fehlen hier (gezaehlt in ``ohne_jahr``).
      * ``ohne_thema`` — Anzahl der Anlaesse ohne Thema (Rueckfall-Event),
        gezaehlt **vor** dem Jahr-Filter, damit die Zahl die Anlaesse meint und
        nicht die Restmenge.

    Die Reihenfolge der Ziele bleibt die Reihenfolge der Anlaesse; die
    Kollisionsaufloesung haengt nicht an ihr (sie sortiert nach Anlass-ID).
    """
    ziele: list[dict] = []
    ohne_jahr = 0
    ohne_thema = 0
    for anlass in anlaesse if isinstance(anlaesse, list) else []:
        if not isinstance(anlass, dict):
            continue
        thema = _event.anlass_thema(anlass)
        if not thema:
            ohne_thema += 1
        jahr = anlass_jahr(anlass)
        if jahr is None:
            ohne_jahr += 1
            continue
        kategorie, kategorie_neu = ziel_kategorie_und_neu(anlass, bestand,
                                                          zuordnung)
        wahl = event_waehlen(anlass, kategorie, bestand, auch_schwach=auch_schwach)
        ziel = {
            "id": str(anlass.get("id") or ""),
            "jahr": jahr,
            "kategorie": kategorie,
            "kategorie_neu": bool(kategorie_neu),
            "event": wahl["event"],
            "event_quelle": wahl["event_quelle"],
            "event_stufe": wahl["event_stufe"],
            "event_neu": wahl["event_quelle"] == QUELLE_NEU,
            "thema": thema,
            "datum": _event.anlass_datum(anlass),
            "dateien": list(anlass.get("dateien") or []),
            "kollision": False,
        }
        ziele.append(ziel)
    kollisionen_aufloesen(ziele)
    return {"ziele": ziele, "ohne_jahr": ohne_jahr, "ohne_thema": ohne_thema}


# ── 4. Die Ordnerkette planen (Regel 7) ──────────────────────────────────

def kategorie_kennung(kategorie, bestand):
    """Die ``folderid`` einer Kategorie aus dem Bestand — ``None``, wenn unbekannt."""
    if isinstance(bestand, dict):
        eintraege = bestand.get("kategorien")
    else:
        eintraege = bestand
    for eintrag in eintraege if isinstance(eintraege, list) else []:
        if not isinstance(eintrag, dict):
            continue
        if (str(eintrag.get("name") or "").strip().casefold()
                != str(kategorie or "").strip().casefold()):
            continue
        return _als_int_oder_none(eintrag.get("folderid"))
    return None


def _trocken_createfolder(ebene, name, eltern_id):
    """Eine TROCKENE Ordner-Vorbuchung ueber ``pcloud_bewegungen`` — oder ``None``.

    Ohne bekannte Eltern-Kennung gibt es **keine** Vorbuchung (und schon gar
    keine erfundene Kennung): der Aufruf wuerde eine Kennung brauchen, die erst
    beim Anlegen entsteht. Alle Aufrufe hier sind ``trocken=True`` — es wird
    nichts gesendet und nichts ins Manifest geschrieben.
    """
    if eltern_id is None:
        return None
    try:
        if ebene == EBENE_EVENT:
            # Finden ODER bauen: der Ordner kann beim Vollzug schon da sein.
            return _bewegungen.zielordner_finden_oder_bauen(
                eltern_id, name, trocken=True)
        return _bewegungen.ordner_anlegen(eltern_id, name, trocken=True)
    except _bewegungen.PCloudBewegungsFehler:
        return None


def ordnerkette(jahr, kategorie, event, bestand, ziel_ids=None) -> list[dict]:
    """Die Kette ``Agent/Fotos/<Jahr>/<Kategorie>/<Event>`` als Plandaten (Regel 7).

    Jeder Teil wird einzeln geplant (der Zielpfad kommt aus den Teilen, nicht
    umgekehrt) und traegt:

        {"pfad", "ebene", "name", "art", "eltern", "eltern_id",
         "createfolder", "hinweis"}

    ``art`` ist ``"vorhanden"`` nur, wenn der Bestand den Teil kennt: die
    Kategorie (``unterordner_von`` gibt eine Liste) bzw. der Event-Name in
    ihren Unterordnern (Vergleich ohne Gross-/Kleinschreibung). Basis- und
    Jahres-Ordner stehen im Bestand nicht — sie sind ``"neu"``. Jeder neue Teil
    bekommt eine **trockene** ``createfolder``-Vorbuchung, wenn die
    Eltern-Kennung bekannt ist (der erste Teil ``Agent`` haengt direkt unter der
    pCloud-Wurzel ``0``; die Kategorie-Kennung steht im Bestand; weitere
    Kennungen kann ``ziel_ids`` liefern). Sonst ist ``createfolder`` ``None``
    mit Klartext-``hinweis`` — Kennungen werden nicht erfunden.
    """
    unterordner = _event.unterordner_von(kategorie, bestand)
    kategorie_da = isinstance(unterordner, list)
    event_da = bool(kategorie_da) and any(
        str(eintrag).strip().casefold() == str(event).strip().casefold()
        for eintrag in unterordner if isinstance(eintrag, str))

    teile: list[tuple[str, str, bool]] = []
    for teil in str(ZIEL_BASIS).split("/"):
        if teil.strip():
            teile.append((pfad_saeubern(teil), EBENE_BASIS, False))
    teile.append((str(jahr), EBENE_JAHR, False))
    teile.append((pfad_saeubern(kategorie), EBENE_KATEGORIE, kategorie_da))
    teile.append((pfad_saeubern(event), EBENE_EVENT, event_da))

    bekannte = ziel_ids if isinstance(ziel_ids, dict) else {}
    ergebnis: list[dict] = []
    pfad = ""
    eltern_pfad = ""
    for name, ebene, vorhanden in teile:
        pfad = f"{pfad}/{name}" if pfad else name
        if ebene == EBENE_BASIS and not eltern_pfad:
            # "Agent" liegt direkt unter der pCloud-Wurzel (Kennung 0).
            eltern_id = PCLOUD_WURZEL_ID
        else:
            eltern_id = _als_int_oder_none(bekannte.get(eltern_pfad))
        art = ART_VORHANDEN if vorhanden else ART_NEU
        eintrag = {"pfad": pfad, "ebene": ebene, "name": name, "art": art,
                   "eltern": eltern_pfad, "eltern_id": eltern_id}
        if art == ART_NEU:
            eintrag["createfolder"] = _trocken_createfolder(ebene, name, eltern_id)
            if eintrag["createfolder"] is None:
                eintrag["hinweis"] = (
                    "Eltern-Kennung im Trockenlauf nicht bekannt — die "
                    "createfolder-Vorbuchung entsteht erst beim Vollzug (N8).")
        ergebnis.append(eintrag)
        eltern_pfad = pfad
    return ergebnis


# ── 5. Die Zuege planen (Regel 8) ────────────────────────────────────────

def datei_kennung(ids, von_ordner, von_name):
    """Die ``fileid`` einer Datei aus der Kennungs-Sammlung — sonst ``None``."""
    if not isinstance(ids, dict):
        return None
    eintrag = ids.get(von_ordner)
    if not isinstance(eintrag, dict):
        return None
    dateien = eintrag.get("dateien")
    if not isinstance(dateien, dict):
        return None
    if von_name in dateien:
        return _als_int_oder_none(dateien.get(von_name))
    for name, kennung in dateien.items():          # zweite Chance: andere Schreibweise
        if name.strip().casefold() == str(von_name).strip().casefold():
            return _als_int_oder_none(kennung)
    return None


def _ordner_kennung(ids, von_ordner):
    """Die Ordner-Kennung eines Quellordners aus der Kennungs-Sammlung."""
    if not isinstance(ids, dict):
        return None
    eintrag = ids.get(von_ordner)
    if not isinstance(eintrag, dict):
        return None
    return _als_int_oder_none(eintrag.get("folderid"))


def zuege_bauen(ziele, ids=None, ziel_ids=None) -> list[dict]:
    """Eine Zug-Zeile je Datei bauen, reproduzierbar sortiert (Regel 8).

    Je Zug: ``{thema_quelle, jahr, kategorie, event, event_quelle, von_ordner,
    von_name, ziel_pfad, fileid}`` — dazu ``vorbuchung`` (die **trockene**
    ``datei_verschieben``-Vorbuchung, sonst ``None``) und ``hinweis`` (warum es
    keine gibt). Sortiert nach ``(jahr, kategorie, event, von_name, von_ordner,
    thema_quelle)`` — die zusaetzlichen Schluessel machen die Reihenfolge auch
    bei gleichen Dateinamen eindeutig.

    Eine Vorbuchung entsteht nur, wenn Datei- **und** Ziel-Kennung wirklich
    bekannt sind. Ohne ``--mit-ids`` sind die Datei-Kennungen unbekannt und
    ``fileid`` ist ``None``: der Plan laeuft trotzdem weiter (kein Abbruch).
    """
    quellen = ids if isinstance(ids, dict) else {}
    ziel_kennungen = ziel_ids if isinstance(ziel_ids, dict) else {}
    zuege: list[dict] = []
    for ziel in ziele if isinstance(ziele, list) else []:
        if not isinstance(ziel, dict):
            continue
        pfad = ziel_pfad(ziel["jahr"], ziel["kategorie"], ziel["event"])
        ziel_id = _als_int_oder_none(ziel_kennungen.get(pfad))
        for datei in ziel.get("dateien") or []:
            von_ordner = _text(datei.get("von_ordner"))
            von_name = _text(datei.get("von_name"))
            fileid = datei_kennung(quellen, von_ordner, von_name)
            von_folderid = _ordner_kennung(quellen, von_ordner)
            vorbuchung = None
            if fileid is None:
                hinweis = ("Datei-Kennung unbekannt (ohne --mit-ids) — keine "
                           "Vorbuchung.")
            elif ziel_id is None:
                hinweis = ("Ziel-Kennung im Trockenlauf nicht bekannt — die "
                           "Verschiebe-Vorbuchung entsteht erst beim Vollzug (N8).")
            else:
                try:
                    vorbuchung = _bewegungen.datei_verschieben(
                        fileid, ziel_id, name=von_name, von_folderid=von_folderid,
                        von_pfad=von_ordner, nach_pfad=pfad, trocken=True)
                    hinweis = ""
                except _bewegungen.PCloudBewegungsFehler as problem:
                    hinweis = f"keine Vorbuchung: {problem}"
            zuege.append({
                "thema_quelle": ziel.get("id") or "",
                "jahr": ziel["jahr"],
                "kategorie": ziel["kategorie"],
                "event": ziel["event"],
                "event_quelle": ziel["event_quelle"],
                "von_ordner": von_ordner,
                "von_name": von_name,
                "ziel_pfad": pfad,
                "fileid": fileid,
                "vorbuchung": vorbuchung,
                "hinweis": hinweis,
            })
    zuege.sort(key=lambda zug: (zug["jahr"], zug["kategorie"], zug["event"],
                                zug["von_name"], zug["von_ordner"],
                                zug["thema_quelle"]))
    return zuege


# ── 6. Den ganzen Plan bauen ─────────────────────────────────────────────

def plan_bauen(zeilen, bestand, zuordnung, ids=None, ziel_ids=None,
               auch_schwach: bool = False) -> dict:
    """Den ganzen Sortierplan bauen — rein, ohne I/O, ohne Netz (``trocken: True``).

    Ablauf: buendeln (Regeln 1/2) -> Ziele vergeben (3–6) -> Ordnerkette
    dedupliziert planen (7) -> Zuege bauen (8) -> Zaehler.

    Rueckgabe (ohne ``stand`` — den setzt erst ``plan_schreiben``)::

        {"trocken": True, "anlaesse": [...], "ordner": [...], "zuege": [...],
         "zusammenfassung": {"zeilen", "anlaesse", "zuege",
                             "doppelung_gesamt", "doppelung_ohne_anlass",
                             "doppelung_uebersprungen", "ohne_thema",
                             "ohne_jahr", "ordner_neu", "ordner_vorhanden",
                             "events_neu", "events_wiederverwendet",
                             "je_jahr", "je_kategorie"}}

    Die ``ordner``-Liste ist ueber **alle** Anlaesse hinweg dedupliziert (kein
    ``createfolder`` doppelt, auch nicht ueber Anlaesse hinweg) und nach Pfad
    sortiert; trifft ein Pfad einmal als ``neu`` und einmal als ``vorhanden``
    zusammen, gewinnt ``neu`` (die vorsichtigere Annahme).
    """
    gebuendelt = anlaesse_buendeln(zeilen)
    vergabe = ziele_vergeben(gebuendelt["anlaesse"], bestand, zuordnung,
                             auch_schwach=auch_schwach)
    ziele = vergabe["ziele"]

    ordner: dict[str, dict] = {}
    for ziel in ziele:
        for teil in ordnerkette(ziel["jahr"], ziel["kategorie"], ziel["event"],
                                bestand, ziel_ids=ziel_ids):
            vorhanden = ordner.get(teil["pfad"])
            if vorhanden is None:
                ordner[teil["pfad"]] = teil
            elif teil["art"] == ART_NEU:
                vorhanden["art"] = ART_NEU
                vorhanden["createfolder"] = teil.get("createfolder")
                if teil.get("hinweis"):
                    vorhanden["hinweis"] = teil["hinweis"]
    ordner_liste = [ordner[pfad] for pfad in sorted(ordner)]

    anlass_liste = sorted(
        ({"thema_quelle": ziel["id"],
          "jahr": ziel["jahr"],
          "kategorie": ziel["kategorie"],
          "kategorie_neu": ziel["kategorie_neu"],
          "event": ziel["event"],
          "event_quelle": ziel["event_quelle"],
          "event_stufe": ziel["event_stufe"],
          "thema": ziel["thema"],
          "datum": ziel["datum"],
          "dateien": len(ziel.get("dateien") or []),
          "kollision": ziel["kollision"]} for ziel in ziele),
        key=lambda eintrag: (eintrag["jahr"], eintrag["kategorie"],
                             eintrag["event"], eintrag["thema_quelle"]))

    zuege = zuege_bauen(ziele, ids=ids, ziel_ids=ziel_ids)

    je_jahr: dict[str, int] = {}
    je_kategorie: dict[str, int] = {}
    for ziel in ziele:
        je_jahr[str(ziel["jahr"])] = je_jahr.get(str(ziel["jahr"]), 0) + 1
        je_kategorie[ziel["kategorie"]] = je_kategorie.get(ziel["kategorie"], 0) + 1

    zusammenfassung = {
        "zeilen": len(zeilen) if isinstance(zeilen, list) else 0,
        "anlaesse": len(anlass_liste),
        "zuege": len(zuege),
        "doppelung_gesamt": gebuendelt["doppelung_gesamt"],
        "doppelung_ohne_anlass": gebuendelt["doppelung_ohne_anlass"],
        "doppelung_uebersprungen": gebuendelt["doppelung_uebersprungen"],
        "ohne_thema": vergabe["ohne_thema"],
        "ohne_jahr": vergabe["ohne_jahr"],
        "ordner_neu": sum(1 for eintrag in ordner_liste
                          if eintrag["art"] == ART_NEU),
        "ordner_vorhanden": sum(1 for eintrag in ordner_liste
                                if eintrag["art"] == ART_VORHANDEN),
        "events_neu": sum(1 for ziel in ziele
                          if ziel["event_quelle"] == QUELLE_NEU),
        "events_wiederverwendet": sum(1 for ziel in ziele
                                      if ziel["event_quelle"] == QUELLE_VORSCHLAG),
        "je_jahr": {jahr: je_jahr[jahr] for jahr in sorted(je_jahr)},
        "je_kategorie": {name: je_kategorie[name]
                         for name in sorted(je_kategorie)},
    }

    return {"trocken": True,
            "anlaesse": anlass_liste,
            "ordner": ordner_liste,
            "zuege": zuege,
            "zusammenfassung": zusammenfassung}


# ── 7. Den Plan schreiben (nur mit --schreiben, nur ausserhalb des Repos) ─

def plan_schreiben(pfad: str = STANDARD_PLAN, inhalt=None,
                   schreiben: bool = False) -> dict:
    """Den Plan schreiben — atomar, nur ausserhalb des Repos, nur bei Aenderung.

    ``pfad`` MUSS ausserhalb des Repos liegen; die Pruefung uebernimmt
    ``foto_kategorien._pruefe_ziel_ausserhalb_repo`` (Ziel im Repo: deutsche
    Meldung und ``SystemExit(2)`` — es wird nichts geschrieben).

    Geschrieben wird ``{..., "stand": <Zeit>}`` atomar (temp-Datei +
    ``os.replace``) und **nur bei echter Aenderung**: Der neue Inhalt ohne
    ``stand`` wird mit dem vorhandenen Inhalt ohne ``stand`` verglichen; ist
    beides gleich, bleibt die Datei byte-identisch (Meldung "unveraendert") und
    der zweite Lauf schreibt nicht. ``schreiben=False`` (Standard) zeigt nur
    an, was geschrieben wuerde.

    Rueckgabe: ``{"geschrieben", "unveraendert", "trocken", "ziel", "zuege"}``.
    """
    ziel = _kategorien._pruefe_ziel_ausserhalb_repo(pfad)
    daten = dict(inhalt) if isinstance(inhalt, dict) else {}
    daten.pop("stand", None)
    anzahl = len(daten.get("zuege") or [])

    vorhanden = None
    if os.path.isfile(ziel):
        try:
            with open(ziel, encoding="utf-8") as datei:
                vorhanden = json.load(datei)
        except (OSError, ValueError):
            vorhanden = None                      # kaputt -> wird ersetzt

    if (vorhanden is not None
            and _kategorien._inhalt_ohne_stand(vorhanden)
            == _kategorien._inhalt_ohne_stand(daten)):
        print(f"Plan unveraendert: {ziel} ({anzahl} Zuege)")
        return {"geschrieben": False, "unveraendert": True,
                "trocken": not schreiben, "ziel": ziel, "zuege": anzahl}

    daten["stand"] = datetime.datetime.now().isoformat(timespec="seconds")
    if not schreiben:
        print(f"Trockenlauf: {ziel} wuerde geschrieben ({anzahl} Zuege).")
        return {"geschrieben": False, "unveraendert": False, "trocken": True,
                "ziel": ziel, "zuege": anzahl}

    _kategorien._schreibe_atomar(ziel, daten)
    print(f"Plan geschrieben: {ziel} ({anzahl} Zuege)")
    return {"geschrieben": True, "unveraendert": False, "trocken": False,
            "ziel": ziel, "zuege": anzahl}


# ── 8. Kennungen lesend aus der pCloud holen (nur mit --mit-ids) ─────────

def pfad_teile(ordner) -> list[str]:
    """Die Teile eines Ordnerpfads ohne Laufwerks-Kennung (``P:/A/B`` -> ``A/B``)."""
    text = str(ordner or "").replace("\\", "/").strip()
    teile = [teil for teil in text.split("/") if teil and teil not in (".", "..")]
    if teile and re.fullmatch(r"[A-Za-z]:", teile[0]):
        teile = teile[1:]
    return teile


def ordner_kennung(service, ordner):
    """Die Kennung eines Ordners ueber den Pfad aufloesen — LESEND, sonst ``None``.

    Von der Wurzel (``0``) abwaerts, Ebene fuer Ebene mit ``service.liste``
    (je Ebene genau ein Aufruf, keine Rekursion). Findet sich ein Teil nicht
    oder antwortet der Dienst mit einem Fehler, kommt ``None`` zurueck statt
    einer Ausnahme — der Plan laeuft dann mit ``fileid: null`` weiter.
    """
    if service is None:
        return None
    eltern = PCLOUD_WURZEL_ID
    for teil in pfad_teile(ordner):
        try:
            eintraege = service.liste(eltern)
        except Exception:
            return None
        gefunden = None
        for eintrag in eintraege if isinstance(eintraege, list) else []:
            if not isinstance(eintrag, dict) or not eintrag.get("ist_ordner"):
                continue
            if (str(eintrag.get("name") or "").strip().casefold()
                    == teil.casefold()):
                gefunden = eintrag
                break
        if gefunden is None:
            return None
        eltern = _als_int_oder_none(gefunden.get("folderid"))
        if eltern is None:
            return None
    return eltern


def service_ids_holen(service, ordner_liste) -> dict:
    """Dateiname -> ``fileid`` je Quellordner holen — LESEND, ohne Download.

    Rueckgabe ``{ordner: {"folderid": int|None, "dateien": {name: fileid}}}``.
    Je Quellordner werden genau zwei Dinge gelesen: sein eigener ``listfolder``
    (Dateien) und der Weg dorthin. Es wird nichts heruntergeladen, nichts
    geschrieben und nichts ins Manifest gebucht; ein Ordner, der nicht
    gefunden wird oder einen Fehler liefert, bekommt einen leeren Eintrag
    (``fileid: null`` im Plan) statt eines Abbruchs.
    """
    ergebnis: dict[str, dict] = {}
    for ordner in ordner_liste if isinstance(ordner_liste, list) else []:
        kennung = ordner_kennung(service, ordner)
        dateien: dict[str, int | None] = {}
        if kennung is not None:
            try:
                for eintrag in service.liste(kennung) or []:
                    if not isinstance(eintrag, dict) or eintrag.get("ist_ordner"):
                        continue
                    name = str(eintrag.get("name") or "")
                    if name:
                        dateien[name] = _als_int_oder_none(eintrag.get("fileid"))
            except Exception:
                dateien = {}
        ergebnis[ordner] = {"folderid": kennung, "dateien": dateien}
    return ergebnis


def schluessel_da() -> bool:
    """Ist ein pCloud-Schluessel vorhanden (Umgebung oder ``backend/.env``)?

    Geprueft wird nur, OB es einen Wert gibt — der Wert selbst wird nie
    gelesen, nie ausgegeben und nie in eine Datei geschrieben.
    """
    if (os.environ.get("PCLOUD_TOKEN") or "").strip():
        return True
    env_datei = os.path.join(REPO, "backend", ".env")
    if not os.path.isfile(env_datei):
        return False
    try:
        with open(env_datei, encoding="utf-8", errors="replace") as datei:
            for zeile in datei:
                zeile = zeile.strip()
                if zeile.startswith("#") or "=" not in zeile:
                    continue
                name, wert = zeile.split("=", 1)
                if name.strip() == "PCLOUD_TOKEN" and wert.strip().strip("\"'"):
                    return True
    except OSError:
        return False
    return False


# ── 9. Ausgabe auf der Konsole (Klartext, deutsch) ───────────────────────

def zahlenzeile(zusammenfassung) -> str:
    """Die eine Zahlenzeile der Uebersicht (deutsche Tausenderpunkte)."""
    z = zusammenfassung if isinstance(zusammenfassung, dict) else {}
    return (f"{_zahl(z.get('anlaesse'))} Anlaesse · {_zahl(z.get('zeilen'))} Zeilen · "
            f"{_zahl(z.get('zuege'))} Zuege · {_zahl(z.get('ordner_neu'))} Ordner neu · "
            f"{_zahl(z.get('events_wiederverwendet'))} Events wiederverwendet")


def uebersicht_text(zusammenfassung, ohne_thema_quelle: int = 0) -> str:
    """Die Zahlenuebersicht als mehrzeiliger Klartext (feste Reihenfolge).

    Alle Zaehler des Auftrags stehen einzeln da: Zeilen, Anlaesse, Zuege,
    Doppelungen (aufgeschluesselt in ``doppelung_gesamt``,
    ``doppelung_ohne_anlass`` und ``doppelung_uebersprungen``), ohne_thema,
    ohne_jahr, ordner_neu, ordner_vorhanden, events_neu,
    events_wiederverwendet und je Jahr.

    Die Doppelungs-Zeile nennt bewusst die Gesamtzahl zuerst: die blosse Zahl
    der uebersprungenen Doppelungen liest sich sonst, als gaebe es in der CSV
    nur diese — dabei liegen die meisten in Zeilen ohne Anlass-ID, die ohnehin
    uebersprungen werden.
    """
    z = zusammenfassung if isinstance(zusammenfassung, dict) else {}
    zeilen = [
        zahlenzeile(z),
        f"Zeilen: {_zahl(z.get('zeilen'))}   "
        f"Anlaesse: {_zahl(z.get('anlaesse'))}   Zuege: {_zahl(z.get('zuege'))}",
        f"Doppelungen: {_zahl(z.get('doppelung_gesamt'))} in der CSV · "
        f"davon {_zahl(z.get('doppelung_ohne_anlass'))} ohne Anlass-ID "
        f"(ohnehin uebersprungen) · "
        f"{_zahl(z.get('doppelung_uebersprungen'))} in geplanten Anlaessen "
        f"uebersprungen",
        f"Anlaesse ohne Thema: {_zahl(z.get('ohne_thema'))}   "
        f"Anlaesse ohne Jahr: {_zahl(z.get('ohne_jahr'))}",
        f"Ordner neu: {_zahl(z.get('ordner_neu'))}   "
        f"Ordner vorhanden: {_zahl(z.get('ordner_vorhanden'))}   "
        f"Events neu: {_zahl(z.get('events_neu'))}   "
        f"Events wiederverwendet: {_zahl(z.get('events_wiederverwendet'))}",
    ]
    if ohne_thema_quelle:
        zeilen.append(f"Zeilen ohne Anlass-ID (uebersprungen): "
                      f"{_zahl(ohne_thema_quelle)}")
    je_jahr = z.get("je_jahr")
    if isinstance(je_jahr, dict) and je_jahr:
        zeilen.append("Je Jahr: " + "   ".join(
            f"{jahr}: {_zahl(je_jahr[jahr])}" for jahr in sorted(je_jahr)))
    return "\n".join(zeilen)


def beispiele_zeilen(plan, anzahl: int = 5) -> list[str]:
    """Bis zu ``anzahl`` Klartextzeilen aus den Zuegen (Stichprobe)."""
    zuege = plan.get("zuege") if isinstance(plan, dict) else None
    zeilen: list[str] = []
    for zug in (zuege if isinstance(zuege, list) else [])[:max(0, anzahl)]:
        kennung = zug.get("fileid")
        zeilen.append(f"  {zug.get('von_ordner')}/{zug.get('von_name')}"
                      f"  ->  {zug.get('ziel_pfad')}"
                      + (f"   (fileid {kennung})" if kennung is not None
                         else "   (fileid unbekannt)"))
    return zeilen


# ── 10. Kommandozeile ────────────────────────────────────────────────────

def main(argv=None, service=None) -> int:
    """Kommandozeilen-Teil: Plan bauen, Zahlen zeigen, nur mit --schreiben ablegen.

    ``service`` (pCloud-Dienst) ist fuer Tests injizierbar; ohne ihn wird er
    erst geladen, wenn ``--mit-ids`` an ist und wirklich Kennungen geholt
    werden sollen. Ohne Schluessel laeuft der Plan mit ``fileid: null`` weiter.
    """
    zerleger = argparse.ArgumentParser(
        description="Foto-Sortieren N7: TROCKENLAUF — baut nur einen Plan "
                    "(welche Ordner entstehen, welche Datei wohin zieht) und "
                    "sortiert nichts. Kein Schreibaufruf, kein Manifest.")
    zerleger.add_argument("--csv", dest="csv", default=STANDARD_CSV,
                          help="Sortierschluessel-Themen (CSV, ausserhalb des Repos)")
    zerleger.add_argument("--kategorien-pfad", dest="kategorien_pfad",
                          default=STANDARD_KATEGORIEN,
                          help="Bestandsdatei (ausserhalb des Repos)")
    zerleger.add_argument("--zuordnung-pfad", dest="zuordnung_pfad",
                          default=STANDARD_ZUORDNUNG,
                          help="Zuordnung Bucket -> Ordner (ausserhalb des Repos)")
    zerleger.add_argument("--plan", dest="plan", default=STANDARD_PLAN,
                          help="Zieldatei des Plans (ausserhalb des Repos)")
    zerleger.add_argument("--beispiele", type=int, default=5, dest="beispiele",
                          help="so viele Stichproben-Zuege zeigen (Standard 5, 0 = keine)")
    zerleger.add_argument("--mit-ids", dest="mit_ids", action="store_true",
                          default=None,
                          help="die Quellordner LESEND auflisten, um fileid zu "
                               "fuellen (Standard: an, wenn ein Schluessel da ist)")
    zerleger.add_argument("--ohne-ids", dest="mit_ids", action="store_false",
                          help="keine pCloud-Abfrage: fileid bleibt null")
    zerleger.add_argument("--auch-schwach", dest="auch_schwach",
                          action="store_true",
                          help="auch die Stufen 'jahr'/'spanne' als Event-Vorschlag "
                               "zulassen (dann nur, wenn der Vorschlag sicher ist)")
    zerleger.add_argument("--schreiben", action="store_true",
                          help="den Plan wirklich schreiben (atomar, nur ausserhalb "
                               "des Repos)")
    zerleger.add_argument("--ohne-schreiben", dest="ohne_schreiben",
                          action="store_true",
                          help="ausdruecklich nichts schreiben (Standard)")
    args = zerleger.parse_args(argv)

    schreiben = bool(args.schreiben) and not bool(args.ohne_schreiben)
    mit_ids = args.mit_ids if args.mit_ids is not None else schluessel_da()

    try:
        bestand, zuordnung = _event.bestand_und_zuordnung(args.kategorien_pfad,
                                                          args.zuordnung_pfad)
        zeilen = zeilen_lesen(args.csv)

        print("Foto-Sortieren N7 — TROCKENLAUF (es wird NICHTS sortiert)")
        print(f"Sortierschluessel: {args.csv} ({_zahl(len(zeilen))} Zeilen)")
        print(f"Bestand: {args.kategorien_pfad}")
        print(f"Zuordnung: {args.zuordnung_pfad}")
        print(f"Manifest: {STANDARD_MANIFEST} — nicht angeruehrt "
              "(Trockenlauf, kein Eintrag)")

        ids: dict = {}
        if mit_ids:
            dienst = service
            if dienst is None:
                try:
                    dienst = _kategorien.pcloud_service_laden()
                except Exception as problem:
                    print("Hinweis: pCloud-Dienst nicht verfuegbar "
                          f"({problem.__class__.__name__}) — der Plan laeuft mit "
                          "fileid null weiter.")
                    dienst = None
            if dienst is not None:
                quellen = quellordner_auflisten(zeilen)
                ids = service_ids_holen(dienst, quellen)
                print(f"Quellordner gelesen (nur lesend): {len(quellen)}, "
                      f"davon gefunden: "
                      f"{sum(1 for wert in ids.values() if wert.get('folderid') is not None)}")
        else:
            print("Ohne Kennungsabfrage: fileid bleibt null (kein Netzaufruf).")

        plan = plan_bauen(zeilen, bestand, zuordnung, ids=ids,
                          auch_schwach=args.auch_schwach)
        zusammenfassung = plan["zusammenfassung"]

        print(uebersicht_text(zusammenfassung,
                              anlaesse_buendeln(zeilen)["ohne_thema_quelle"]))
        if zusammenfassung.get("ohne_jahr", 0) > 0:
            print(f"WARNUNG: {_zahl(zusammenfassung['ohne_jahr'])} Anlaesse ohne "
                  "Jahr wurden uebersprungen (nicht geraten).")

        if args.beispiele:
            print(f"Stichprobe ({args.beispiele}):")
            for zeile in beispiele_zeilen(plan, args.beispiele):
                print(zeile)

        if schreiben:
            ergebnis = plan_schreiben(args.plan, plan, schreiben=True)
            print(f"Zuege im Plan: {_zahl(ergebnis['zuege'])}")
        else:
            print("Ohne --schreiben wurde NICHTS geschrieben.")
        return 0
    except (SortierFehler, KategorienFehler, EventFehler) as problem:
        print(f"Fehler: {problem}")
        return 2
    except SystemExit:
        raise


if __name__ == "__main__":
    raise SystemExit(main())
