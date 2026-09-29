"""Personen-Register (E17, 29.09.2026): wer ist auf welchem Bild, wie gross, wie oft.

Wozu dieses Werkzeug:
  ``personen_cluster`` buendelt Gesichter zu Gruppen (``Person_001`` …), legt
  aber je Gesicht **keine** Zuordnungsdatei ab: persistiert wird nur der
  Kennungs-Altbestand (``kennungen.json``, Mittelpunkte). Die Zuordnung
  Gesicht -> Kennung entsteht in ``personen_cluster.lauf_rechnen`` (Feld
  ``kennungen[i]["indizes"]`` = Stellen in ``eintraege``; jeder Eintrag traegt
  ``bild_id`` + ``index`` = Stelle des Gesichts im Bild). Dieses Werkzeug
  rechnet genau diesen Lauf (gegen den Altbestand, damit die Kennungen stabil
  bleiben) und macht daraus ein **Register**, das Fragen wie „nur David und ich"
  beantwortet. Gesichter werden ueber ``bild_id`` + ``index`` referenziert; die
  ``bbox`` steht zusaetzlich in der Ausgabe.

  Wiederverwendet (kein eigener Parser): ``personen_andocken.vektoren_lesen``
  (Vektorzeilen inkl. ``metadaten``), ``personen_andocken.bestaetigung_lesen``
  (Namen aus ``personen_bestaetigt.json``), ``personen_cluster.katalog_lesen`` /
  ``katalog_personen`` (Namen aus dem Katalog), ``lauf_rechnen``,
  ``gesichter_bewerten``, ``pruefe_ausserhalb_repo`` und das atomare
  ``personen_andocken.schreiben``.

Namen: Bestaetigungsdatei vor Katalog, sonst bleibt die Kennung
  (``Person_017``) — es wird nichts geraten. Eine Person mit Name gilt als
  **bekannt**, eine ohne als **unbenannt**.

Ausgabe 1 ``bild_person.jsonl`` (Ableitung, atomar neu, ein Objekt je erkanntem
Gesicht)::

    {"bild_id", "index", "person", "cluster", "bbox", "gesichtsanteil",
     "score", "zaehlt_mit", "aufnahme"}

  ``person`` = Name oder Kennung; ``cluster`` = Kennung (``null`` fuer ein
  Gesicht ohne Gruppe: Rauschen, Menge, zu klein); ``gesichtsanteil`` =
  Gesichtsflaeche / Bildflaeche (4 Stellen); ``aufnahme`` aus ``metadaten``.

Die zwei Schwellen von ``zaehlt_mit`` (beide muessen erfuellt sein):
  * ``--min-anteil`` (Standard 0,004): ein Gesicht mit 4 Promille der
    Bildflaeche ist bei quadratischer Box etwa 6 % der Bildbreite breit
    (Wurzel aus 0,004 ~ 0,063). Kleinere Gesichter sind Passanten oder
    Menschen im Hintergrund. Sie sollen ein Foto „nur wir beide" **nicht**
    zerstoeren: sie zaehlen im Register mit (Ausgabe 1), aber nicht als
    Person des Bildes.
  * ``--min-score`` (Standard 0,8): das Cluster-Werkzeug nimmt ab 0,6 auf, um
    Gesichter nicht zu verlieren. Fuer die Frage „wer ist wirklich drauf" gilt
    strenger: unter 0,8 sind Detektor-Treffer haeufig Teilgesichter oder
    Fehlgriffe, und ein Fehlgriff darf weder eine Person zufuegen noch ein
    „genau" kippen.

Ausgabe 2 ``personen_uebersicht.json``: je Person ``anzahl_bilder`` (alle
  Gesichter), ``anzahl_bilder_wichtig`` (nur ``zaehlt_mit``), ``erstes`` /
  ``letztes`` (Aufnahme), ``haeufigste_begleiter`` (Top 10, nur ``zaehlt_mit``
  auf demselben Bild, mit Anzahl) — dazu je Bild-Statistik die Verteilung
  ``personen_wichtig`` (0, 1, 2, 3, 4+).

Abfrage: ``bilder_mit(register, personen, modus)`` — ``"genau"``: die wichtigen
  Personen des Bildes sind exakt diese Menge; ``"mindestens"``: alle genannten
  dabei, andere erlaubt. Ein wichtiges Gesicht **ohne Namen** ist eine eigene,
  fremde Person (bei ``"genau"`` schlaegt es an, ausser man fragt ausdruecklich
  nach seiner Kennung). Ergebnis chronologisch, fehlendes Datum ans Ende.

Was dieses Werkzeug bewusst NICHT tut:
  * Kein Bild, kein Netz, kein Loeschen (nur die eigene temp-Datei beim
    atomaren Schreiben), keine Aenderung an Vektoren/Kennungen/Katalog.
  * Kein Schreiben ins Repo: Ziel im Repo -> Klartextmeldung, Exit 2.
  * Keine Namen auf der Konsole: gezeigt werden nur Zaehler.
  * Standard ist der Trockenlauf; geschrieben wird nur mit ``--schreiben``.

Aufruf::

    python tools/foto_sortierung/personen_register.py \
        --vektoren ~/foto_sortierung/personen_vektoren_n9e.jsonl \
        --vektoren ~/foto_sortierung/personen_vektoren_video.jsonl
    python tools/foto_sortierung/personen_register.py --schreiben

Als Modul: ``main(argv=[...])``.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))


def _nachbar(name: str):
    """Ein Nachbarmodul importieren; im Test-Ladeweg ueber den Dateipfad."""
    try:
        return __import__(name)
    except ImportError:                          # pragma: no cover
        spez = importlib.util.spec_from_file_location(
            name, os.path.join(HIER, name + ".py"))
        if spez is None or spez.loader is None:  # pragma: no cover
            raise
        modul = importlib.util.module_from_spec(spez)
        spez.loader.exec_module(modul)
        return modul


_cluster = _nachbar("personen_cluster")
_andocken = _nachbar("personen_andocken")

pruefe_ausserhalb_repo = _cluster.pruefe_ausserhalb_repo
# Beide Klassen fangen: je nach Ladeweg (Import/Dateipfad) sind es zwei Kopien.
PersonenFehler = (_cluster.PersonenFehler, _andocken.PersonenFehler)

STANDARD_BASIS = os.path.join(os.path.expanduser("~"), "foto_sortierung")
STANDARD_AUSGABE_BILD_PERSON = os.path.join(STANDARD_BASIS, "bild_person.jsonl")
STANDARD_AUSGABE_UEBERSICHT = os.path.join(STANDARD_BASIS,
                                           "personen_uebersicht.json")

MIN_ANTEIL = 0.004
MIN_SCORE = 0.8
BEGLEITER_ANZAHL = 10
MODUS_GENAU = "genau"
MODUS_MINDESTENS = "mindestens"
VERTEILUNG_SCHLUESSEL = ("0", "1", "2", "3", "4+")


def _text(wert) -> str:
    return wert.strip() if isinstance(wert, str) else ""


# ── 1. Bilder: Dubletten, Aufnahme ────────────────────────────────────────

def bilder_vereinen(zeilen) -> tuple[list[dict], int]:
    """Vektorzeilen ohne Dubletten: je ``bild_id`` gewinnt die erste Zeile.

    Rueckgabe ``(bilder, dubletten)``. Zeilen ohne brauchbare ``bild_id`` fallen
    weg (werden nicht geraten und nicht mitgezaehlt).
    """
    gesehen: set[str] = set()
    bilder: list[dict] = []
    dubletten = 0
    for zeile in zeilen or []:
        if not isinstance(zeile, dict):
            continue
        kennung = zeile.get("bild_id")
        if isinstance(kennung, bool) or not isinstance(kennung, (str, int)):
            continue
        bild_id = str(kennung).strip()
        if not bild_id:
            continue
        if bild_id in gesehen:
            dubletten += 1
            continue
        gesehen.add(bild_id)
        bilder.append(dict(zeile, bild_id=bild_id))
    return bilder, dubletten


def aufnahme_von(zeile) -> str | None:
    """Das Aufnahmedatum aus ``metadaten`` (Text) oder ``None``."""
    metadaten = zeile.get("metadaten") if isinstance(zeile, dict) else None
    aufnahme = metadaten.get("aufnahme") if isinstance(metadaten, dict) else None
    return aufnahme.strip() if isinstance(aufnahme, str) and aufnahme.strip() \
        else None


# ── 2. Gesicht -> Kennung -> Name ─────────────────────────────────────────

def zuordnung_bauen(lauf) -> dict:
    """``{(bild_id, index): kennung}`` aus einem ``lauf_rechnen``-Ergebnis."""
    daten = lauf if isinstance(lauf, dict) else {}
    eintraege = daten.get("eintraege") or []
    ergebnis: dict = {}
    for gruppe in daten.get("kennungen") or []:
        if not isinstance(gruppe, dict):
            continue
        kennung = _text(gruppe.get("kennung"))
        if not kennung:
            continue
        for stelle in gruppe.get("indizes") or []:
            if isinstance(stelle, bool) or not isinstance(stelle, int):
                continue
            if not 0 <= stelle < len(eintraege):
                continue
            eintrag = eintraege[stelle]
            if not isinstance(eintrag, dict):
                continue
            ergebnis[(str(eintrag.get("bild_id")), eintrag.get("index"))] = kennung
    return ergebnis


def namen_bauen(katalog=None, bestaetigung=None) -> dict:
    """``{kennung: name}`` — Bestaetigung vor Katalog; leere Namen bleiben weg."""
    namen: dict = {}
    if katalog:
        for person in _cluster.katalog_personen(katalog):
            if person.get("name"):
                namen[person["kennung"]] = person["name"]
    for kennung, name in (bestaetigung or {}).items():
        if _text(name):
            namen[str(kennung)] = _text(name)
    return namen


# ── 3. Das Register ───────────────────────────────────────────────────────

def register_zeilen_bauen(bilder, zuordnung, namen=None,
                          min_anteil: float = MIN_ANTEIL,
                          min_score: float = MIN_SCORE) -> list[dict]:
    """Je erkanntem Gesicht eine Zeile (siehe Modul-Docstring) — rein, ohne I/O."""
    namen = namen or {}
    zeilen: list[dict] = []
    for bild in bilder:
        aufnahme = aufnahme_von(bild)
        bewertet = _cluster.gesichter_bewerten(
            bild.get("gesichter"), bild.get("breite"), bild.get("hoehe"))
        for gesicht in bewertet:
            cluster = zuordnung.get((bild["bild_id"], gesicht["index"]))
            anteil = round(gesicht["anteil"], 4)
            zeilen.append({
                "bild_id": bild["bild_id"],
                "index": gesicht["index"],
                "person": namen.get(cluster, cluster) if cluster else None,
                "cluster": cluster,
                "bbox": gesicht["bbox"],
                "gesichtsanteil": anteil,
                "score": gesicht["score"],
                "zaehlt_mit": bool(anteil >= min_anteil
                                   and gesicht["score"] >= min_score),
                "aufnahme": aufnahme,
            })
    return zeilen


def register_bauen(zeilen) -> dict:
    """Das abfragbare Register aus ``bild_person``-Zeilen.

    ``{"bilder": {bild_id: {"aufnahme", "wichtig": set, "alle": set}}}``.
    ``wichtig`` = Namen der ``zaehlt_mit``-Gesichter; ein Gesicht ohne Gruppe
    (``person`` ``None``) ist je Gesicht eine eigene fremde Person.
    """
    bilder: dict = {}
    for zeile in zeilen or []:
        eintrag = bilder.setdefault(zeile["bild_id"], {
            "aufnahme": zeile.get("aufnahme"), "wichtig": set(), "alle": set()})
        name = zeile.get("person")
        if name is None:
            name = f"?{zeile.get('index')}"       # fremd, je Gesicht eigen
        eintrag["alle"].add(name)
        if zeile.get("zaehlt_mit"):
            eintrag["wichtig"].add(name)
    return {"bilder": bilder}


def _chrono(register, bild_ids) -> list[str]:
    bilder = register["bilder"]
    return sorted(bild_ids, key=lambda b: (bilder[b]["aufnahme"] is None,
                                           bilder[b]["aufnahme"] or "", b))


def bilder_mit(register, personen, modus: str = MODUS_GENAU) -> list[str]:
    """Bild-IDs (chronologisch, fehlendes Datum am Ende) zu einer Personenmenge.

    ``"genau"``: die wichtigen Personen des Bildes sind exakt ``personen``;
    ``"mindestens"``: alle genannten sind wichtig dabei, andere erlaubt.
    """
    if modus not in (MODUS_GENAU, MODUS_MINDESTENS):
        raise ValueError(f"Unbekannter Modus: {modus!r}")
    gesucht = set(personen or ())
    if not gesucht:
        return []
    treffer = []
    for bild_id, eintrag in register["bilder"].items():
        wichtig = eintrag["wichtig"]
        if (wichtig == gesucht) if modus == MODUS_GENAU else gesucht <= wichtig:
            treffer.append(bild_id)
    return _chrono(register, treffer)


# ── 4. Die Uebersicht ─────────────────────────────────────────────────────

def uebersicht_bauen(zeilen) -> dict:
    """Personen-Uebersicht + Verteilung ``personen_wichtig`` — rein."""
    register = register_bauen(zeilen)
    je_person: dict = {}
    for zeile in zeilen or []:
        person = zeile.get("person")
        if person is None:
            continue
        eintrag = je_person.setdefault(person, {
            "cluster": zeile.get("cluster"), "alle": set(), "wichtig": set()})
        eintrag["alle"].add(zeile["bild_id"])
        if zeile.get("zaehlt_mit"):
            eintrag["wichtig"].add(zeile["bild_id"])
    personen = []
    for person in sorted(je_person):
        eintrag = je_person[person]
        daten = [register["bilder"][b]["aufnahme"] for b in eintrag["alle"]
                 if register["bilder"][b]["aufnahme"]]
        begleiter: dict = {}
        for bild_id in eintrag["wichtig"]:
            for anderer in register["bilder"][bild_id]["wichtig"]:
                if anderer != person and not anderer.startswith("?"):
                    begleiter[anderer] = begleiter.get(anderer, 0) + 1
        top = sorted(begleiter.items(), key=lambda kv: (-kv[1], kv[0]))
        personen.append({
            "person": person,
            "cluster": eintrag["cluster"],
            "anzahl_bilder": len(eintrag["alle"]),
            "anzahl_bilder_wichtig": len(eintrag["wichtig"]),
            "erstes": min(daten) if daten else None,
            "letztes": max(daten) if daten else None,
            "haeufigste_begleiter": [{"person": name, "anzahl": anzahl}
                                     for name, anzahl in top[:BEGLEITER_ANZAHL]],
        })
    verteilung = dict.fromkeys(VERTEILUNG_SCHLUESSEL, 0)
    for eintrag in register["bilder"].values():
        anzahl = len(eintrag["wichtig"])
        verteilung["4+" if anzahl >= 4 else str(anzahl)] += 1
    return {"art": "personen_uebersicht",
            "anzahl_personen": len(personen),
            "anzahl_bilder": len(register["bilder"]),
            "personen_wichtig": verteilung,
            "personen": personen}


# ── 5. Kommandozeile ──────────────────────────────────────────────────────

def main(argv=None) -> int:
    """Lesen, rechnen, Zaehler zeigen; nur mit ``--schreiben`` ablegen."""
    zerleger = argparse.ArgumentParser(
        description="Personen-Register E17: je Gesicht Person, Groesse und "
                    "Gewicht (zaehlt_mit), dazu Personen-Uebersicht. Trockenlauf "
                    "ist Standard; Ausgabe nur ausserhalb des Repos; die "
                    "Konsole zeigt nur Zaehler, keine Namen.")
    zerleger.add_argument("--vektoren", dest="vektoren", action="append",
                          default=None,
                          help="Vektordatei (JSONL, wiederholbar; Dubletten je "
                               "bild_id zaehlen einmal)")
    zerleger.add_argument("--alt-kennungen", dest="alt_kennungen",
                          default=_andocken.STANDARD_ALT_KENNUNGEN,
                          help="Kennungs-Altbestand des Cluster-Laufs (darf fehlen)")
    zerleger.add_argument("--bestaetigung", dest="bestaetigung",
                          default=_andocken.STANDARD_BESTAETIGUNG,
                          help="Namen (personen_bestaetigt.json, darf fehlen)")
    zerleger.add_argument("--katalog", dest="katalog", default=None,
                          help="Personen-Katalog (JSON, optional; Namen)")
    zerleger.add_argument("--ausgabe-bild-person", dest="ausgabe_bild_person",
                          default=STANDARD_AUSGABE_BILD_PERSON)
    zerleger.add_argument("--ausgabe-uebersicht", dest="ausgabe_uebersicht",
                          default=STANDARD_AUSGABE_UEBERSICHT)
    zerleger.add_argument("--min-anteil", dest="min_anteil", type=float,
                          default=MIN_ANTEIL,
                          help=f"Mindest-Gesichtsanteil (Standard {MIN_ANTEIL})")
    zerleger.add_argument("--min-score", dest="min_score", type=float,
                          default=MIN_SCORE,
                          help=f"Mindest-Score (Standard {MIN_SCORE})")
    zerleger.add_argument("--trocken", dest="trocken", action="store_true",
                          help="nichts schreiben (Standard; hat Vorrang)")
    zerleger.add_argument("--schreiben", dest="schreiben", action="store_true",
                          help="beide Ausgabedateien atomar schreiben")
    args = zerleger.parse_args(argv)

    # Repo-Schutz zuerst, auch im Trockenlauf (Exit 2).
    pruefe_ausserhalb_repo(args.ausgabe_bild_person)
    pruefe_ausserhalb_repo(args.ausgabe_uebersicht)
    schreiben = bool(args.schreiben) and not bool(args.trocken)

    try:
        pfade = args.vektoren or list(_andocken.STANDARD_VEKTOREN)
        eingelesen = _andocken.vektoren_lesen(pfade)
        bilder, dubletten = bilder_vereinen(eingelesen["zeilen"])
        katalog = _cluster.katalog_lesen(args.katalog) if args.katalog else {}
        altbestand = _cluster.altbestand_lesen_datei(args.alt_kennungen)
        bestaetigung = _andocken.bestaetigung_lesen(args.bestaetigung)
        lauf = _cluster.lauf_rechnen(bilder, katalog=katalog,
                                     altbestand=altbestand)
        namen = namen_bauen(katalog, bestaetigung)
        zeilen = register_zeilen_bauen(bilder, zuordnung_bauen(lauf), namen,
                                       args.min_anteil, args.min_score)
        uebersicht = uebersicht_bauen(zeilen)
    except PersonenFehler as problem:
        print(f"Fehler: {problem}", file=sys.stderr)
        return 2

    zaehlt = sum(1 for z in zeilen if z["zaehlt_mit"])
    ohne_gruppe = sum(1 for z in zeilen if z["cluster"] is None)
    print("Personen-Register E17 - "
          + ("SCHREIBEN" if schreiben
             else "TROCKENLAUF (es wird nichts geschrieben)"))
    print(f"Vektordateien: {len(pfade)}   Zeilen: {len(eingelesen['zeilen'])}"
          f"   defekt: {eingelesen['defekt']}   Dubletten: {dubletten}")
    print(f"Bilder: {len(bilder)}   Gesichter: {len(zeilen)}"
          f"   zaehlt_mit: {zaehlt}   ohne Gruppe: {ohne_gruppe}")
    print(f"Personen: {uebersicht['anzahl_personen']}   "
          f"benannt: {sum(1 for p in uebersicht['personen'] if p['person'] != p['cluster'])}")
    verteilung = uebersicht["personen_wichtig"]
    print("Bilder nach wichtigen Personen: "
          + "  ".join(f"{k}: {verteilung[k]}" for k in VERTEILUNG_SCHLUESSEL))
    if not schreiben:
        print("Ohne --schreiben wurde NICHTS geschrieben.")
        return 0
    _andocken.schreiben(args.ausgabe_bild_person, zeilen)
    _andocken.schreiben(args.ausgabe_uebersicht, uebersicht)
    print("Geschrieben: bild_person (" + str(len(zeilen)) + " Zeilen) und "
          "Uebersicht.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
