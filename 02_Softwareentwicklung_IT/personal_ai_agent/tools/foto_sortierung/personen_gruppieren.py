"""Personen gruppieren ueber ALLE Gesichter (Foto-Gedaechtnis, Schritt 1, 30.09.2026).

Wozu:
  Die Gesichtsvektoren liegen fuer alle Bilder vor (Aufgabe 1 + Aufgabe 3,
  dazu Video-Standbilder). ``personen_cluster.py`` gruppiert mit
  Complete-Linkage ueber eine volle n x n-Matrix (``vollstaendig_clustern``) —
  bei rund 30.000 Gesichtern waeren das etwa 7 GB je Matrix und etwa n^3
  Rechenschritte. Dieses Werkzeug gruppiert deshalb ueber **Mittelpunkte**:
  jedes Gesicht wird mit den Mittelpunkten der bisherigen Gruppen verglichen,
  nicht mit allen anderen Gesichtern. Speicher: O(n x 128), keine n x n-Matrix.

Was es von ``personen_cluster`` uebernimmt (unveraendert, per Import):
  Zeilenpruefung (``zeile_pruefen``), die Mengen-Regel (``bild_entscheidung`` —
  Menschenmengen ohne bekannte Person werden nicht gruppiert), die
  Gesichtsbewertung (``gesichter_bewerten``), die Schwellen (``CLUSTER_SCHWELLE``,
  ``ALT_SCHWELLE``, ``CLUSTER_MIN_NACHBAR``), das Kennungsmuster ``Person_%03d``,
  den Repo-Schutz und das Schreiben des Kennungs-Altbestands.

Das Verfahren (``gruppieren``, rein, nur numpy):
  1. **Anlegen:** Gesichter nach Qualitaet (Flaechenanteil x Score) absteigend;
     jedes Gesicht geht an die aehnlichste Gruppe, deren Mittelpunkt es mit
     Cosinus >= ``zuordnung`` trifft — aber **nie** an eine Gruppe, die schon
     ein Gesicht **desselben Bildes** enthaelt (cannot-link: zwei Gesichter auf
     einem Foto sind zwei Menschen). Sonst beginnt es eine neue Gruppe.
  2. **Verfeinern** (``runden`` Mal): alle Gesichter gegen die Mittelpunkte neu
     zuordnen, je Bild ohne Doppelung; Mittelpunkte neu rechnen.
  3. **Verschmelzen:** Gruppen, deren Mittelpunkte Cosinus >= ``verschmelzen``
     haben, werden zusammengelegt — ausser sie teilen sich ein Bild, der Nutzer
     hat sie als verschieden markiert oder sie tragen verschiedene bestaetigte
     Namen. Gleich markierte Gruppen werden zusammengelegt.
  4. **Rauschen:** Gruppen unter ``min_groesse`` Gesichtern bekommen keine Kennung.
  5. **Zwillings-/Doppel-Kandidaten:** Paare verschiedener Gruppen mit
     Mittelpunkt-Cosinus >= ``zwilling`` — aehnlich, aber getrennt geblieben.
     Teilen sie sich Bilder, sind es sicher zwei Menschen (Zwillinge,
     Geschwister); sonst kann es auch dieselbe Person sein. Beides entscheidet
     der Nutzer im Quiz — nie das Werkzeug.

Ausgaben (nur mit ``--schreiben``, nur ausserhalb des Repos, atomar):
  * ``gesicht_zuordnung.jsonl`` — je Gesicht ``bild_id``, ``index``,
    ``kennung`` (``null`` = Rauschen), ``bbox``, ``breite``, ``hoehe``,
    ``anteil``, ``score``, ``aufnahme``, ``video_id``, ``zeit_s``.
    **Ohne Vektoren** — darf ans Handy.
  * ``personen_beispiele.json`` — je Gruppe Groesse, Bilder, Zeitraum,
    bestaetigter Name (falls vorhanden), Zwillings-Kandidaten und bis zu 8
    Beispiel-Gesichter (nur Fotos, beste Qualitaet, ueber die Jahre gestreut)
    fuer das Quiz. **Ohne Vektoren** — darf ans Handy.
  * ``kennungen.json`` — Mittelpunkte je Kennung (stabile Kennungen beim
    naechsten Lauf). **Biometrie — bleibt am PC.**

Bericht: nur Zaehlungen (Dateien, Zeilen, Bilder, Gesichter, Gruppen, Groessen,
Rauschen, Kandidaten-Paare) — nie Namen, nie Vektoren, nie Dateinamen von Fotos.

Aufruf::

    .venv/Scripts/python.exe ../tools/foto_sortierung/personen_gruppieren.py            # Trockenlauf
    .venv/Scripts/python.exe ../tools/foto_sortierung/personen_gruppieren.py --schreiben

Nachtragen (``--nachtragen``, 06.10.2026):
  Neue Gesichter an die **bestehenden** Gruppen haengen, ohne neu zu rechnen.
  Anlass: die Fotobuch-Fotos fehlten in der Gesichtererkennung, und ein voller
  Neu-Lauf bringt die schon benannten Gruppen durcheinander (gemessen: eine
  Gruppe behielt nur 22 % ihrer Gesichter, 27 Gesichter wanderten zu einer
  anderen benannten Person). Deshalb: alte Zuordnungszeilen 1:1 uebernehmen,
  alte Mittelpunkte **nicht** verschieben; jedes neue Gesicht dockt an den
  aehnlichsten alten Mittelpunkt (Cosinus >= ``ZUORDNUNG_AEHNLICH``, nie zwei
  Gesichter desselben Bildes in dieselbe Gruppe, Nutzer-Ausschluesse beachtet).
  Was nicht andockt, gruppiert sich untereinander und bekommt **neue** Kennungen
  hinter der hoechsten Nummer. Vor dem Schreiben werden die drei Dateien als
  ``*.vorher`` gesichert (Rueckweg); ein zweiter Lauf ist idempotent.
  Seit 13.10.2026 nennt der Lauf ausserdem, welche **bekannten Vektordateien
  vorliegen, aber nicht Teil dieses Laufs** waren (``fehlende_vektoren()``) —
  ein Nachtrag faehrt immer nur die genannten Dateien, eine vorliegende Datei
  ohne Lauf erreicht den Personenkatalog sonst still (gemessen: 7.307 Gesichter
  der Upload-Videos lagen vor und waren nie angedockt).

  Seit 14.10.2026 gilt ``--min-score`` **auch beim Nachtragen**: die Schwelle
  entscheidet, welche Gesichter ueberhaupt gelesen werden. Vorher wurde der
  Schalter auf diesem Weg still ignoriert (gemessen: ein Nachtrag ueber
  ``personen_vektoren_n0929_voll.jsonl`` meldete mit und ohne ``--min-score 0.8``
  dieselben 4.205 Gesichter — das sind die Funde unter 0,8, die der volle Lauf
  vom 08.10. bewusst draussen liess). Die Voreinstellung bleibt 0,6.

    .venv/Scripts/python.exe ../tools/foto_sortierung/personen_gruppieren.py ^
        --nachtragen %USERPROFILE%/foto_sortierung/personen_vektoren_fotobuch.jsonl
    # Schreiben erst nach dem OK auf die Trockenlauf-Zahlen: zusaetzlich --schreiben

Gruppierung v2 (``--verfahren v2``, 15.10.2026; Standard bleibt v1):
  Sauberer Kern, Lebensabschnitte, Andocken (``lauf_rechnen_v2``,
  ``gruppieren_v2``, Phasen in ``personen_phasen.py``):

  * Nur **saubere** Gesichter (score >= 0,90 UND Ausschnittbreite >= 64 px, die
    Grenzen stehen in ``mittelpunkt_rauschen_messen.py``) bilden Gruppen.
  * Jede Gruppe wird durch **Phasen-Mittelpunkte** (Lebensabschnitte nach
    Aufnahmejahr) beschrieben statt durch einen einzigen Mittelpunkt; das
    Verfeinern und das Verschmelzen vergleichen Phase gegen Phase.
  * **Vorbilder:** jede bestaetigt benannte Kennung bekommt eine eigene
    Startgruppe aus ihren festen Zuordnungen und den Gesichtern, die ihr in der
    bestehenden ``gesicht_zuordnung.jsonl`` zugeordnet waren (ohne
    ausgeschlossene). Der Name allein verschmilzt keine Kennungen; nur ``gleich``
    vereint (dieselbe Funktion ``_verschmelzen`` wie v1). Unbenannte Gruppen, die
    einer benannten aehneln, werden nur GEZAEHLT, nie uebernommen.
  * **Andocken:** alle uebrigen Gesichter (unsichere, grobe, aus kleinen Gruppen
    gefallene) docken an die beste Gruppe an - nur mit Schwelle UND Vorsprung
    vor dem besten anderen Namen, nie an eine Gruppe mit demselben Bild, nie an
    eine ausgeschlossene Kennung. Gesichter allein gruenden nie eine Gruppe.
    Nach Regel B geschuetzte und ausgeschlossene Gesichter docken nie an.
  * **Regel B (Bestandsschutz, Auflage 1 der Fassung 5.3):** JEDES Gesicht mit
    alter benannter Kennung bleibt in dieser Kennung - auch ein unsicheres, das
    der Kern nicht gruppiert. Abweichungen gibt es nur ausdruecklich gespeichert
    und getrennt gezaehlt: die **feste Einzelzuordnung** (``wechsel_genehmigt``)
    und der **Ausschluss** genau dieses Gesichts (``ausschluss_genehmigt``).
    Alle uebrigen Wechsel stehen als ``wechsel_unerlaubt`` im Bericht und
    **muessen 0 sein**; sie blockieren die Freigabe.
  * Kennungen stabil ueber ``kennungen_vergeben``; benannte Kennungen bleiben,
    ihr Altbestand-Eintrag geht auch bei leerer Gruppe nie verloren.
  * Ausgabe in derselben Form wie v1; ``personen_beispiele.json`` traegt
    zusaetzlich ``phasen: [{von, bis, anzahl}]`` (ohne Vektoren) und
    ``verfahren: "mittelpunkt_phasen"``.
  * **Schreiben (Auflage 6, fail-closed):** ``--verfahren v2 --schreiben``
    braucht eine gueltige ``--freigabe <datei.json>`` und schreibt in den
    **Kandidatenordner** (``--ausgabe-kandidat``, Standard
    ``~/foto_sortierung/kandidat_v2``) — **nie** in ``--ausgabe``. Der produktive
    Ordner ist nur mit Freigabe UND ``--produktiv`` erreichbar. Die Freigabe ist
    an den frisch gerechneten Snapshot-hash der Grundlage, die Parameter und ein
    Urteil gebunden; jede Verletzung oder eine Sperrzahl > 0 endet mit **Exit 3**,
    ohne dass eine Datei angelegt wird. ``--trocken`` hat weiter Vorrang.
  * **G0/G1 vor jedem Rechnen (Auflage 2):** ``personen_bestaetigt.json`` und
    ``personen_vorgaben.json`` sind **Pflicht** — fehlt eine, endet v2 mit
    **Exit 2**, ohne zu rechnen und ohne zu schreiben (eine fehlende Regeldatei
    ist kein leerer Bestand). Dazu wird ein **Vollstaendigkeitsnachweis** gegen
    den Geraetestand des Handys gefuehrt (`--geraetestand`, Standard
    ``~/foto_sortierung/geraetestand.json``): je Pflichtquelle muessen **sha256**
    und die **durchgezaehlten Eintraege** stimmen und der Stand zum Bestand
    passen. Jede Abweichung endet mit Exit 2; ohne vollstaendigen Nachweis
    rechnet v2 nur als **Trockenmessung** mit ``--ohne-geraetenachweis`` (ein
    Schreiben mit diesem Schalter wird mit Exit 2 abgelehnt). Ist die
    Grundwahrheit ``vorlaeufig`` oder ``veraltet`` (``gruppierung_bewerten``),
    ist ``--schreiben`` mit **Exit 3** gesperrt — auch fuer den
    Kandidatenordner; eine Trockenmessung bleibt erlaubt.
  * ``--bewerten``: gibt zusaetzlich den Vergleich der bestehenden Zuordnung
    (vorher) mit diesem Lauf (nachher) aus - ``gruppierung_bewerten.py``,
    nur Zahlen, schreibt nichts.
  * Die Schwellen in ``personen_phasen.py`` sind Startwerte und werden erst
    nach dem Messlauf (G4) bestaetigt oder geaendert.

    .venv/Scripts/python.exe ../tools/foto_sortierung/personen_gruppieren.py ^
        --verfahren v2 --bewerten            # Trockenlauf: schreibt nichts
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib.util
import json
import os
import re
import shutil
import time

import numpy as np

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
_phasen = _nachbar("personen_phasen")

PersonenFehler = _cluster.PersonenFehler
pruefe_ausserhalb_repo = _cluster.pruefe_ausserhalb_repo

STANDARD_BASIS = os.path.join(os.path.expanduser("~"), "foto_sortierung")
STANDARD_VEKTOREN = [
    os.path.join(STANDARD_BASIS, "personen_vektoren_n0929_voll.jsonl"),
    os.path.join(STANDARD_BASIS, "personen_vektoren_n0929_bildervideos.jsonl"),
    os.path.join(STANDARD_BASIS, "video_vektoren_bildervideos.jsonl"),
]
# Alle bekannten Gesichts-Vektordateien im Standardordner (ohne Probe- und
# Altdateien): Grundlage fuer ``fehlende_vektoren()`` — den Hinweis beim
# Nachtragen. ``STANDARD_VEKTOREN`` oben ist die Liste des VOLLEN Laufs, nicht
# die Liste dessen, was angedockt ist.
STANDARD_VEKTOREN_KATALOG = (
    "personen_vektoren_n0929_voll.jsonl",
    "personen_vektoren_n0929_bildervideos.jsonl",
    "personen_vektoren_papa.jsonl",
    "personen_vektoren_gedreht_neu.jsonl",
    "personen_vektoren_fotobuch.jsonl",
    "video_vektoren_bildervideos.jsonl",
    "video_vektoren_upload.jsonl",
)
STANDARD_AUSGABE = os.path.join(STANDARD_BASIS, "personen_gruppen")
# Kandidatenordner von v2 (Auflage 1 der Plan-Fassung 5.3): v2 schreibt NIE in
# ``--ausgabe``. Der produktive Ordner ist nur mit gueltiger Freigabe (Auflage 6)
# UND dem zusaetzlichen Schalter ``--produktiv`` erreichbar.
STANDARD_KANDIDAT = os.path.join(STANDARD_BASIS, "kandidat_v2")
STANDARD_BESTAETIGT = os.path.join(STANDARD_BASIS, "personen_bestaetigt.json")
STANDARD_VORGABEN = os.path.join(STANDARD_BASIS, "personen_vorgaben.json")
# Der Geraetestand (G0, Auflage 2): das Handy schreibt ihn zu seinen
# Pflichtquellen (``termux/rueckweg-bereitstellen.sh``), das PC-Werkzeug holt
# ihn per Kabel (``tools/handy/rueckweg_holen.py``) und prueft ihn hier.
STANDARD_GERAETESTAND = os.path.join(STANDARD_BASIS, "geraetestand.json")

# G0 (Auflage 2): Diese zwei Dateien sind PFLICHT. Fehlt eine, wird bei
# ``--verfahren v2`` nicht gerechnet und nicht geschrieben — eine fehlende
# Regeldatei ist kein "leerer Bestand", sondern eine unbekannte Grundlage.
PFLICHTQUELLEN = ("personen_bestaetigt.json", "personen_vorgaben.json")

DATEI_ZUORDNUNG = "gesicht_zuordnung.jsonl"
DATEI_BEISPIELE = "personen_beispiele.json"
DATEI_KENNUNGEN = _cluster.KENNUNGEN_DATEI          # "kennungen.json"

# Cosinus-Aehnlichkeit Gesicht -> Gruppenmittelpunkt. Abgeleitet aus der
# bestehenden Cluster-Grenze (Distanz 0,45 = Aehnlichkeit 0,55), damit beide
# Werkzeuge dieselbe Strenge haben.
ZUORDNUNG_AEHNLICH = 1.0 - _cluster.CLUSTER_SCHWELLE
# Mittelpunkt <-> Mittelpunkt: ab hier ist es dieselbe Person (Mittelpunkte sind
# rauschaermer als Einzelgesichter, deshalb etwas strenger als die Zuordnung).
VERSCHMELZ_AEHNLICH = 0.60
# Aehnlich, aber getrennt geblieben -> Kandidat fuer "gleiche Person?" oder
# "Zwillinge/Geschwister" im Quiz.
ZWILLING_AEHNLICH = 0.45
MIN_GROESSE = _cluster.CLUSTER_MIN_NACHBAR
VERFEINERN_RUNDEN = 2
BEISPIELE_JE_GRUPPE = 8
ZWILLING_KANDIDATEN_JE_GRUPPE = 3
BLOCK = 1024                                        # Gesichter je Rechenblock


# ── Lesen ────────────────────────────────────────────────────────────────

def _json_lesen(pfad, standard, pflicht=False, was="Datei"):
    """JSON lesen — fehlende Datei = ``standard``, kaputte Datei = Fehler.

    ``pflicht=True`` (G0, Auflage 2): eine **fehlende** Datei ist dann kein
    leerer Bestand, sondern ein ``PersonenFehler``. Nur der Name der Datei steht
    im Text, nie ein Pfad.
    """
    if not pfad or not os.path.isfile(pfad):
        if pflicht:
            raise PersonenFehler(f"Pflichtquelle fehlt: {was}")
        return standard
    try:
        with open(pfad, encoding="utf-8") as datei:
            return json.load(datei)
    except (OSError, ValueError) as problem:
        raise PersonenFehler(
            f"Datei nicht lesbar ({problem.__class__.__name__}): {pfad}") from None


def bestaetigt_lesen(pfad, pflicht=False) -> dict:
    """``{"bestaetigt": {"Person_001": "Name"}}`` -> ``{kennung: name}``.

    ``pflicht=True`` (G0): fehlt die Datei, kommt ein ``PersonenFehler``.
    """
    daten = _json_lesen(pfad, {}, pflicht, PFLICHTQUELLEN[0])
    roh = daten.get("bestaetigt") if isinstance(daten, dict) else None
    if not isinstance(roh, dict):
        return {}
    return {str(k): str(v).strip() for k, v in roh.items()
            if isinstance(v, str) and v.strip()}


def _name_normalisieren(name):
    """Wie das Quiz: Steuerzeichen entfernen, Leerraum falten, leer/zu lang verwerfen."""
    if not isinstance(name, str):
        return None
    sauber = re.sub(r"[\x00-\x1f\x7f]", "", name)
    sauber = re.sub(r"\s+", " ", sauber).strip()
    return sauber if sauber and len(sauber) <= 60 else None


def vorgaben_lesen(pfad, pflicht=False) -> dict:
    """Gleich/Verschieden, Ausschluesse und Quiz-Einzelzuordnungen lesen.

    ``zugeordnet`` ist nach ``(bild_id, index)`` indiziert. Ein gueltiger
    spaeterer Quiz-Eintrag gewinnt; ungueltige Eintraege ueberschreiben keinen
    frueheren gueltigen Zielnamen. ``kennung`` bleibt dabei Herkunft.
    ``pflicht=True`` (G0, Auflage 2): fehlt die Datei, kommt ein
    ``PersonenFehler`` statt eines leeren Bestands.
    """
    daten = _json_lesen(pfad, {}, pflicht, PFLICHTQUELLEN[1])
    ergebnis = {"gleich": set(), "verschieden": set(), "ausgeschlossen": set(),
                "zugeordnet": {}}
    if not isinstance(daten, dict):
        return ergebnis
    for e in daten.get("ausgeschlossen") or []:
        if (isinstance(e, dict) and isinstance(e.get("kennung"), str) and e["kennung"]
                and str(e.get("bild_id") or "").isdigit()):
            try:
                ergebnis["ausgeschlossen"].add((e["kennung"], str(e["bild_id"]), int(e.get("index") or 0)))
            except (TypeError, ValueError):
                continue
    for e in daten.get("zugeordnet") or []:
        if not isinstance(e, dict):
            continue
        bild_id, index = e.get("bild_id"), e.get("index")
        quelle = e.get("kennung")
        name = _name_normalisieren(e.get("name"))
        if (not isinstance(bild_id, str) or not bild_id.isdigit()
                or type(index) is not int or index < 0
                or not isinstance(quelle, str) or not quelle.strip() or name is None):
            continue
        ergebnis["zugeordnet"][(bild_id, index)] = {
            "name": name, "kennung": quelle.strip()}
    for art in ("gleich", "verschieden"):
        for paar in daten.get(art) or []:
            if (isinstance(paar, (list, tuple)) and len(paar) == 2
                    and all(isinstance(x, str) and x for x in paar)
                    and paar[0] != paar[1]):
                ergebnis[art].add(tuple(sorted(paar)))
    return ergebnis


def _einzelzuordnungen_auflosen(vorgaben, bestaetigt) -> dict:
    """Gespeicherte Zielnamen auf bestaetigte Kennungen aufloesen.

    ``kennung`` im Quiz-Eintrag bleibt Herkunft; nur ``name`` bestimmt das Ziel.
    Bei mehreren gleichnamigen Kennungen gewinnt die bisherige Herkunft, wenn
    sie bereits dieselbe bestaetigte Person ist, sonst die kleinste Kennung.
    """
    namen_je_faltung: dict[str, list[tuple[str, str]]] = {}
    for kennung, rohname in dict(bestaetigt or {}).items():
        name = _name_normalisieren(rohname)
        if name:
            namen_je_faltung.setdefault(name.casefold(), []).append((str(kennung), name))

    erg: dict[tuple[str, int], dict] = {}
    zugeordnet = (vorgaben or {}).get("zugeordnet") or {}
    ausgeschlossen = (vorgaben or {}).get("ausgeschlossen") or set()
    for schluessel, eintrag in zugeordnet.items():
        if (not isinstance(schluessel, tuple) or len(schluessel) != 2
                or not isinstance(schluessel[0], str) or type(schluessel[1]) is not int
                or schluessel[1] < 0 or not isinstance(eintrag, dict)):
            continue
        name = _name_normalisieren(eintrag.get("name"))
        quelle = eintrag.get("kennung")
        if name is None or not isinstance(quelle, str) or not quelle.strip():
            continue
        kandidaten = namen_je_faltung.get(name.casefold(), [])
        if not kandidaten:
            raise PersonenFehler("Eine feste Zuordnung hat kein bestaetigtes Ziel.")
        kandidaten.sort(key=lambda eintrag: eintrag[0])
        treffer = next((e for e in kandidaten if e[0] == quelle.strip()), kandidaten[0])
        zielkennung, zielname = treffer
        if (zielkennung, schluessel[0], schluessel[1]) in ausgeschlossen:
            raise PersonenFehler("Eine feste Zuordnung widerspricht einer Ausschlussregel.")
        erg[schluessel] = {"kennung": zielkennung, "name": zielname,
                           "herkunft": quelle.strip()}
    return erg


def gesichter_lesen(pfade, katalog=None, min_score=None) -> dict:
    """Alle Vektordateien lesen — nur lesend. Rueckgabe siehe unten.

    ``min_score`` (08.10.2026): Mindest-Erkennungssicherheit eines Gesichts, um
    gruppiert zu werden (Standard ``personen_cluster.MIN_SCORE`` = 0,6). Die
    Gruppen-Diagnose zeigte: Mischgruppen bestehen zu 81 % aus Funden unter 0,8,
    echte Gruppen nur zu 10 %. Funde darunter bleiben ohne Gruppe.

    Je Bild entscheidet die Mengen-Regel aus ``personen_cluster``, ob es
    gruppiert wird. Ein Bild, das schon aus einer frueheren Datei kam
    (gleiche ``bild_id``), zaehlt einmal. Kaputte Zeilen werden gezaehlt,
    nicht geraten; eine fehlende Datei ist ein Fehler (keine stillen Luecken).

    Rueckgabe ``{"gesichter": [...], "vektoren": ndarray (n, 128) float32,
    "dateien": [...], "bilder": int, "bilder_gruppiert": int, "je_grund": {},
    "ungueltig": int, "doppelt": int}``.
    """
    gesichter: list[dict] = []
    vektoren: list[list[float]] = []
    dateien: list[dict] = []
    gesehen: set[str] = set()
    je_grund: dict[str, int] = {}
    bilder = gruppiert = ungueltig_gesamt = doppelt = 0
    params = {"min_score": float(min_score)} if min_score is not None else None
    for pfad in pfade:
        if not os.path.isfile(pfad):
            raise PersonenFehler(f"Vektordatei nicht gefunden: {pfad}")
        zeilen = ungueltig = 0
        try:
            with open(pfad, encoding="utf-8") as datei:
                for roh in datei:
                    zeilen += 1
                    roh = roh.strip()
                    try:
                        daten = json.loads(roh) if roh else None
                    except ValueError:
                        daten = None
                    geprueft = _cluster.zeile_pruefen(daten)
                    if geprueft is None:
                        ungueltig += 1
                        continue
                    bild_id = geprueft["bild_id"]
                    if bild_id in gesehen:
                        doppelt += 1
                        continue
                    gesehen.add(bild_id)
                    bilder += 1
                    entscheidung = _cluster.bild_entscheidung(geprueft, katalog)
                    grund = entscheidung.get("grund") or "?"
                    je_grund[grund] = je_grund.get(grund, 0) + 1
                    if not entscheidung.get("clustern"):
                        continue
                    gruppiert += 1
                    meta = daten.get("metadaten") if isinstance(daten.get("metadaten"), dict) else {}
                    aufnahme = meta.get("aufnahme") if isinstance(meta.get("aufnahme"), str) else None
                    video_id = daten.get("video_id")
                    zeit_s = daten.get("zeit_s")
                    for g in _cluster.gesichter_bewerten(geprueft["gesichter"],
                                                         geprueft["breite"],
                                                         geprueft["hoehe"],
                                                         params=params):
                        if not g["nutzbar"]:
                            continue
                        gesichter.append({
                            "bild_id": bild_id,
                            "index": int(g["index"]),
                            "bbox": [round(float(w), 1) for w in g["bbox"]],
                            "breite": geprueft["breite"],
                            "hoehe": geprueft["hoehe"],
                            "anteil": round(float(g["anteil"]), 6),
                            "score": round(float(g["score"]), 4),
                            "aufnahme": aufnahme,
                            "video_id": str(video_id) if video_id not in (None, "") else None,
                            "zeit_s": zeit_s if _cluster._ist_zahl(zeit_s) else None,
                        })
                        vektoren.append(g["embedding"])
        except OSError as problem:
            raise PersonenFehler(
                f"Vektordatei nicht lesbar ({problem.__class__.__name__}): {pfad}") from None
        dateien.append({"pfad": pfad, "zeilen": zeilen, "ungueltig": ungueltig})
        ungueltig_gesamt += ungueltig
    matrix = (np.asarray(vektoren, dtype=np.float32) if vektoren
              else np.zeros((0, _cluster.MERKMAL_LAENGE), dtype=np.float32))
    return {"gesichter": gesichter, "vektoren": einheitsvektoren(matrix),
            "dateien": dateien, "bilder": bilder, "bilder_gruppiert": gruppiert,
            "je_grund": je_grund, "ungueltig": ungueltig_gesamt, "doppelt": doppelt}


# ── Rechnen (rein) ───────────────────────────────────────────────────────

def einheitsvektoren(matrix) -> np.ndarray:
    """Zeilen auf Laenge 1; Nullzeilen bleiben Null (zu nichts aehnlich)."""
    m = np.asarray(matrix, dtype=np.float32)
    if m.ndim != 2 or m.shape[0] == 0:
        return m.reshape(0, m.shape[-1] if m.ndim == 2 else _cluster.MERKMAL_LAENGE)
    laenge = np.linalg.norm(m, axis=1, keepdims=True)
    laenge[laenge == 0] = 1.0
    return m / laenge


def _mittelpunkte(v, label, k) -> tuple[np.ndarray, np.ndarray]:
    """Summen -> normierte Mittelpunkte und Gruppengroessen fuer Labels 0..k-1."""
    summen = np.zeros((k, v.shape[1]), dtype=np.float64)
    gueltig = label >= 0
    np.add.at(summen, label[gueltig], v[gueltig])
    groessen = np.bincount(label[gueltig], minlength=k)
    return einheitsvektoren(summen), groessen


def _kompakt(label) -> tuple[np.ndarray, int]:
    """Labels auf 0..k-1 ohne Luecken bringen (Reihenfolge des ersten Auftretens)."""
    neu = np.full_like(label, -1)
    zuordnung: dict[int, int] = {}
    for i, alt in enumerate(label.tolist()):
        if alt < 0:
            continue
        if alt not in zuordnung:
            zuordnung[alt] = len(zuordnung)
        neu[i] = zuordnung[alt]
    return neu, len(zuordnung)


def _anlegen(v, bild, reihenfolge, schwelle, vorab_label=None) -> np.ndarray:
    """Schritt 1: Gesichter der Reihe nach an Gruppen haengen (cannot-link je Bild).

    ``vorab_label`` (nur v2, sonst ``None`` = Verhalten wie immer): Feld ``(n,)``
    mit Gruppennummern ``0..K-1`` fuer Gesichter, die VOR der Gruendung schon zu
    einer Gruppe gehoeren (Vorbilder benannter Personen), ``-1`` fuer alle
    anderen. Jede Nummer ``0..K-1`` muss mindestens ein Gesicht haben. Die
    Vorbild-Gruppen starten mit ihrem Mittelpunkt; der Rest wird wie gewohnt
    der Reihe nach angehaengt.
    """
    n, d = v.shape
    label = np.full(n, -1, dtype=np.int64)
    summen = np.zeros((n, d), dtype=np.float64)
    mitte = np.zeros((n, d), dtype=np.float32)
    bilder_je_gruppe: list[set] = []
    k = 0
    if vorab_label is not None:
        vorab = np.asarray(vorab_label, dtype=np.int64)
        k = int(vorab.max()) + 1 if vorab.size and int(vorab.max()) >= 0 else 0
        bilder_je_gruppe = [set() for _ in range(k)]
        for i in np.nonzero(vorab >= 0)[0].tolist():
            g = int(vorab[i])
            label[i] = g
            summen[g] += v[i]
            bilder_je_gruppe[g].add(bild[i])
        for g in range(k):
            laenge = np.linalg.norm(summen[g])
            mitte[g] = summen[g] / (laenge if laenge else 1.0)
    for i in reihenfolge:
        if label[i] >= 0:                        # schon als Vorbild gesetzt
            continue
        ziel = -1
        if k:
            aehnlich = mitte[:k] @ v[i]
            kandidaten = np.nonzero(aehnlich >= schwelle)[0]
            if kandidaten.size:
                for c in kandidaten[np.argsort(-aehnlich[kandidaten], kind="stable")]:
                    if bild[i] not in bilder_je_gruppe[c]:
                        ziel = int(c)
                        break
        if ziel < 0:
            ziel = k
            k += 1
            bilder_je_gruppe.append(set())
        label[i] = ziel
        summen[ziel] += v[i]
        laenge = np.linalg.norm(summen[ziel])
        mitte[ziel] = summen[ziel] / (laenge if laenge else 1.0)
        bilder_je_gruppe[ziel].add(bild[i])
    return label


def _verfeinern(v, bild, label, schwelle, kandidaten_je_gesicht=5) -> np.ndarray:
    """Schritt 2: alle Gesichter neu zuordnen, je Bild ohne Doppelung."""
    label, k = _kompakt(label)
    if k == 0:
        return label
    mitte, _ = _mittelpunkte(v, label, k)
    n = v.shape[0]
    top = min(kandidaten_je_gesicht, k)
    beste = np.zeros((n, top), dtype=np.int64)
    werte = np.zeros((n, top), dtype=np.float32)
    for start in range(0, n, BLOCK):
        s = v[start:start + BLOCK] @ mitte.T                     # (b, k)
        if top < k:
            idx = np.argpartition(-s, top - 1, axis=1)[:, :top]
        else:
            idx = np.tile(np.arange(k), (s.shape[0], 1))
        w = np.take_along_axis(s, idx, axis=1)
        ordnung = np.argsort(-w, axis=1, kind="stable")
        beste[start:start + BLOCK] = np.take_along_axis(idx, ordnung, axis=1)
        werte[start:start + BLOCK] = np.take_along_axis(w, ordnung, axis=1)
    neu = np.full(n, -1, dtype=np.int64)
    je_bild: dict = {}
    for i, b in enumerate(bild):
        je_bild.setdefault(b, []).append(i)
    for gesichter in je_bild.values():
        paare = sorted(((float(werte[i, j]), i, int(beste[i, j]))
                        for i in gesichter for j in range(top)
                        if werte[i, j] >= schwelle),
                       key=lambda t: (-t[0], t[1], t[2]))
        belegt: set = set()
        for _, i, c in paare:
            if neu[i] >= 0 or c in belegt:
                continue
            neu[i] = c
            belegt.add(c)
        for i in gesichter:                      # nichts passte: eigene Gruppe behalten
            if neu[i] < 0 and label[i] >= 0 and label[i] not in belegt:
                neu[i] = label[i]
                belegt.add(int(label[i]))
    return _kompakt(neu)[0]


def _bilder_je_gruppe(bild, label, k) -> list[set]:
    ergebnis: list[set] = [set() for _ in range(k)]
    for b, c in zip(bild, label.tolist()):
        if c >= 0:
            ergebnis[c].add(b)
    return ergebnis


def _paare_ueber(mitte, schwelle) -> list[tuple[float, int, int]]:
    """Alle Gruppenpaare (a < b) mit Mittelpunkt-Cosinus >= schwelle — blockweise."""
    k = mitte.shape[0]
    paare: list[tuple[float, int, int]] = []
    for start in range(0, k, BLOCK):
        s = mitte[start:start + BLOCK] @ mitte.T
        zeilen, spalten = np.nonzero(s >= schwelle)
        for z, sp in zip(zeilen.tolist(), spalten.tolist()):
            a = start + z
            if a < sp:
                paare.append((float(s[z, sp]), a, sp))
    paare.sort(key=lambda t: (-t[0], t[1], t[2]))
    return paare


def _verschmelzen(label, k, bild, paare, kennung_vorab, verschieden=None, gleich=None,
                  benannt=None):
    """Schritt 3 (geteilt von v1 und v2): Gruppen per Union-Find vereinen.

    ``paare`` sind die Gruppenpaare ``(aehnlich, a, b)`` in Verschmelz-Reihenfolge
    (v1: Mittelpunkt gegen Mittelpunkt, v2: Phase gegen Phase). Vereint wird nie,
    wenn die Gruppen ein Bild teilen (cannot-link) oder ``verschieden`` auf ihre
    Kennungen zutrifft. Zuerst werden die ``gleich``-Paare vereint - die
    ausdrueckliche Entscheidung "dieselbe Person" -, danach die Aehnlichkeitspaare.
    **Dies ist der einzige Weg, auf dem ``gleich`` wirkt** (v1 und v2 rufen diese
    Funktion).

    ``benannt`` (nur v2): je Gruppe die Menge der bestaetigt benannten Kennungen.
    Mit ``benannt`` vereinen Aehnlichkeitspaare nie eine Gruppe, die eine benannte
    Kennung traegt - weder mit einer unbenannten noch mit einer anderen benannten;
    der Name allein verschmilzt keine Kennungen. Nur ``gleich`` darf das. Gruppen
    ohne Namen, die einer benannten aehnlich sind, werden gezaehlt
    (``vorschlag_wurzeln``) und NICHT uebernommen.

    Rueckgabe ``(label, info)``: ``label`` traegt je Gesicht die Wurzel-Gruppe
    (``-1`` bleibt), ``info`` enthaelt ``gleich_vereint`` (Zahl der durch ``gleich``
    vereinten Gruppen), ``vorschlag_wurzeln`` und ``benannt_je_wurzel``.
    """
    bilder = _bilder_je_gruppe(bild, label, k)
    eltern = list(range(k))

    def wurzel(x):
        while eltern[x] != x:
            eltern[x] = eltern[eltern[x]]
            x = eltern[x]
        return x

    kennungen_je_wurzel = {c: ({kennung_vorab[c]} if kennung_vorab[c] else set())
                           for c in range(k)}
    benannt_je_wurzel = {c: (set(benannt[c]) if benannt is not None else set())
                         for c in range(k)}

    def darf(a, b) -> bool:
        if bilder[a] & bilder[b]:
            return False
        if verschieden:
            for x in kennungen_je_wurzel[a]:
                for y in kennungen_je_wurzel[b]:
                    if verschieden(x, y):
                        return False
        return True

    def vereinen(a, b) -> bool:
        a, b = wurzel(a), wurzel(b)
        if a == b or not darf(a, b):
            return False
        klein, gross = (a, b) if a > b else (b, a)
        eltern[klein] = gross
        bilder[gross] |= bilder[klein]
        kennungen_je_wurzel[gross] |= kennungen_je_wurzel[klein]
        benannt_je_wurzel[gross] |= benannt_je_wurzel[klein]
        return True

    gleich_vereint = 0
    if gleich:
        nach_kennung: dict[str, int] = {}
        for c, kenn in enumerate(kennung_vorab):
            if kenn and kenn not in nach_kennung:
                nach_kennung[kenn] = c
        for a, b in sorted(gleich):
            if a in nach_kennung and b in nach_kennung:
                if vereinen(nach_kennung[a], nach_kennung[b]):
                    gleich_vereint += 1
    for _, a, b in paare:
        if benannt is not None and (benannt_je_wurzel[wurzel(a)] or benannt_je_wurzel[wurzel(b)]):
            continue                      # benannte Kennungen verschmelzen nur ueber "gleich"
        vereinen(a, b)

    vorschlag_wurzeln: set = set()
    if benannt is not None:
        for _, a, b in paare:
            ra, rb = wurzel(a), wurzel(b)
            if ra == rb:
                continue
            a_benannt, b_benannt = bool(benannt_je_wurzel[ra]), bool(benannt_je_wurzel[rb])
            if a_benannt != b_benannt and darf(ra, rb):
                vorschlag_wurzeln.add(rb if a_benannt else ra)
    neu = np.array([wurzel(int(c)) if c >= 0 else -1 for c in label], dtype=np.int64)
    return neu, {"gleich_vereint": gleich_vereint, "vorschlag_wurzeln": vorschlag_wurzeln,
                 "benannt_je_wurzel": benannt_je_wurzel}


def _aussortieren(label, k, min_groesse, behalten_immer=()):
    """Schritt 4 (geteilt): kleine Gruppen sind Rauschen; Rest nach Groesse nummerieren.

    ``behalten_immer`` sind Gruppen, die auch unter ``min_groesse`` bleiben, solange
    sie mindestens ein Gesicht haben (v2: benannte Gruppen). Rueckgabe
    ``(label, k_neu, nummer)``; ``nummer`` bildet alte auf neue Gruppennummern ab.
    """
    groessen = np.bincount(label[label >= 0], minlength=k) if k else np.zeros(0, int)
    behalten = [c for c in range(len(groessen))
                if groessen[c] >= max(1, int(min_groesse))
                or (c in behalten_immer and groessen[c] > 0)]
    behalten.sort(key=lambda c: (-int(groessen[c]), c))
    neu_nummer = {c: i for i, c in enumerate(behalten)}
    label = np.array([neu_nummer.get(int(c), -1) for c in label], dtype=np.int64)
    return label, len(behalten), neu_nummer


def gruppieren(vektoren, bild_ids, qualitaet=None,
               zuordnung: float = ZUORDNUNG_AEHNLICH,
               verschmelzen: float = VERSCHMELZ_AEHNLICH,
               min_groesse: int = MIN_GROESSE,
               runden: int = VERFEINERN_RUNDEN,
               vorab_kennung=None, verschieden=None, gleich=None) -> dict:
    """Das Gruppier-Verfahren (rein). Siehe Moduldoku, Schritte 1–4.

    ``vorab_kennung(mittelpunkte) -> list[str|None]`` ordnet Gruppen VOR dem
    Verschmelzen einer frueheren Kennung zu (fuer Nutzervorgaben); ``verschieden``
    ist eine Funktion ``(kennung_a, kennung_b) -> bool`` (nie verschmelzen),
    ``gleich`` eine Menge von Kennungs-Paaren, die verschmolzen werden.

    Rueckgabe ``{"label": ndarray (n,) mit -1 = Rauschen, "k": int}``; Labels
    sind nach Gruppengroesse absteigend nummeriert (0 = groesste Gruppe).
    """
    v = einheitsvektoren(vektoren)
    n = v.shape[0]
    if n == 0:
        return {"label": np.zeros(0, dtype=np.int64), "k": 0}
    bild = list(bild_ids)
    q = np.zeros(n) if qualitaet is None else np.asarray(qualitaet, dtype=float)
    reihenfolge = np.lexsort((np.arange(n), -q))            # beste zuerst, stabil

    label = _anlegen(v, bild, reihenfolge, zuordnung)
    for _ in range(max(0, int(runden))):
        label = _verfeinern(v, bild, label, zuordnung)

    # Schritt 3: verschmelzen (Union-Find ueber Gruppen, Bedingungen je Paar).
    label, k = _kompakt(label)
    mitte, _ = _mittelpunkte(v, label, k)
    kennung_vorab = list(vorab_kennung(mitte)) if vorab_kennung else [None] * k
    label, _info = _verschmelzen(label, k, bild, _paare_ueber(mitte, verschmelzen),
                                 kennung_vorab, verschieden, gleich)

    # Schritt 4: kleine Gruppen sind Rauschen; nach Groesse absteigend nummerieren.
    label, k_neu, _nummer = _aussortieren(label, k, min_groesse)
    return {"label": label, "k": k_neu}


def zwillings_kandidaten(vektoren, bild_ids, label, k,
                         schwelle: float = ZWILLING_AEHNLICH) -> list[dict]:
    """Schritt 5: aehnliche, aber getrennte Gruppen — mit Zahl gemeinsamer Bilder."""
    if k < 2:
        return []
    mitte, _ = _mittelpunkte(einheitsvektoren(vektoren), np.asarray(label), k)
    bilder = _bilder_je_gruppe(list(bild_ids), np.asarray(label), k)
    return [{"a": a, "b": b, "aehnlich": round(w, 3),
             "gemeinsame_bilder": len(bilder[a] & bilder[b])}
            for w, a, b in _paare_ueber(mitte, schwelle)]


def kennungen_vergeben(mitte, altbestand, schwelle: float = _cluster.ALT_SCHWELLE,
                       reserviert=None, zaehlung=None):
    """Stabile Kennungen: Gruppen (in Reihenfolge) auf frühere Mittelpunkte abbilden.

    Wie ``personen_cluster.gruppen_kennungen``, aber vektorisiert: jede fruehere
    Kennung zaehlt je Lauf einmal, die erste (= groesste) passende Gruppe
    gewinnt; neue Kennungen setzen hinter der hoechsten Nummer fort, Nummern
    werden nie wiederverwendet. Rueckgabe je Gruppe ``{kennung, neu, treffer}``.

    ``zaehlung`` (nur v2): weitere bekannte Kennungen, die nur fuer die hoechste
    Nummer zaehlen (benannte Kennungen, die nicht zum Abgleich bereitstehen) -
    neue Nummern setzen auch dahinter fort.
    """
    alt = _cluster.altbestand_lesen(altbestand)
    hoechste = _cluster._naechste_nummer(
        sorted([e["kennung"] for e in alt] + [str(k) for k in (zaehlung or ())]))
    reserviert = set(reserviert or ())
    ergebnis = []
    if alt and len(mitte):
        a = einheitsvektoren(np.asarray([e["mittelpunkt"] for e in alt], dtype=np.float32))
        s = einheitsvektoren(mitte) @ a.T
    else:
        s = None
    benutzt: set[int] = set()
    for g in range(len(mitte)):
        kennung, neu, treffer = None, True, None
        if s is not None:
            for j in np.argsort(-s[g], kind="stable").tolist():
                if j in benutzt:
                    continue
                if s[g, j] >= schwelle:
                    kennung, neu, treffer = alt[j]["kennung"], False, round(float(s[g, j]), 4)
                    benutzt.add(j)
                break
        if kennung is None:
            while True:
                hoechste += 1
                kennung = _cluster.KENNUNG_MUSTER % hoechste
                if kennung not in reserviert:
                    break
        ergebnis.append({"kennung": kennung, "neu": neu, "treffer": treffer})
    return ergebnis


def beispiele_waehlen(gesichter, anzahl: int = BEISPIELE_JE_GRUPPE) -> list[dict]:
    """Bis zu ``anzahl`` Beispiel-Gesichter: nur Fotos, je Bild eines, ueber die Jahre gestreut.

    Innerhalb eines Jahres gewinnt die beste Qualitaet (Flaechenanteil x Score);
    die Jahre werden reihum bedient (neuestes zuerst), damit das Quiz die Person
    in verschiedenen Lebensphasen zeigt.
    """
    fotos = [g for g in gesichter if not g.get("video_id")]
    je_jahr: dict[str, list[dict]] = {}
    for g in sorted(fotos, key=lambda g: (-(g["anteil"] * g["score"]), g["bild_id"], g["index"])):
        jahr = (g.get("aufnahme") or "")[:4] or "????"
        je_jahr.setdefault(jahr, []).append(g)
    jahre = sorted(je_jahr, reverse=True)
    gewaehlt: list[dict] = []
    bilder: set = set()
    while len(gewaehlt) < anzahl and any(je_jahr[j] for j in jahre):
        for jahr in jahre:
            while je_jahr[jahr]:
                g = je_jahr[jahr].pop(0)
                if g["bild_id"] not in bilder:
                    gewaehlt.append(g)
                    bilder.add(g["bild_id"])
                    break
            if len(gewaehlt) >= anzahl:
                break
    return [{k: g.get(k) for k in ("bild_id", "index", "bbox", "breite", "hoehe",
                                   "anteil", "score", "aufnahme")} for g in gewaehlt]


def lauf_rechnen(eingelesen, altbestand=None, bestaetigt=None, vorgaben=None,
                 zuordnung=ZUORDNUNG_AEHNLICH, verschmelzen=VERSCHMELZ_AEHNLICH,
                 zwilling=ZWILLING_AEHNLICH, min_groesse=MIN_GROESSE,
                 runden=VERFEINERN_RUNDEN) -> dict:
    """Ganzer Lauf ohne Schreiben: gruppieren, Kennungen, Beispiele, Bericht."""
    gesichter = eingelesen["gesichter"]
    v = eingelesen["vektoren"]
    bild_ids = [g["bild_id"] for g in gesichter]
    q = np.array([g["anteil"] * g["score"] for g in gesichter], dtype=float)
    namen = dict(bestaetigt or {})
    vorg = vorgaben or {"gleich": set(), "verschieden": set(), "ausgeschlossen": set()}
    fest = _einzelzuordnungen_auflosen(vorg, namen)
    stellen_je_schluessel: dict[tuple[str, int], list[int]] = {}
    for i, gesicht in enumerate(gesichter):
        stellen_je_schluessel.setdefault(_schluessel(gesicht), []).append(i)
    fehlend = set(fest) - set(stellen_je_schluessel)
    if fehlend:
        raise PersonenFehler(f"Feste Zuordnungen ohne Beleg: {len(fehlend)}.")
    reserviert = {eintrag["kennung"] for eintrag in fest.values()}

    def vorab(mittelpunkte):
        return [e["kennung"] if not e["neu"] else None
                for e in kennungen_vergeben(mittelpunkte, altbestand,
                                            reserviert=reserviert)] if altbestand else [None] * len(mittelpunkte)

    def verschieden(a, b):
        if tuple(sorted((a, b))) in vorg.get("verschieden", set()):
            return True
        return bool(namen.get(a) and namen.get(b) and namen[a] != namen[b])

    start = time.monotonic()
    erg = gruppieren(v, bild_ids, q, zuordnung, verschmelzen, min_groesse, runden,
                     vorab_kennung=vorab, verschieden=verschieden,
                     gleich=vorg.get("gleich", set()))
    label, k = erg["label"], erg["k"]
    mitte, _ = _mittelpunkte(v, label, k)
    kennungen = kennungen_vergeben(mitte, altbestand, reserviert=reserviert)
    auto_mitte = {kennungen[c]["kennung"]: mitte[c] for c in range(k)}
    return _lauf_abschluss(eingelesen, label, kennungen, auto_mitte, fest, namen, vorg,
                           zwilling, start)


def _lauf_abschluss(eingelesen, label, kennungen, auto_mitte, fest, namen, vorg, zwilling,
                    start, gruppen_zusatz=None, altbestand_zusatz=None, bericht_zusatz=None):
    """Der gemeinsame Schluss von v1 und v2: Kennungen auf die Gesichter legen.

    ``label`` ist je Gesicht die automatische Gruppe ``0..k-1`` (``-1`` = ohne),
    ``kennungen[c]`` die Kennung der Gruppe ``c`` (``{kennung, neu, treffer}``),
    ``auto_mitte`` der Mittelpunkt je Kennung. Feste Zuordnungen gewinnen vor der
    automatischen Gruppe, Ausschluss-Regeln nehmen ein Gesicht aus einer Gruppe.
    Danach: Zwillings-Kandidaten, Beispiele, Altbestand, Bericht.

    Nur fuer v2 gesetzt: ``gruppen_zusatz(kennung, stellen) -> dict`` (zusaetzliche
    Felder je Gruppe), ``altbestand_zusatz`` (Altbestand-Eintraege, die erhalten
    bleiben, auch wenn ihre Gruppe leer ist) und ``bericht_zusatz`` (Zahlen unter
    ``bericht["v2"]``).
    """
    gesichter = eingelesen["gesichter"]
    v = eingelesen["vektoren"]
    bild_ids = [g["bild_id"] for g in gesichter]
    automatische_ids = [e["kennung"] for e in kennungen]
    auto_info = {e["kennung"]: e for e in kennungen}

    mitglieder: dict[str, list[int]] = {}
    finale_kennung: list[str | None] = [None] * len(gesichter)
    regeln = vorg.get("ausgeschlossen") or set()
    ausgeschlossen = 0
    zielnamen: dict[str, str] = {}
    for eintrag in fest.values():
        zielnamen[eintrag["kennung"]] = eintrag["name"]
    for i, (gesicht, auto_c) in enumerate(zip(gesichter, label.tolist())):
        automatische_kennung = automatische_ids[auto_c] if auto_c >= 0 else None
        schluessel = _schluessel(gesicht)
        fest_eintrag = fest.get(schluessel)
        kennung = fest_eintrag["kennung"] if fest_eintrag else automatische_kennung
        if (not fest_eintrag and kennung
                and (kennung, schluessel[0], schluessel[1]) in regeln):
            kennung = None
            ausgeschlossen += 1
        gesicht["kennung"] = kennung
        finale_kennung[i] = kennung
        if kennung:
            mitglieder.setdefault(kennung, []).append(i)

    gruppen_ids = [kennung for kennung in automatische_ids if mitglieder.get(kennung)]
    gruppen_ids.extend(sorted(k for k in mitglieder if k not in auto_info))
    gruppenindex = {kennung: i for i, kennung in enumerate(gruppen_ids)}
    finales_label = np.full(len(gesichter), -1, dtype=np.int64)
    for i, kennung in enumerate(finale_kennung):
        if kennung:
            finales_label[i] = gruppenindex[kennung]
    paare = zwillings_kandidaten(v, bild_ids, finales_label, len(gruppen_ids), zwilling)
    kandidaten: list[list[dict]] = [[] for _ in gruppen_ids]
    for paar in paare:
        for eigen, fremd in ((paar["a"], paar["b"]), (paar["b"], paar["a"])):
            if len(kandidaten[eigen]) < ZWILLING_KANDIDATEN_JE_GRUPPE:
                kandidaten[eigen].append({
                    "kennung": gruppen_ids[fremd], "aehnlich": paar["aehnlich"],
                    "gemeinsame_bilder": paar["gemeinsame_bilder"]})

    gruppen = []
    altbestand_neu = []
    groessen = []
    for pos, kennung in enumerate(gruppen_ids):
        stellen = mitglieder[kennung]
        mitglieder_gesicht = [gesichter[i] for i in stellen]
        daten = sorted(d for d in (g.get("aufnahme") for g in mitglieder_gesicht) if d)
        auto = auto_info.get(kennung)
        name = _name_normalisieren(namen.get(kennung)) or zielnamen.get(kennung)
        gruppen.append({
            "kennung": kennung,
            "neu": bool(auto["neu"]) if auto else False,
            "name": name,
            "groesse": len(stellen),
            "bilder": len({g["bild_id"] for g in mitglieder_gesicht if not g.get("video_id")}),
            "videos": len({g["video_id"] for g in mitglieder_gesicht if g.get("video_id")}),
            "von": daten[0][:10] if daten else None,
            "bis": daten[-1][:10] if daten else None,
            "zwilling_kandidaten": kandidaten[pos],
            "beispiele": beispiele_waehlen(mitglieder_gesicht),
        })
        if gruppen_zusatz:
            gruppen[-1].update(gruppen_zusatz(kennung, stellen))
        groessen.append(len(stellen))
        if kennung in auto_mitte:
            zentrum = auto_mitte[kennung]
        else:
            zentrum = np.asarray(_mittelpunkt(v[stellen]), dtype=np.float32)
        altbestand_neu.append({"kennung": kennung,
                               "mittelpunkt": [float(x) for x in zentrum]})

    if altbestand_zusatz:
        vorhanden = {e["kennung"] for e in altbestand_neu}
        altbestand_neu.extend(e for e in altbestand_zusatz if e["kennung"] not in vorhanden)
    groessen.sort(reverse=True)
    groessen_array = np.asarray(groessen, dtype=int)
    rauschen = sum(kennung is None for kennung in finale_kennung)
    bericht = {
        "dateien": [{"datei": os.path.basename(d["pfad"]), "zeilen": d["zeilen"],
                     "ungueltig": d["ungueltig"]} for d in eingelesen["dateien"]],
        "bilder": eingelesen["bilder"], "doppelt": eingelesen["doppelt"],
        "bilder_gruppiert": eingelesen["bilder_gruppiert"],
        "je_grund": dict(sorted(eingelesen["je_grund"].items())),
        "gesichter": len(gesichter), "gruppen": len(gruppen_ids),
        "gesichter_in_gruppen": len(gesichter) - rauschen, "rauschen": rauschen,
        "groessen_top10": [int(x) for x in groessen_array[:10]],
        "gruppen_ab_50": int((groessen_array >= 50).sum()) if gruppen_ids else 0,
        "gruppen_ab_10": int((groessen_array >= 10).sum()) if gruppen_ids else 0,
        "kennungen_neu": sum(1 for k in gruppen_ids if auto_info.get(k, {}).get("neu", False)),
        "kennungen_wiederverwendet": sum(1 for k in gruppen_ids
                                          if not auto_info.get(k, {}).get("neu", False)),
        "namen_bestaetigt": sum(1 for g in gruppen if g["name"]),
        "aehnliche_paare": len(paare),
        "ausgeschlossen_nach_regel": ausgeschlossen,
        "davon_mit_gemeinsamen_bildern": sum(1 for p in paare if p["gemeinsame_bilder"]),
        "sekunden": round(time.monotonic() - start, 1),
    }
    if bericht_zusatz:
        bericht["v2"] = dict(bericht_zusatz)
    return {"gesichter": gesichter, "gruppen": gruppen, "bericht": bericht,
            "altbestand": altbestand_neu}


# ── Gruppierung v2: sauberer Kern, Lebensabschnitte, Andocken ────────────
#
# Gruppierung v2 (15.10.2026, Plan "Gruppierung v2" Fassung 4, G3). Nur ueber
# ``--verfahren v2`` erreichbar; v1 bleibt der Standard. Schritte:
#
#   1. **Vorbilder:** jede bestaetigt benannte Kennung bekommt eine eigene Gruppe
#      aus ihren festen Zuordnungen und - falls vorhanden - den Gesichtern, die
#      ihr in der bestehenden Zuordnung zugeordnet waren (ohne Gesichter, die der
#      Nutzer ausgeschlossen hat). Der Name allein verschmilzt keine Kennungen.
#   2. **Kern:** nur SAUBERE Gesichter (score und Ausschnittbreite, siehe
#      ``personen_phasen.sauber``) werden gruppiert - Anlegen wie v1 (mit den
#      Vorbildern als Start), dann ``runden`` Verfeinerungen mit dem
#      Phasenvergleich statt eines einzelnen Mittelpunkts.
#   3. **Verschmelzen** Phase gegen Phase (``personen_phasen.verschmelz_paare``),
#      ueber DIESELBE Funktion wie v1 (``_verschmelzen``): ``gleich`` vereint,
#      ``verschieden``/cannot-link trennen. Benannte Gruppen vereint nur ``gleich``.
#   4. **Andocken** aller anderen Gesichter (unsichere, grobe, aus kleinen Gruppen
#      gefallene) an die beste Gruppe - nur mit Schwelle UND Vorsprung zwischen
#      Namen. Gesichter allein gruenden nie eine Gruppe.
#   5. **Kennungen** stabil ueber ``kennungen_vergeben`` - benannte Kennungen
#      bleiben, unbenannte Gruppen finden nur unbenannte alte Kennungen.

def alte_zuordnung_lesen(pfad) -> dict:
    """Die bestehende Zuordnung als ``{(bild_id, index): kennung}`` (nur lesend).

    Fehlende oder unlesbare Datei -> leer; kaputte Zeilen und Gesichter ohne
    Kennung werden uebersprungen. Der erste Eintrag je Gesicht gilt.
    """
    ergebnis: dict = {}
    if not pfad or not os.path.isfile(pfad):
        return ergebnis
    try:
        with open(pfad, encoding="utf-8") as datei:
            for roh in datei:
                try:
                    zeile = json.loads(roh)
                except ValueError:
                    continue
                if (not isinstance(zeile, dict) or zeile.get("bild_id") is None
                        or not isinstance(zeile.get("kennung"), str) or not zeile["kennung"]):
                    continue
                ergebnis.setdefault(_schluessel(zeile), zeile["kennung"])
    except OSError:
        return {}
    return ergebnis


def _mitglieder_je_gruppe(label, k) -> list:
    """Je Gruppe ``0..k-1`` die Stellen ihrer Gesichter (ndarray, aufsteigend)."""
    if k <= 0:
        return []
    stellen = np.nonzero(label >= 0)[0]
    geordnet = stellen[np.argsort(label[stellen], kind="stable")]
    grenzen = np.cumsum(np.bincount(label[stellen], minlength=k))
    return np.split(geordnet, grenzen[:-1])


def _phasen_der_gruppen(v, jahre, label, k) -> list:
    """Die Phasen jeder Gruppe (``personen_phasen.phasen_bilden``); leere Gruppe -> ``[]``."""
    ergebnis = []
    for stellen in _mitglieder_je_gruppe(label, k):
        if len(stellen) == 0:
            ergebnis.append([])
        else:
            ergebnis.append(_phasen.phasen_bilden(v[stellen], [jahre[i] for i in stellen]))
    return ergebnis


def _verfeinern_phasen(v, bild, jahre, label, schwelle, fixiert=None,
                       kandidaten_je_gesicht=5) -> np.ndarray:
    """Schritt 2 (v2): alle Gesichter gegen die PHASEN der Gruppen neu zuordnen.

    Wie ``_verfeinern`` (je Bild ohne Doppelung, nichts passt -> eigene Gruppe
    bleibt), aber verglichen wird mit dem Phasen-Mittelpunkt, der zum Aufnahmejahr
    passt. Die Phasen werden je Runde EINMAL neu berechnet (nicht je Gesicht).
    ``fixiert`` (bool-Feld) haelt Gesichter an ihrer Gruppe (feste Zuordnungen).
    Die Gruppennummern bleiben stabil (eine Gruppe kann leer werden), damit
    Vorbild-Gruppen nachverfolgbar bleiben.
    """
    n = v.shape[0]
    k = int(label.max()) + 1 if n and int(label.max()) >= 0 else 0
    if k == 0:
        return label
    phasen = _phasen_der_gruppen(v, jahre, label, k)
    aktiv = np.asarray([g for g in range(k) if phasen[g]], dtype=np.int64)
    satz = _phasen.phasen_satz([phasen[g] for g in aktiv.tolist()])
    top = min(kandidaten_je_gesicht, satz["k"])
    idx, werte = _phasen.beste_gruppen(v, _phasen.jahre_als_zahlen(jahre), satz, top=top)
    beste = aktiv[idx]
    neu = np.full(n, -1, dtype=np.int64)
    je_bild: dict = {}
    for i, b in enumerate(bild):
        je_bild.setdefault(b, []).append(i)
    for gesichter in je_bild.values():
        belegt: set = set()
        for i in gesichter:                          # feste Zuordnungen zuerst
            if fixiert is not None and fixiert[i] and label[i] >= 0:
                neu[i] = label[i]
                belegt.add(int(label[i]))
        paare = sorted(((float(werte[i, j]), i, int(beste[i, j]))
                        for i in gesichter for j in range(top)
                        if werte[i, j] >= schwelle),
                       key=lambda t: (-t[0], t[1], t[2]))
        for _, i, c in paare:
            if neu[i] >= 0 or c in belegt:
                continue
            neu[i] = c
            belegt.add(c)
        for i in gesichter:                          # nichts passte: eigene Gruppe behalten
            if neu[i] < 0 and label[i] >= 0 and int(label[i]) not in belegt:
                neu[i] = label[i]
                belegt.add(int(label[i]))
    return neu


def gruppieren_v2(vektoren, bild_ids, qualitaet, jahre, kern, vorbilder=None, fixiert=None,
                  zuordnung: float = ZUORDNUNG_AEHNLICH,
                  verschmelzen: float = VERSCHMELZ_AEHNLICH,
                  min_groesse: int = MIN_GROESSE, runden: int = VERFEINERN_RUNDEN,
                  vorab_kennung=None, verschieden=None, gleich=None) -> dict:
    """Der Kern von v2 (rein): nur die sauberen Gesichter gruppieren.

    ``kern`` (bool, ``(n,)``) markiert die sauberen Gesichter; nur sie bilden
    Gruppen. ``jahre`` sind die Aufnahmejahre (``int``/``None``). ``vorbilder`` ist
    ``{kennung: [Stellen]}`` (benannte Kennungen, deren Gesichter vorab eine
    Gruppe bilden), ``fixiert`` die Stellen, die in ihrer Gruppe bleiben.
    ``vorab_kennung``, ``verschieden`` und ``gleich`` wie bei ``gruppieren``;
    ``vorab_kennung`` wird nur mit den Mittelpunkten der Gruppen OHNE Vorbild
    aufgerufen.

    Rueckgabe: ``label`` (``(n,)``, ``-1`` = nicht im Kern gruppiert), ``k``,
    ``benannt`` (je Gruppe die Kennung des Vorbilds oder ``None``; bei durch
    ``gleich`` vereinten benannten Gruppen die kleinste), ``phasen`` (je Gruppe)
    und ``info`` (Zahlen fuer den Bericht).
    """
    v = einheitsvektoren(vektoren)
    n = v.shape[0]
    info = {"vorbild_gruppen": 0, "vorbild_gesichter": 0, "vorbild_verloren": 0,
            "gleich_vereint": 0, "aehneln_benannten": 0, "gruppen_vor_rauschen": 0}
    leer = {"label": np.full(n, -1, dtype=np.int64), "k": 0, "benannt": [],
            "phasen": [], "info": info}
    bild = list(bild_ids)
    jahre = list(jahre)
    idx = np.nonzero(np.asarray(kern, dtype=bool))[0]
    if idx.size == 0:
        return leer
    m = int(idx.size)
    pos = {int(g): j for j, g in enumerate(idx.tolist())}
    vs = v[idx]
    bs = [bild[i] for i in idx.tolist()]
    js = [jahre[i] for i in idx.tolist()]
    q = np.zeros(m) if qualitaet is None else np.asarray(qualitaet, dtype=float)[idx]

    # 1. Vorbilder: je benannte Kennung eine Startgruppe.
    vorab = np.full(m, -1, dtype=np.int64)
    seed_kennung: list[str] = []
    for kennung in sorted(vorbilder or {}):
        gruppe = len(seed_kennung)
        belegt = 0
        for i in vorbilder[kennung]:
            j = pos.get(int(i))
            if j is not None and vorab[j] < 0:
                vorab[j] = gruppe
                belegt += 1
        if belegt:
            seed_kennung.append(kennung)
    fix = np.zeros(m, dtype=bool)
    for i in (fixiert or ()):
        j = pos.get(int(i))
        if j is not None and vorab[j] >= 0:
            fix[j] = True
    info["vorbild_gruppen"] = len(seed_kennung)
    info["vorbild_gesichter"] = int((vorab >= 0).sum())

    # 2. Anlegen und Verfeinern mit Phasenvergleich.
    reihenfolge = np.lexsort((np.arange(m), -q))             # beste zuerst, stabil
    label = _anlegen(vs, bs, reihenfolge, zuordnung,
                     vorab_label=vorab if seed_kennung else None)
    for _ in range(max(0, int(runden))):
        label = _verfeinern_phasen(vs, bs, js, label, zuordnung, fix)
    benutzt = sorted(set(label[label >= 0].tolist()))
    alt_zu_neu = {g: i for i, g in enumerate(benutzt)}
    label = np.array([alt_zu_neu.get(int(c), -1) for c in label], dtype=np.int64)
    k = len(benutzt)
    seed_gruppe = {alt_zu_neu[g]: seed_kennung[g]
                   for g in range(len(seed_kennung)) if g in alt_zu_neu}
    info["vorbild_verloren"] = len(seed_kennung) - len(seed_gruppe)
    info["gruppen_vor_rauschen"] = k

    # 3. Verschmelzen Phase gegen Phase, ueber dieselbe Funktion wie v1.
    phasen = _phasen_der_gruppen(vs, js, label, k)
    paare = _phasen.verschmelz_paare(_phasen.phasen_satz(phasen), verschmelzen)
    mitte, _ = _mittelpunkte(vs, label, k)
    kennung_vorab: list = [None] * k
    for c, kennung in seed_gruppe.items():
        kennung_vorab[c] = kennung
    andere = [c for c in range(k) if c not in seed_gruppe]
    if vorab_kennung and andere:
        for c, kennung in zip(andere, vorab_kennung(mitte[andere])):
            kennung_vorab[c] = kennung
    benannt0 = [{seed_gruppe[c]} if c in seed_gruppe else set() for c in range(k)]
    label, verschmolzen = _verschmelzen(label, k, bs, paare, kennung_vorab, verschieden,
                                        gleich, benannt=benannt0)
    info["gleich_vereint"] = verschmolzen["gleich_vereint"]

    # 4. Rauschen: kleine Gruppen fallen weg - ausser benannte.
    benannte_wurzeln = {c for c in range(k) if verschmolzen["benannt_je_wurzel"][c]}
    label, k2, nummer = _aussortieren(label, k, min_groesse, behalten_immer=benannte_wurzeln)
    benannt: list = [None] * k2
    for wurzel_, neu_nummer in nummer.items():
        kennungen = verschmolzen["benannt_je_wurzel"][wurzel_]
        if kennungen:
            benannt[neu_nummer] = min(kennungen)
    info["aehneln_benannten"] = len({nummer[w] for w in verschmolzen["vorschlag_wurzeln"]
                                     if w in nummer})
    phasen_neu = _phasen_der_gruppen(vs, js, label, k2)
    voll = np.full(n, -1, dtype=np.int64)
    voll[idx] = label
    return {"label": voll, "k": k2, "benannt": benannt, "phasen": phasen_neu, "info": info}


def _phasen_ausgabe(phasen) -> list:
    """Phasen fuer ``personen_beispiele.json``: nur ``von``/``bis``/``anzahl`` (keine Vektoren)."""
    return [{"von": von, "bis": bis, "anzahl": int(anzahl)}
            for von, bis, _mitte, anzahl in phasen]


def lauf_rechnen_v2(eingelesen, altbestand=None, bestaetigt=None, vorgaben=None,
                    alte_zuordnung=None,
                    zuordnung=ZUORDNUNG_AEHNLICH, verschmelzen=VERSCHMELZ_AEHNLICH,
                    zwilling=ZWILLING_AEHNLICH, min_groesse=MIN_GROESSE,
                    runden=VERFEINERN_RUNDEN,
                    andock_schwelle=_phasen.ANDOCK_SCHWELLE,
                    andock_abstand=_phasen.ANDOCK_ABSTAND) -> dict:
    """Ganzer Lauf v2 ohne Schreiben (Gegenstueck zu ``lauf_rechnen``).

    ``alte_zuordnung`` ist ``{(bild_id, index): kennung}`` der bestehenden
    Zuordnung (``alte_zuordnung_lesen``); daraus kommen die Vorbilder der
    benannten Kennungen. Ohne sie bilden nur die festen Zuordnungen Vorbilder.
    Rueckgabe wie ``lauf_rechnen``, zusaetzlich ``verfahren: "v2"`` und
    ``bericht["v2"]``; jede Gruppe traegt ``phasen`` (ohne Vektoren).
    """
    gesichter = eingelesen["gesichter"]
    v = eingelesen["vektoren"]
    n = len(gesichter)
    bild_ids = [g["bild_id"] for g in gesichter]
    q = np.array([g["anteil"] * g["score"] for g in gesichter], dtype=float)
    jahre = [_phasen.jahr_aus(g.get("aufnahme")) for g in gesichter]
    kern = np.array([_phasen.sauber(g) for g in gesichter], dtype=bool)
    namen = dict(bestaetigt or {})
    vorg = vorgaben or {"gleich": set(), "verschieden": set(), "ausgeschlossen": set()}
    fest = _einzelzuordnungen_auflosen(vorg, namen)
    stellen_je_schluessel: dict[tuple[str, int], list[int]] = {}
    for i, gesicht in enumerate(gesichter):
        stellen_je_schluessel.setdefault(_schluessel(gesicht), []).append(i)
    fehlend = set(fest) - set(stellen_je_schluessel)
    if fehlend:
        raise PersonenFehler(f"Feste Zuordnungen ohne Beleg: {len(fehlend)}.")
    regeln = vorg.get("ausgeschlossen") or set()

    # Regelkonflikt (Auflage 1, fail-closed): dieselbe Kennungsgruppe kann nicht
    # gleichzeitig "dieselbe Person" (gleich) und "verschiedene Personen"
    # (verschieden) sein. Nur die Zahl wird genannt - nie Namen oder Bilder.
    gleich_paare = {tuple(sorted(tuple(p))) for p in (vorg.get("gleich") or set())}
    verschieden_paare = {tuple(sorted(tuple(p))) for p in (vorg.get("verschieden") or set())}
    widerspruch = gleich_paare & verschieden_paare
    if widerspruch:
        raise PersonenFehler(f"Regelkonflikte: {len(widerspruch)} Paare sind gleich "
                             f"UND verschieden.")

    # Altbestand: benannte Kennungen bleiben unberuehrt, unbenannte Gruppen
    # finden nur UNBENANNTE alte Kennungen; Nummern werden nie wiederverwendet.
    benannte = {str(k) for k, name in namen.items() if _name_normalisieren(name)}
    alt = _cluster.altbestand_lesen(altbestand) if altbestand else []
    alt_unbenannt = [e for e in alt if e["kennung"] not in benannte]
    reserviert = ({e["kennung"] for e in alt} | benannte
                  | {e["kennung"] for e in fest.values()})

    # 1. Vorbilder aus festen Zuordnungen und der bestehenden Zuordnung.
    fest_stellen: set = set()
    vorbilder: dict[str, list[int]] = {}
    fixiert: set = set()
    for schluessel, eintrag in fest.items():
        for i in stellen_je_schluessel[schluessel]:
            fest_stellen.add(i)
            if kern[i]:
                vorbilder.setdefault(eintrag["kennung"], []).append(i)
                fixiert.add(i)
    # Regel B (Auflage 1, Plan-Fassung 5.3): JEDES Gesicht mit alter BENANNTER
    # Kennung bleibt in dieser Kennung — auch ein unsicheres/grobes, das der Kern
    # nicht gruppiert. Ausnahmen sind nur die beiden ausdruecklich gespeicherten:
    # (1) feste Einzelzuordnung (unten, sie gewinnt), (2) Ausschluss genau dieses
    # Gesichts (das Gesicht bleibt draussen, es wechselt nicht zu einer anderen
    # Person). Alles andere waere ein nicht genehmigter Wechsel -> gesperrt.
    geschuetzt: dict[int, str] = {}          # Stelle -> alte benannte Kennung (unsicher)
    ausgeschlossen_fest: set = set()         # benannte Gesichter mit Ausschluss-Regel
    for i, gesicht in enumerate(gesichter):
        if i in fest_stellen:                # Ausnahme 1 gewinnt (unten aufgeloest)
            continue
        schl = _schluessel(gesicht)
        alte = (alte_zuordnung or {}).get(schl)
        if alte not in benannte:
            continue                         # ohne benannte Herkunft greift Regel B nicht
        if (alte, schl[0], schl[1]) in regeln:
            ausgeschlossen_fest.add(i)       # Ausnahme 2: bleibt draussen
            continue
        if kern[i]:
            vorbilder.setdefault(alte, []).append(i)
            fixiert.add(i)                   # auch aus der alten Zuordnung fixiert
        else:
            geschuetzt[i] = alte             # unsicher: wird nach dem Andocken gesetzt

    def vorab(mittelpunkte):
        if not alt_unbenannt:
            return [None] * len(mittelpunkte)
        return [e["kennung"] if not e["neu"] else None
                for e in kennungen_vergeben(mittelpunkte, alt_unbenannt,
                                            reserviert=reserviert, zaehlung=reserviert)]

    def verschieden(a, b):
        if tuple(sorted((a, b))) in vorg.get("verschieden", set()):
            return True
        return bool(namen.get(a) and namen.get(b) and namen[a] != namen[b])

    start = time.monotonic()
    erg = gruppieren_v2(v, bild_ids, q, jahre, kern, vorbilder=vorbilder, fixiert=fixiert,
                        zuordnung=zuordnung, verschmelzen=verschmelzen,
                        min_groesse=min_groesse, runden=runden, vorab_kennung=vorab,
                        verschieden=verschieden, gleich=vorg.get("gleich", set()))
    label, k = erg["label"].copy(), erg["k"]
    kern_gruppiert = int((label >= 0).sum())

    # 5. Kennungen: benannte behalten ihre, unbenannte werden stabil vergeben.
    mitte, _ = _mittelpunkte(v, label, k)
    ohne_vorbild = [c for c in range(k) if not erg["benannt"][c]]
    vergeben = (kennungen_vergeben(mitte[ohne_vorbild], alt_unbenannt, reserviert=reserviert,
                                   zaehlung=reserviert)
                if ohne_vorbild else [])
    kennungen: list = [None] * k
    for c in range(k):
        if erg["benannt"][c]:
            kennungen[c] = {"kennung": erg["benannt"][c], "neu": False, "treffer": None}
    for c, eintrag in zip(ohne_vorbild, vergeben):
        kennungen[c] = eintrag
    ids = [e["kennung"] for e in kennungen]
    auto_mitte = {ids[c]: mitte[c] for c in range(k)}

    # 4. Andocken: alle Gesichter ausserhalb der Kern-Gruppen — AUSSER den nach
    # Regel B geschuetzten und den ausgeschlossenen (Ausnahme 2): sie koennen nie
    # an eine andere Person wandern.
    kandidaten = [i for i in range(n) if label[i] < 0 and i not in fest_stellen
                  and i not in geschuetzt and i not in ausgeschlossen_fest]
    zaehler = {"angedockt": 0, "keine_passende_phase": 0, "unter_schwelle": 0,
               "zu_knapp": 0, "gleiches_bild": 0}
    if kandidaten and k:
        satz = _phasen.phasen_satz(erg["phasen"])
        gruppen_bilder = [set() for _ in range(k)]
        for i in np.nonzero(label >= 0)[0].tolist():
            gruppen_bilder[int(label[i])].add(bild_ids[i])
        schluessel_je_gruppe = [("name", _name_normalisieren(namen.get(kenn)).casefold())
                                if _name_normalisieren(namen.get(kenn)) else ("kennung", kenn)
                                for kenn in ids]
        verboten = None
        if regeln:
            regel_je_gesicht: dict = {}
            for kenn, regel_bild, regel_index in regeln:
                regel_je_gesicht.setdefault((regel_bild, regel_index), set()).add(kenn)
            gruppe_je_kennung = {kenn: c for c, kenn in enumerate(ids)}
            verboten = [{gruppe_je_kennung[kenn]
                         for kenn in regel_je_gesicht.get(_schluessel(gesichter[i]), ())
                         if kenn in gruppe_je_kennung}
                        for i in kandidaten]
        andock = _phasen.andocken(
            v[kandidaten], [jahre[i] for i in kandidaten], [bild_ids[i] for i in kandidaten],
            satz, gruppen_bilder, schluessel_je_gruppe, verboten=verboten,
            schwelle=andock_schwelle, abstand=andock_abstand)
        zaehler = andock["zaehler"]
        for stelle, gruppe in zip(kandidaten, andock["gruppe"].tolist()):
            if gruppe >= 0:
                label[stelle] = gruppe

    # Regel B, zweiter Teil: die geschuetzten (unsicheren) Gesichter bekommen ihre
    # alte benannte Kennung zurueck. Gibt es die Kennung nicht als Gruppe, ist das
    # ein fail-closed-Konflikt — es wird nur die Zahl genannt.
    if geschuetzt:
        fehlende_ziele = sorted({kennung for kennung in geschuetzt.values()} - set(ids))
        if fehlende_ziele:
            raise PersonenFehler(
                f"Regel-B-Konflikte: {len(fehlende_ziele)} benannte Kennungen haben "
                f"keine Gruppe, halten aber geschuetzte Gesichter.")
        gruppe_je_kennung = {kennung: c for c, kennung in enumerate(ids)}
        for stelle, kennung in geschuetzt.items():
            label[stelle] = gruppe_je_kennung[kennung]

    def gruppen_zusatz(kennung, stellen):
        sauber_stellen = [i for i in stellen if kern[i]]
        return {"phasen": _phasen_ausgabe(_phasen.phasen_bilden(
            v[sauber_stellen], [jahre[i] for i in sauber_stellen])) if sauber_stellen else []}

    bericht_zusatz = {
        "gesichter_sauber": int(kern.sum()),
        "gesichter_unsicher": int(n - kern.sum()),
        "vorbild_gruppen": erg["info"]["vorbild_gruppen"],
        "vorbild_gesichter": erg["info"]["vorbild_gesichter"],
        "vorbild_verloren": erg["info"]["vorbild_verloren"],
        "kern_gruppen": k,
        "kern_gruppiert": kern_gruppiert,
        "kern_ohne_gruppe": int(kern.sum()) - kern_gruppiert,
        "durch_gleich_vereint": erg["info"]["gleich_vereint"],
        "aehneln_benannten": erg["info"]["aehneln_benannten"],
        "angedockt": zaehler["angedockt"],
        "nicht_angedockt": {k_: z for k_, z in zaehler.items() if k_ != "angedockt"},
        "phasen_gesamt": sum(len(p) for p in erg["phasen"]),
    }
    ergebnis = _lauf_abschluss(
        eingelesen, label, kennungen, auto_mitte, fest, namen, vorg, zwilling, start,
        gruppen_zusatz=gruppen_zusatz,
        altbestand_zusatz=[e for e in alt if e["kennung"] in benannte],
        bericht_zusatz=bericht_zusatz)
    mit_gruppe = {g["kennung"] for g in ergebnis["gruppen"]}
    ohne_gruppe = len(benannte - mit_gruppe)
    # Zaehlregel (Auflage 1, Befund R8-1): jede Aenderung der Gruppenzugehoerigkeit
    # eines benannten Gesichts wird als GENEHMIGT (feste Einzelzuordnung = Ausnahme 1
    # oder Ausschluss = Ausnahme 2) oder als UNERLAUBT gezaehlt. Nur "unerlaubt"
    # muss 0 sein (Freigabesperre (c) und Pass/Fail-Zeile 4).
    wechsel_genehmigt = 0
    wechsel_unerlaubt = 0
    ausschluss_genehmigt = 0
    for i, gesicht in enumerate(gesichter):
        schl = _schluessel(gesicht)
        alte = (alte_zuordnung or {}).get(schl)
        if alte not in benannte:
            continue
        neu = gesicht.get("kennung")
        if neu == alte:
            continue
        if schl in fest and fest[schl]["kennung"] != alte:
            wechsel_genehmigt += 1
        elif neu is None and (alte, schl[0], schl[1]) in regeln:
            ausschluss_genehmigt += 1
        else:
            wechsel_unerlaubt += 1
    ergebnis["bericht"]["v2"].update({
        "regel_b_geschuetzt": len(geschuetzt),
        "regel_b_ausgeschlossen": len(ausgeschlossen_fest),
        "wechsel_genehmigt": wechsel_genehmigt,
        "wechsel_unerlaubt": wechsel_unerlaubt,
        "ausschluss_genehmigt": ausschluss_genehmigt,
        "benannte_ohne_gruppe": ohne_gruppe,
        # Ohne Aliasmenge (Plan-Schritt 3) sind beide Zahlen gleich; die
        # aliasfaehige Fassung folgt dort.
        "leere_benannte_gruppe": ohne_gruppe,
        "regel_konflikte": 0,
    })
    ergebnis["verfahren"] = "v2"
    ergebnis["sperrzahlen"] = {
        "benannte_ohne_gruppe": ohne_gruppe,
        "leere_benannte_gruppe": ohne_gruppe,
        "wechsel_unerlaubt": wechsel_unerlaubt,
    }
    return ergebnis


def bericht_text_v2(b) -> str:
    """Die v2-Zahlen des Berichts (leer, wenn der Lauf kein v2 war). Nur Zaehlungen."""
    z = b.get("v2")
    if not z:
        return ""
    nicht = z["nicht_angedockt"]
    zeilen = [
        "Verfahren v2: sauberer Kern, Lebensabschnitte, Andocken",
        f"Gesichter sauber: {z['gesichter_sauber']}, unsicher/grob: {z['gesichter_unsicher']}",
        f"Vorbilder benannter Personen: {z['vorbild_gruppen']} Gruppen aus "
        f"{z['vorbild_gesichter']} Gesichtern (verloren gegangen: {z['vorbild_verloren']})",
        f"Kern: {z['kern_gruppen']} Gruppen mit {z['kern_gruppiert']} Gesichtern, "
        f"{z['kern_ohne_gruppe']} saubere Gesichter ohne Gruppe",
        f"Phasen gesamt: {z['phasen_gesamt']}",
        f"Durch gleich vereint: {z['durch_gleich_vereint']} Gruppen; "
        f"Gruppen ohne Namen, die einer benannten aehneln (nur Vorschlag): "
        f"{z['aehneln_benannten']}",
        f"Angedockt: {z['angedockt']}; nicht angedockt: "
        f"keine passende Phase {nicht['keine_passende_phase']}, unter Schwelle "
        f"{nicht['unter_schwelle']}, zu knapp {nicht['zu_knapp']}, gleiches Bild "
        f"{nicht['gleiches_bild']}",
        f"Benannte Kennungen ohne Gruppe (Mittelpunkt bleibt im Altbestand): "
        f"{z['benannte_ohne_gruppe']}",
        f"Regel B: {z['regel_b_geschuetzt']} unsichere Gesichter halten ihre benannte "
        f"Kennung; ausgeschlossen (bleiben draussen): {z['regel_b_ausgeschlossen']}",
        f"Wechsel benannter Gesichter: genehmigt (feste Zuordnung) {z['wechsel_genehmigt']}, "
        f"durch Ausschluss {z['ausschluss_genehmigt']}, UNERLAUBT {z['wechsel_unerlaubt']} "
        f"(muss 0 sein)",
        f"Sperrzahlen der Freigabe (alle muessen 0 sein): verlorene benannte Kennung "
        f"{z['benannte_ohne_gruppe']}, leere benannte Gruppe {z['leere_benannte_gruppe']}, "
        f"unerlaubte Wechsel {z['wechsel_unerlaubt']}",
    ]
    return "\n".join(zeilen)


# ── Freigabe: das technische Schreib-Tor von v2 (Auflage 6) ──────────────
#
# ``--verfahren v2 --schreiben`` ist nur mit einer gueltigen Freigabedatei
# moeglich — auch in den Kandidatenordner. Die Freigabe ist an den frisch
# gerechneten Snapshot-hash der Grundlage UND an die Parameter gebunden, nennt
# ein Urteil und die drei Sperrzahlen; jede Verletzung endet mit Exit 3, ohne
# dass eine Datei angelegt wird. Der produktive Ordner verlangt zusaetzlich
# ``--produktiv`` (Auflage 1).

SPERRZAHLEN = ("benannte_ohne_gruppe", "leere_benannte_gruppe", "wechsel_unerlaubt")


def parameter_stand(args) -> dict:
    """Die Parameter, an die eine Freigabe gebunden ist (nur Zahlen und Text)."""
    return {
        "verfahren": "v2",
        "zuordnung": round(float(args.zuordnung), 6),
        "verschmelzen": round(float(args.verschmelzen), 6),
        "zwilling": round(float(args.zwilling), 6),
        "min_groesse": int(args.min_groesse),
        "min_score": None if args.min_score is None else round(float(args.min_score), 6),
        "runden": int(VERFEINERN_RUNDEN),
    }


def eingabe_hash(pfade, bestaetigt_pfad, vorgaben_pfad, kennungen_pfad, zuordnung_pfad,
                 parameter) -> str:
    """sha256 ueber die Grundlage: jede Eingabedatei (Inhalt oder ``fehlt``) + Parameter.

    Deterministisch, ohne Inhalte in der Ausgabe (nur der hash). Eine fehlende
    Datei geht als ``fehlt`` ein — der hash aendert sich also, sobald sie da ist.
    """
    pruefer = hashlib.sha256()
    eintraege = [("vektor", p) for p in sorted(pfade or [])]
    eintraege += [("bestaetigt", bestaetigt_pfad), ("vorgaben", vorgaben_pfad),
                  ("kennungen", kennungen_pfad), ("zuordnung", zuordnung_pfad)]
    for beschriftung, pfad in eintraege:
        pruefer.update(f"{beschriftung}|{pfad or ''}|".encode("utf-8"))
        if pfad and os.path.isfile(pfad):
            with open(pfad, "rb") as datei:
                for stueck in iter(lambda: datei.read(1 << 20), b""):
                    pruefer.update(stueck)
        else:
            pruefer.update(b"fehlt")
        pruefer.update(b"\n")
    pruefer.update(json.dumps(parameter or {}, sort_keys=True,
                              ensure_ascii=False).encode("utf-8"))
    return pruefer.hexdigest()


# ── G0: Pflichtquellen und Vollstaendigkeitsnachweis (Auflage 2) ──────────
#
# Warum das hier steht: eine fehlende Regeldatei war bisher ein LEERER Bestand,
# und eine halb uebertragene Datei fiel niemandem auf. Beides ist jetzt
# fail-closed: fehlt eine Pflichtquelle, wird nicht gerechnet und nicht
# geschrieben; weicht der Geraetestand ab, ebenso (Exit 2).

# Toleranz beim Stand-Vergleich (Sekunden): Handy- und PC-Uhr laufen nicht
# sekundengenau gleich; erst ein DEUTLICH aelterer Geraetestand gilt als
# "unpassender Stand".
STAND_TOLERANZ = 120


def _sha256_datei(pfad) -> str:
    """Die sha256 einer Datei blockweise lesen (nur lesend); fehlt: ``""``."""
    try:
        pruefer = hashlib.sha256()
        with open(pfad, "rb") as datei:
            for stueck in iter(lambda: datei.read(1 << 20), b""):
                pruefer.update(stueck)
        return pruefer.hexdigest()
    except OSError:
        return ""


def _zaehler_bestaetigt(daten) -> dict:
    """Die durchgezaehlten Eintraege einer ``personen_bestaetigt.json``.

    Dieselben zwei Zahlen rechnet das Handy in ``geraetestand.json`` aus
    (``termux/rueckweg-bereitstellen.sh``, Abschnitt „Geraetestand"): benannte
    Kennungen (Schluessel) und Namen (nicht leere Textwerte). Es sind **nur
    Zahlen** — kein Name verlaesst diese Funktion.
    """
    roh = daten.get("bestaetigt") if isinstance(daten, dict) else None
    if not isinstance(roh, dict):
        return {"benannte_kennungen": 0, "namen": 0}
    namen = sum(1 for wert in roh.values() if isinstance(wert, str) and wert.strip())
    return {"benannte_kennungen": len(roh), "namen": namen}


def _zaehler_vorgaben(daten) -> dict:
    """Die durchgezaehlten Eintraege einer ``personen_vorgaben.json`` (nur Zahlen)."""
    ergebnis = {}
    for feld, schluessel in (("gleich", "gleich"), ("verschieden", "verschieden"),
                             ("ausgeschlossen", "ausgeschlossen"), ("fest", "zugeordnet")):
        wert = daten.get(schluessel) if isinstance(daten, dict) else None
        ergebnis[feld] = len(wert) if isinstance(wert, (list, tuple, set, dict)) else 0
    return ergebnis


def geraetestand_lesen(pfad) -> dict | None:
    """Den Geraetestand des Handys lesen (G0). Fehlt er: ``None``.

    Fehlt die Datei, gilt der Nachweis als **nicht erbracht** (kein Geraet am
    Kabel). Ist sie vorhanden, aber unlesbar oder kein Objekt, ist das ein
    ``PersonenFehler`` — ein behaupteter Nachweis darf nicht als "kein Geraet"
    durchgehen (fail-closed).
    """
    if not pfad or not os.path.isfile(pfad):
        return None
    try:
        with open(pfad, encoding="utf-8") as datei:
            daten = json.load(datei)
    except (OSError, ValueError) as problem:
        raise PersonenFehler(
            f"Geraetestand nicht lesbar ({problem.__class__.__name__}).") from None
    if not isinstance(daten, dict):
        raise PersonenFehler("Geraetestand enthaelt kein Objekt.")
    return daten


def _zeitpunkt(wert):
    """Einen ISO-Zeitstempel des Geraetestands in Sekunden lesen (sonst ``None``)."""
    text = str(wert or "").strip()
    if not text:
        return None
    if text.endswith("Z") or text.endswith("z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.datetime.fromisoformat(text).timestamp()
    except ValueError:
        return None


def entscheidungen_pruefen(bestaetigt_pfad, vorgaben_pfad, geraetestand,
                           stand_zuordnung=None) -> dict:
    """Vollstaendigkeitsnachweis der Entscheidungen (G0, Auflage 2). Nur Zahlen.

    Je Pflichtquelle wird die **sha256** und die **durchgezaehlte Menge** der
    PC-Datei gegen die Angaben des Geraetestands gehalten; dazu der Stand des
    Geraets gegen den Stand der bestehenden Zuordnung. Rueckgabe::

        {"erbracht": bool,       # Nachweis liegt vollstaendig vor UND passt
         "abweichung": bool,     # eine gemessene Abweichung (Exit 2)
         "gruende": [str, ...],  # nur Dateinamen und Zahlen
         "zeilen": [str, ...]}   # Klartextzeile fuer den Bericht

    ``erbracht=False, abweichung=False`` heisst: es liegt (noch) kein
    vollstaendiger Nachweis vor — das erlaubt nur eine Trockenmessung, nie ein
    Schreiben. ``abweichung=True`` heisst: gemessen und falsch (Exit 2).
    """
    dateien = geraetestand.get("dateien") if isinstance(geraetestand, dict) else None
    if not isinstance(dateien, dict):
        return {"erbracht": False, "abweichung": False, "gruende": [],
                "zeilen": ["Geraetenachweis nicht erbracht: es liegt kein "
                           "Geraetestand vor."]}

    gruende: list = []
    unvollstaendig: list = []
    for name, pfad, zaehler_fn in (
            (PFLICHTQUELLEN[0], bestaetigt_pfad, _zaehler_bestaetigt),
            (PFLICHTQUELLEN[1], vorgaben_pfad, _zaehler_vorgaben)):
        # Gesucht wird erst unter dem Namen, den die verglichene PC-Datei
        # traegt (so passt auch ein umbenannter Pfad), dann unter dem
        # Standardnamen des Geraets. Beides ist eindeutig — es wird nichts
        # geraten, was nicht im Geraetestand steht.
        eintrag = dateien.get(os.path.basename(str(pfad or "")))
        if not isinstance(eintrag, dict):
            eintrag = dateien.get(name)
        if not isinstance(eintrag, dict):
            unvollstaendig.append(name)
            continue
        if not pfad or not os.path.isfile(pfad):
            gruende.append(f"Grundlage fehlt: {name}")
            continue
        if str(eintrag.get("sha256") or "") != _sha256_datei(pfad):
            gruende.append(f"sha256 weicht ab ({name})")
        if isinstance(eintrag.get("bytes"), int) and os.path.getsize(pfad) != eintrag["bytes"]:
            gruende.append(f"Bytezahl weicht ab ({name})")
        soll = eintrag.get("zaehler")
        if not isinstance(soll, dict):
            unvollstaendig.append(name + " (ohne Zaehlung)")
            continue
        ist = zaehler_fn(_json_lesen(pfad, {}))
        felder = set(soll) | set(ist)
        abweichend = [f for f in sorted(felder) if soll.get(f) != ist.get(f)]
        if abweichend:
            gruende.append(f"Zahl weicht ab ({name}: {len(abweichend)} von "
                           f"{len(felder)} Feldern)")

    stand_text = geraetestand.get("stand")
    stand_geraet = _zeitpunkt(stand_text)
    if stand_text and stand_geraet is None:
        gruende.append("Geraetestand nicht lesbar (Stand)")
    elif (stand_geraet is not None and stand_zuordnung is not None
            and stand_geraet < stand_zuordnung - STAND_TOLERANZ):
        gruende.append("Geraetestand aelter als die Zuordnung")

    if gruende:
        return {"erbracht": False, "abweichung": True, "gruende": gruende,
                "zeilen": ["Geraetenachweis ABWEICHUNG (" + str(len(gruende))
                           + " Befund(e)): " + "; ".join(gruende)]}
    if unvollstaendig:
        return {"erbracht": False, "abweichung": False, "gruende": [],
                "zeilen": ["Geraetenachweis nicht erbracht: der Geraetestand "
                           f"nennt {len(unvollstaendig)} Pflichtquelle(n) nicht "
                           "oder ohne Zaehlung."]}
    return {"erbracht": True, "abweichung": False, "gruende": [],
            "zeilen": ["Geraetenachweis erbracht: sha256 und Zaehlung beider "
                       "Pflichtquellen stimmen, Stand passt."]}


def g0_pruefen(args, schreiben_an) -> dict:
    """G0 (Pflichtquellen + Nachweis) und G1 (Zustand) VOR jedem Rechnen.

    Auflage 2 der Plan-Fassung 5.3. Rueckgabe ``{"code": int|None, "bestaetigt":
    ..., "vorgaben": ...}``: ein ``code`` ungleich ``None`` ist der Exit-Code
    des Aufrufs (es wurde dann **nichts** gerechnet und **nichts** geschrieben);
    bei ``None`` sind die gelesenen Entscheidungen mit dabei. Der Text nennt nur
    Dateinamen und Zahlen.
    """
    bestaetigt = bestaetigt_lesen(args.bestaetigt, pflicht=True)
    vorgaben = vorgaben_lesen(args.vorgaben, pflicht=True)
    zuordnung_pfad = os.path.join(args.ausgabe, DATEI_ZUORDNUNG)
    stand_zuordnung = _nachbar("gruppierung_bewerten")._stand(zuordnung_pfad)

    pruefung = entscheidungen_pruefen(args.bestaetigt, args.vorgaben,
                                      geraetestand_lesen(args.geraetestand),
                                      stand_zuordnung)
    for zeile in pruefung["zeilen"]:
        print(zeile)
    if pruefung["abweichung"]:
        print("Der Geraetenachweis weicht ab — es wurde nichts gerechnet und "
              "nichts geschrieben (Exit 2).")
        return {"code": 2, "bestaetigt": bestaetigt, "vorgaben": vorgaben}
    if not pruefung["erbracht"]:
        if not args.ohne_geraetenachweis:
            print("Ohne Geraetenachweis rechnet v2 nur mit --ohne-geraetenachweis "
                  "(Trockenmessung) — es wurde nichts gerechnet und nichts "
                  "geschrieben (Exit 2).")
            return {"code": 2, "bestaetigt": bestaetigt, "vorgaben": vorgaben}
        if schreiben_an:
            print("--ohne-geraetenachweis erlaubt nur eine Trockenmessung, kein "
                  "Schreiben — es wurde nichts gerechnet und nichts geschrieben "
                  "(Exit 2).")
            return {"code": 2, "bestaetigt": bestaetigt, "vorgaben": vorgaben}
        print("Warnung: Trockenmessung ohne Geraetenachweis — es wird nichts "
              "geschrieben.")

    gb = _nachbar("gruppierung_bewerten")
    zustand = gb.grundwahrheit(bestaetigt, vorgaben, gb._stand(args.bestaetigt),
                               gb._stand(args.vorgaben), stand_zuordnung)
    if zustand["vorlaeufig"] or zustand["veraltet"]:
        lage = ("vorlaeufig" if zustand["vorlaeufig"] else "veraltet")
        zahlen = (f"Namen {zustand['namen']}, Regeln {zustand['regeln_gesamt']}")
        if schreiben_an:
            print(f"Die Grundwahrheit ist {lage} ({zahlen}) — --schreiben ist "
                  "gesperrt (Exit 3, Auflage 2). Es wurde nichts gerechnet und "
                  "nichts geschrieben.")
            return {"code": 3, "bestaetigt": bestaetigt, "vorgaben": vorgaben}
        print(f"Warnung: die Grundwahrheit ist {lage} ({zahlen}) — ein Schreiben "
              "waere gesperrt. Eine Trockenmessung ist erlaubt.")
    else:
        print(f"Grundwahrheit in Ordnung (Namen {zustand['namen']}, "
              f"Regeln {zustand['regeln_gesamt']}).")
    return {"code": None, "bestaetigt": bestaetigt, "vorgaben": vorgaben}


def freigabe_lesen(pfad) -> dict:
    """Die Freigabedatei lesen; fehlend/kaputt/kein Objekt -> ``PersonenFehler``."""
    if not pfad or not os.path.isfile(pfad):
        raise PersonenFehler("Freigabedatei nicht gefunden.")
    try:
        with open(pfad, encoding="utf-8") as datei:
            daten = json.load(datei)
    except (OSError, ValueError) as problem:
        raise PersonenFehler(f"Freigabedatei nicht lesbar ({problem.__class__.__name__}).") \
            from None
    if not isinstance(daten, dict):
        raise PersonenFehler("Freigabedatei enthaelt kein Objekt.")
    return daten


def freigabe_pruefen(freigabe, hash_ist, parameter_ist, sperrzahlen) -> str:
    """Leerer Text = Freigabe gilt; sonst der Grund. Nur Zahlen, keine Namen."""
    if str(freigabe.get("snapshot_sha256") or "") != hash_ist:
        return "die Grundlage hat sich geaendert (Snapshot-hash passt nicht)"
    if freigabe.get("parameter") != parameter_ist:
        return "die Parameter passen nicht zur Freigabe"
    if str(freigabe.get("urteil") or "").strip().lower() != "pass":
        return f"das Urteil ist nicht bestanden ({freigabe.get('urteil')!r})"
    werte = freigabe.get("werte")
    if not isinstance(werte, dict):
        return "die Freigabedatei nennt keine Werte"
    for feld in SPERRZAHLEN:
        if werte.get(feld) != 0:
            return f"die Freigabe nennt {feld} nicht als 0"
        if int(sperrzahlen.get(feld, -1)) != 0:
            return f"die Sperrzahl {feld} dieses Laufs ist nicht 0"
    return ""


# ── Schreiben ────────────────────────────────────────────────────────────

def _atomar(pfad, schreiber):
    pruefe_ausserhalb_repo(pfad)
    os.makedirs(os.path.dirname(os.path.abspath(pfad)), exist_ok=True)
    temp = pfad + ".tmp"
    with open(temp, "w", encoding="utf-8", newline="\n") as datei:
        schreiber(datei)
    os.replace(temp, pfad)
    return pfad


FELDER_ZUORDNUNG = ("bild_id", "index", "kennung", "bbox", "breite", "hoehe",
                    "anteil", "score", "aufnahme", "video_id", "zeit_s")


def schreiben(lauf, ausgabe, stand=None) -> list[str]:
    """Die drei Dateien schreiben (atomar, ausserhalb des Repos)."""
    pruefe_ausserhalb_repo(ausgabe)
    stand = stand or datetime.datetime.now().isoformat(timespec="seconds")

    def zuordnung(datei):
        for g in lauf["gesichter"]:
            datei.write(json.dumps({k: g.get(k) for k in FELDER_ZUORDNUNG},
                                   ensure_ascii=False) + "\n")

    def beispiele(datei):
        json.dump({"stand": stand,
                   "verfahren": ("mittelpunkt_phasen" if lauf.get("verfahren") == "v2"
                                 else "mittelpunkt"),
                   "gruppen": lauf["gruppen"]}, datei, ensure_ascii=False, indent=1)
        datei.write("\n")

    def kennungen(datei):
        json.dump({"stand": stand, "kennungen": lauf["altbestand"]}, datei,
                  ensure_ascii=False)
        datei.write("\n")

    return [_atomar(os.path.join(ausgabe, DATEI_ZUORDNUNG), zuordnung),
            _atomar(os.path.join(ausgabe, DATEI_BEISPIELE), beispiele),
            _atomar(os.path.join(ausgabe, DATEI_KENNUNGEN), kennungen)]


def bericht_text(b) -> str:
    zeilen = [f"Datei {d['datei']}: {d['zeilen']} Zeilen, {d['ungueltig']} ungueltig"
              for d in b["dateien"]]
    zeilen += [
        f"Bilder: {b['bilder']} (doppelt uebersprungen: {b['doppelt']}), "
        f"gruppiert: {b['bilder_gruppiert']}",
        "Je Grund: " + ", ".join(f"{k}: {v}" for k, v in b["je_grund"].items()),
        f"Gesichter: {b['gesichter']} -> in Gruppen: {b['gesichter_in_gruppen']}, "
        f"Rauschen: {b['rauschen']}",
        f"Gruppen: {b['gruppen']} (ab 50 Gesichter: {b['gruppen_ab_50']}, ab 10: "
        f"{b['gruppen_ab_10']}), groesste: {', '.join(map(str, b['groessen_top10'])) or '-'}",
        f"Kennungen neu: {b['kennungen_neu']}, wiederverwendet: "
        f"{b['kennungen_wiederverwendet']}, Namen bestaetigt: {b['namen_bestaetigt']}",
        f"Aehnliche, getrennte Gruppenpaare: {b['aehnliche_paare']} "
        f"(davon mit gemeinsamen Bildern = sicher zwei Menschen: "
        f"{b['davon_mit_gemeinsamen_bildern']})",
        f"Nach Nutzer-Regel aus einem Vorschlag genommen: {b.get('ausgeschlossen_nach_regel', 0)} Gesichter",
        f"Rechenzeit: {b['sekunden']} s",
    ]
    if b.get("v2"):
        zeilen.append(bericht_text_v2(b))
    return "\n".join(zeilen)


def bewertung_text(lauf, ausgabe, bestaetigt, vorgaben, bestaetigt_pfad, vorgaben_pfad) -> str:
    """Die Bewertung an den eigenen Entscheidungen (``gruppierung_bewerten``).

    ``vorher`` ist die bestehende Zuordnung im Ausgabeordner, ``nachher`` dieser
    Lauf (im Speicher, nichts wird geschrieben). Gibt es noch keine bestehende
    Zuordnung, wird nur dieser Lauf bewertet. Der Bericht enthaelt nur Zahlen.
    """
    gb = _nachbar("gruppierung_bewerten")
    nachher = gb.zuordnung_aus_zeilen(
        [{k: g.get(k) for k in FELDER_ZUORDNUNG} for g in lauf["gesichter"]])[0]
    alt_pfad = os.path.join(ausgabe, DATEI_ZUORDNUNG)
    stand_b, stand_v = gb._stand(bestaetigt_pfad), gb._stand(vorgaben_pfad)
    if os.path.isfile(alt_pfad):
        vorher = gb.zuordnung_lesen(alt_pfad)[0]
        return gb.vergleich_bericht(vorher, nachher, bestaetigt, vorgaben, stand_b,
                                    stand_v, gb._stand(alt_pfad))
    return gb.einzel_bericht(nachher, bestaetigt, vorgaben, stand_b, stand_v, None)


# ── Nachtragen (neue Gesichter an bestehende Gruppen haengen) ────────────
#
# Anlass (06.10.2026): die 842 Fotobuch-Fotos waren nie in der Gesichter-
# erkennung. Ein voller Neu-Lauf bringt die schon benannten Gruppen durchein-
# ander (gemessen: eine Gruppe behielt 22 % ihrer Gesichter, 27 Gesichter
# wanderten zu einer anderen benannten Person). Dieser Weg haengt nur die NEUEN
# Gesichter an; alte Zuordnung und alte Mittelpunkte bleiben unberuehrt.

FELDER_BEISPIEL = ("bild_id", "index", "bbox", "breite", "hoehe",
                   "anteil", "score", "aufnahme")


def zuordnung_zeilen_lesen(pfad) -> list[str]:
    """Die bestehende Zuordnung als ROHE Zeilen lesen — 1:1 weiterreichen."""
    if not os.path.isfile(pfad):
        raise PersonenFehler(f"Zuordnungsdatei nicht gefunden: {pfad}")
    try:
        with open(pfad, encoding="utf-8", newline="") as datei:
            return datei.read().splitlines(keepends=True)
    except OSError as problem:
        raise PersonenFehler(
            f"Zuordnungsdatei nicht lesbar ({problem.__class__.__name__}): {pfad}") from None


def beispiele_lesen(pfad) -> dict:
    """Bestehende Quiz-Beispiele lesen: ``{kennung: gruppe}`` (fehlend = leer)."""
    daten = _json_lesen(pfad, {})
    roh = daten.get("gruppen") if isinstance(daten, dict) else None
    ergebnis: dict[str, dict] = {}
    for gruppe in roh or []:
        if isinstance(gruppe, dict) and isinstance(gruppe.get("kennung"), str):
            ergebnis.setdefault(gruppe["kennung"], gruppe)
    return ergebnis


def _schluessel(gesicht) -> tuple:
    """Der Schluessel eines Gesichts: ``(bild_id, index)`` — wie in der Zuordnung."""
    try:
        index = int(gesicht.get("index") or 0)
    except (TypeError, ValueError):
        index = 0
    return (str(gesicht.get("bild_id")), index)


def _gruppe_bauen(kennung, mitglieder, name=None, neu=True, zwilling=None) -> dict:
    """Eine Gruppe im Format von ``lauf_rechnen`` (fuer Beispiele/Quiz)."""
    daten = sorted(d for d in (m.get("aufnahme") for m in mitglieder) if d)
    return {
        "kennung": kennung,
        "neu": bool(neu),
        "name": name,
        "groesse": len(mitglieder),
        "bilder": len({m["bild_id"] for m in mitglieder if not m.get("video_id")}),
        "videos": len({m["video_id"] for m in mitglieder if m.get("video_id")}),
        "von": daten[0][:10] if daten else None,
        "bis": daten[-1][:10] if daten else None,
        "zwilling_kandidaten": list(zwilling or []),
        "beispiele": beispiele_waehlen(mitglieder),
    }


def _mittelpunkt(vektoren) -> list[float]:
    """Mittelpunkt eines Haufens Gesichtsvektoren (Einheitslaenge, wie kennungen.json)."""
    m = einheitsvektoren(np.asarray(vektoren, dtype=np.float32))
    if m.shape[0] == 0:
        return []
    mitte = einheitsvektoren(m.mean(axis=0, keepdims=True).astype(np.float32))
    return [float(x) for x in mitte[0]]


def _vorher_sichern(ausgabe) -> list[str]:
    """Die drei Dateien VOR dem Schreiben als ``*.vorher`` kopieren (Rueckweg).

    Eine vorhandene Sicherung wird **nicht** ueberschrieben — sie ist der Stand
    vor dem ersten Nachtragen und bleibt als Rueckweg erhalten.
    """
    ergebnis: list[str] = []
    for name in (DATEI_ZUORDNUNG, DATEI_BEISPIELE, DATEI_KENNUNGEN):
        quelle = os.path.join(ausgabe, name)
        ziel = quelle + ".vorher"
        if os.path.isfile(quelle) and not os.path.exists(ziel):
            shutil.copy2(quelle, ziel)
            ergebnis.append(ziel)
    return ergebnis


def _stempel_sichern(ausgabe, stempel=None) -> list[str]:
    """Vor einem vollen Neugruppieren die drei Dateien als ``*.vorher_<stempel>``
    kopieren (09.10.2026). Bis dahin sicherte nur ``--nachtragen``; ein voller
    Lauf ersetzte die Gruppen ohne Rueckweg. Der Zeitstempel haelt jede Fassung
    getrennt; eine vorhandene Sicherung wird nie ueberschrieben."""
    stempel = stempel or datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    ergebnis: list[str] = []
    for name in (DATEI_ZUORDNUNG, DATEI_BEISPIELE, DATEI_KENNUNGEN):
        quelle = os.path.join(ausgabe, name)
        ziel = f"{quelle}.vorher_{stempel}"
        if os.path.isfile(quelle) and not os.path.exists(ziel):
            shutil.copy2(quelle, ziel)
            ergebnis.append(ziel)
    return ergebnis


def nachtrag_rechnen(eingelesen, alte_zeilen, alt_kennungen, beispiele_alt=None,
                     bestaetigt=None, vorgaben=None,
                     zuordnung: float = ZUORDNUNG_AEHNLICH,
                     min_groesse: int = MIN_GROESSE,
                     runden: int = VERFEINERN_RUNDEN) -> dict:
    """Neue Gesichter andocken und gespeicherte Alt-Zuordnungen korrigieren."""
    start = time.monotonic()
    gesichter = eingelesen["gesichter"]
    v = einheitsvektoren(eingelesen["vektoren"])
    namen = dict(bestaetigt or {})
    vorg = vorgaben or {}
    fest = _einzelzuordnungen_auflosen(vorg, namen)

    # Alte Rohzeilen nur lesend auswerten; unveraenderte Zeilen bleiben bytegleich.
    vorhanden: set = set()
    zeilen_daten: dict[int, tuple[tuple[str, int], dict]] = {}
    zeilen_je_schluessel: dict[tuple[str, int], list[tuple[int, dict]]] = {}
    for position, roh in enumerate(alte_zeilen):
        try:
            eintrag = json.loads(roh)
        except ValueError:
            continue
        if not isinstance(eintrag, dict) or eintrag.get("bild_id") in (None, ""):
            continue
        schluessel = _schluessel(eintrag)
        vorhanden.add(schluessel)
        zeilen_daten[position] = (schluessel, eintrag)
        zeilen_je_schluessel.setdefault(schluessel, []).append((position, eintrag))

    stellen_je_schluessel: dict[tuple[str, int], list[int]] = {}
    for i, gesicht in enumerate(gesichter):
        stellen_je_schluessel.setdefault(_schluessel(gesicht), []).append(i)
    fehlend = set(fest) - (set(zeilen_je_schluessel) | set(stellen_je_schluessel))
    if fehlend:
        raise PersonenFehler(f"Feste Zuordnungen ohne Beleg: {len(fehlend)}.")

    alt = _cluster.altbestand_lesen(alt_kennungen)
    kennungen_alt = [e["kennung"] for e in alt]
    kennungen_set = set(kennungen_alt)
    if any(e["kennung"] not in kennungen_set for e in fest.values()):
        raise PersonenFehler("Eine feste Zuordnung hat keine gueltige Zielreferenz.")
    reserviert = {e["kennung"] for e in fest.values()}
    m_alt = (einheitsvektoren(np.asarray([e["mittelpunkt"] for e in alt], dtype=np.float32))
             if alt else None)
    regeln = vorg.get("ausgeschlossen") or set()

    korrigierte_altzeilen = list(alte_zeilen)
    alte_korrekturen: dict[tuple[str, int], str] = {}
    for schluessel, fest_eintrag in fest.items():
        zielkennung = fest_eintrag["kennung"]
        alte_treffer = zeilen_je_schluessel.get(schluessel, [])
        if not alte_treffer:
            continue
        if any(str(e.get("kennung") or "") != zielkennung for _, e in alte_treffer):
            alte_korrekturen[schluessel] = zielkennung
        for position, eintrag in alte_treffer:
            if str(eintrag.get("kennung") or "") != zielkennung:
                korrigiert = dict(eintrag)
                korrigiert["kennung"] = zielkennung
                korrigierte_altzeilen[position] = json.dumps(korrigiert, ensure_ascii=False)

    # Alte Kennungsstatistik nach den ausdruecklichen Korrekturen neu zaehlen.
    groesse_alt: dict[str, int] = {}
    bilder_je_kennung: dict[str, set] = {}
    fotos_je_kennung: dict[str, set] = {}
    videos_je_kennung: dict[str, set] = {}
    daten_je_kennung: dict[str, list] = {}
    for schluessel, eintrag in zeilen_daten.values():
        kennung = alte_korrekturen.get(schluessel, str(eintrag.get("kennung") or ""))
        if not kennung:
            continue
        bild = schluessel[0]
        groesse_alt[kennung] = groesse_alt.get(kennung, 0) + 1
        bilder_je_kennung.setdefault(kennung, set()).add(bild)
        if eintrag.get("video_id") in (None, ""):
            fotos_je_kennung.setdefault(kennung, set()).add(bild)
        else:
            videos_je_kennung.setdefault(kennung, set()).add(str(eintrag["video_id"]))
        if isinstance(eintrag.get("aufnahme"), str) and eintrag["aufnahme"]:
            daten_je_kennung.setdefault(kennung, []).append(eintrag["aufnahme"])

    neue = [i for i, g in enumerate(gesichter) if _schluessel(g) not in vorhanden]
    uebersprungen = len(gesichter) - len(neue)
    ziel: dict[int, str | None] = {}
    neu_bilder: dict[str, set] = {}
    for i in sorted(neue, key=lambda i: -(gesichter[i]["anteil"] * gesichter[i]["score"])):
        bild, index = _schluessel(gesichter[i])
        fest_eintrag = fest.get((bild, index))
        treffer = fest_eintrag["kennung"] if fest_eintrag else None
        if treffer is None and m_alt is not None and m_alt.shape[0]:
            s = m_alt @ v[i]
            kandidaten = np.nonzero(s >= zuordnung)[0]
            for c in kandidaten[np.argsort(-s[kandidaten], kind="stable")].tolist():
                kennung = kennungen_alt[c]
                if bild in bilder_je_kennung.get(kennung, ()) or bild in neu_bilder.get(kennung, ()):
                    continue
                if (kennung, bild, index) in regeln:
                    continue
                treffer = kennung
                break
        ziel[i] = treffer
        if treffer:
            neu_bilder.setdefault(treffer, set()).add(bild)

    zuwachs: dict[str, list[int]] = {}
    for i, kennung in ziel.items():
        if kennung:
            zuwachs.setdefault(kennung, []).append(i)
    angedockt = sum(len(x) for x in zuwachs.values())

    rest = [i for i in neue if not ziel.get(i)]
    gruppen_neu: list[dict] = []
    kennungen_neu: list[dict] = []
    mitglieder_neu: dict[str, list[int]] = {}
    if rest:
        rq = np.array([gesichter[i]["anteil"] * gesichter[i]["score"] for i in rest])
        erg = gruppieren(v[rest], [str(gesichter[i]["bild_id"]) for i in rest], rq,
                         zuordnung, VERSCHMELZ_AEHNLICH, min_groesse, runden)
        hoechste = _cluster._naechste_nummer(sorted(kennungen_alt))
        for c in range(erg["k"]):
            stellen = [rest[j] for j in np.nonzero(erg["label"] == c)[0].tolist()]
            while True:
                hoechste += 1
                kennung = _cluster.KENNUNG_MUSTER % hoechste
                if kennung not in reserviert:
                    break
            for i in stellen:
                ziel[i] = kennung
            mitglieder_neu[kennung] = stellen
            kennungen_neu.append({"kennung": kennung,
                                  "mittelpunkt": _mittelpunkt(v[stellen])})
            gruppen_neu.append(_gruppe_bauen(kennung, [gesichter[i] for i in stellen],
                                             name=namen.get(kennung), neu=True))

    # Betroffene Herkunftsbeispiele entfernen; die Zielgruppe bekommt belegte Altgesichter.
    alt_gruppen = dict(beispiele_alt or {})
    beispiele_je_kennung: dict[str, list[dict]] = {
        kennung: list((alt_gruppen.get(kennung) or {}).get("beispiele") or [])
        for kennung in set(alt_gruppen) | set(kennungen_alt)
    }
    for schluessel, zielkennung in alte_korrekturen.items():
        alte_treffer = zeilen_je_schluessel.get(schluessel, [])
        if not alte_treffer:
            continue
        quelle = str(alte_treffer[-1][1].get("kennung") or "")
        if quelle and quelle != zielkennung:
            beispiele_je_kennung[quelle] = [
                b for b in beispiele_je_kennung.get(quelle, [])
                if _schluessel(b) != schluessel]
        gesicht_alt = alte_treffer[-1][1]
        if (isinstance(gesicht_alt.get("anteil"), (int, float))
                and isinstance(gesicht_alt.get("score"), (int, float))):
            beispiele_je_kennung.setdefault(zielkennung, []).append(gesicht_alt)

    reihenfolge = list(alt_gruppen) + [k for k in sorted(kennungen_alt) if k not in alt_gruppen]
    gruppen_alt: list[dict] = []
    for kennung in reihenfolge:
        bekannt = alt_gruppen.get(kennung) or {}
        zu_gesichter = [gesichter[i] for i in zuwachs.get(kennung, [])]
        daten = list(daten_je_kennung.get(kennung, []))
        daten += [g["aufnahme"] for g in zu_gesichter
                  if isinstance(g.get("aufnahme"), str) and g["aufnahme"]]
        daten.sort()
        beispiele = beispiele_je_kennung.get(kennung, []) + zu_gesichter
        gruppen_alt.append({
            "kennung": kennung,
            "neu": bool(bekannt.get("neu", False)),
            "name": bekannt.get("name") or namen.get(kennung),
            "groesse": groesse_alt.get(kennung, 0) + len(zu_gesichter),
            "bilder": len(fotos_je_kennung.get(kennung, set())
                          | {str(g["bild_id"]) for g in zu_gesichter if not g.get("video_id")}),
            "videos": len(videos_je_kennung.get(kennung, set())
                           | {str(g["video_id"]) for g in zu_gesichter if g.get("video_id")}),
            "von": daten[0][:10] if daten else None,
            "bis": daten[-1][:10] if daten else None,
            "zwilling_kandidaten": list(bekannt.get("zwilling_kandidaten") or []),
            "beispiele": beispiele_waehlen(beispiele),
        })

    if gruppen_neu:
        m_neu = einheitsvektoren(np.asarray([e["mittelpunkt"] for e in kennungen_neu],
                                            dtype=np.float32))
        for pos, gruppe in enumerate(gruppen_neu):
            kennung = gruppe["kennung"]
            meine = {str(gesichter[i]["bild_id"]) for i in mitglieder_neu[kennung]}
            zwillinge: list[dict] = []
            if m_alt is not None and m_alt.shape[0]:
                s = m_alt @ m_neu[pos]
                for c in np.argsort(-s, kind="stable").tolist():
                    if s[c] < ZWILLING_AEHNLICH:
                        break
                    fremd = kennungen_alt[c]
                    zwillinge.append({
                        "kennung": fremd, "aehnlich": round(float(s[c]), 3),
                        "gemeinsame_bilder": len(meine & bilder_je_kennung.get(fremd, set()))})
            for pos2, andere in enumerate(gruppen_neu):
                if pos2 == pos:
                    continue
                w = float(m_neu[pos2] @ m_neu[pos])
                if w >= ZWILLING_AEHNLICH:
                    fremde_bilder = {str(gesichter[i]["bild_id"])
                                     for i in mitglieder_neu[andere["kennung"]]}
                    zwillinge.append({"kennung": andere["kennung"], "aehnlich": round(w, 3),
                                      "gemeinsame_bilder": len(meine & fremde_bilder)})
            zwillinge.sort(key=lambda k: -k["aehnlich"])
            gruppe["zwilling_kandidaten"] = zwillinge[:ZWILLING_KANDIDATEN_JE_GRUPPE]

    korrigierte = sum(1 for schluessel, zielkennung in alte_korrekturen.items()
                      if any(str(e.get("kennung") or "") != zielkennung
                             for _, e in zeilen_je_schluessel.get(schluessel, [])))
    rauschen = sum(1 for i in neue if not ziel.get(i))
    bericht = {
        "alt_zeilen": len(alte_zeilen),
        "alt_gesichter": len(vorhanden),
        "alt_gruppen": len(kennungen_alt),
        "neue_gesichter": len(neue),
        "uebersprungen": uebersprungen,
        "angedockt": angedockt,
        "gruppen_mit_zuwachs": len(zuwachs),
        "neue_gruppen": len(gruppen_neu),
        "neue_kennungen": [e["kennung"] for e in kennungen_neu],
        "korrigierte_altgesichter": korrigierte,
        "rauschen": rauschen,
        "noop": not neue and korrigierte == 0,
        "sekunden": round(time.monotonic() - start, 1),
    }
    return {"neu": ziel, "gesichter": gesichter, "zuwachs": zuwachs,
            "korrigierte_altzeilen": korrigierte_altzeilen,
            "gruppen_alt": gruppen_alt, "gruppen_neu": gruppen_neu,
            "kennungen_neu": kennungen_neu, "alt_kennungen": list(alt_kennungen or []),
            "bericht": bericht}


def nachtrag_schreiben(lauf, ausgabe, alte_zeilen, stand=None) -> dict:
    """Zuordnung + Beispiele + Kennungen schreiben (atomar, ausserhalb des Repos).

    Die alten Zeilen kommen **wortgleich** zurueck in die Datei, dahinter die
    neuen; vorher werden die drei Dateien als ``*.vorher`` gesichert (Rueckweg).
    """
    pruefe_ausserhalb_repo(ausgabe)
    stand = stand or datetime.datetime.now().isoformat(timespec="seconds")
    sicherungen = _vorher_sichern(ausgabe)

    neu_zeilen = []
    for i in sorted(lauf["neu"]):
        g = lauf["gesichter"][i]
        eintrag = {k: g.get(k) for k in FELDER_ZUORDNUNG}
        eintrag["index"] = int(g.get("index") or 0)
        eintrag["kennung"] = lauf["neu"][i]
        neu_zeilen.append(json.dumps(eintrag, ensure_ascii=False))

    def zuordnung(datei):
        for roh in lauf.get("korrigierte_altzeilen", alte_zeilen):
            datei.write(roh if roh.endswith("\n") else roh + "\n")
        for zeile in neu_zeilen:
            datei.write(zeile + "\n")

    def beispiele(datei):
        json.dump({"stand": stand, "verfahren": "mittelpunkt-nachtrag",
                   "gruppen": lauf["gruppen_alt"] + lauf["gruppen_neu"]},
                  datei, ensure_ascii=False, indent=1)
        datei.write("\n")

    def kennungen(datei):
        json.dump({"stand": stand,
                   "kennungen": list(lauf["alt_kennungen"]) + lauf["kennungen_neu"]},
                  datei, ensure_ascii=False)
        datei.write("\n")

    geschrieben = [
        _atomar(os.path.join(ausgabe, DATEI_ZUORDNUNG), zuordnung),
        _atomar(os.path.join(ausgabe, DATEI_BEISPIELE), beispiele),
        _atomar(os.path.join(ausgabe, DATEI_KENNUNGEN), kennungen),
    ]
    return {"geschrieben": geschrieben, "sicherungen": sicherungen}


def nachtrag_bericht_text(b) -> str:
    """Bericht des Nachtragens — nur Zahlen, keine Namen, keine Pfade."""
    kennungen = b["neue_kennungen"]
    return "\n".join([
        f"Alte Zuordnung: {b['alt_zeilen']} Zeilen, {b['alt_gesichter']} Gesichter, "
        f"{b['alt_gruppen']} Kennungen (alte Mittelpunkte beibehalten)",
        f"Korrigierte alte Gesichter: {b['korrigierte_altgesichter']}",
        f"Neue Gesichter: {b['neue_gesichter']} "
        f"(schon vorhanden, uebersprungen: {b['uebersprungen']})",
        f"Angedockt an bestehende Gruppen: {b['angedockt']} Gesichter in "
        f"{b['gruppen_mit_zuwachs']} Gruppen",
        f"Neue Gruppen: {b['neue_gruppen']}"
        + (f" (Kennungen {kennungen[0]}..{kennungen[-1]})" if kennungen else ""),
        f"Nicht angedockt (Rauschen): {b['rauschen']}",
        f"Rechenzeit: {b['sekunden']} s",
    ])


def fehlende_vektoren(pfade, basis=None) -> list[str]:
    """Bekannte Vektordateien, die vorliegen, aber nicht Teil DIESES Laufs sind.

    Nur ein Hinweis, keine Rechnung. Warum es ihn gibt (gemessen 13.10.2026):
    Die Gesichter der Upload-Videos (``video_vektoren_upload.jsonl``) lagen
    vollstaendig vor, waren aber nie angedockt — 7.307 Gesichter, die den
    Personenkatalog nie erreichten, weil niemand einen Nachtrag fuer die Datei
    gefahren hat. Ein Nachtrag faehrt immer NUR die genannten Dateien; eine
    vorliegende Datei ohne Lauf bleibt still. Die Reihenfolge folgt dem Katalog.
    """
    basis = basis or STANDARD_BASIS
    dabei = {os.path.abspath(p) for p in (pfade or [])}
    fehlen = []
    for name in STANDARD_VEKTOREN_KATALOG:
        pfad = os.path.join(basis, name)
        if os.path.isfile(pfad) and os.path.abspath(pfad) not in dabei:
            fehlen.append(pfad)
    return fehlen


def _nachtragen_main(args, pfade, schreiben_an) -> int:
    """Der ``--nachtragen``-Weg: lesen, andocken, nur mit ``--schreiben`` schreiben."""
    katalog = _cluster.katalog_lesen(args.katalog) if args.katalog else {}
    kennungen_roh = _json_lesen(os.path.join(args.ausgabe, DATEI_KENNUNGEN), {})
    alt_kennungen = (kennungen_roh.get("kennungen") if isinstance(kennungen_roh, dict)
                     else kennungen_roh) or []
    print("Personen nachtragen — " + ("Schreiben ist eingeschaltet" if schreiben_an
                                      else "Trockenlauf (es wird NICHTS geschrieben)"))
    fehlen = fehlende_vektoren(pfade)
    if fehlen:
        print(f"Hinweis: {len(fehlen)} Vektordatei(en) liegen vor, waren aber nicht Teil "
              "dieses Laufs (ihre Gesichter erreichen den Personenkatalog so nicht): "
              + ", ".join(os.path.basename(p) for p in fehlen))
    alte_zeilen = zuordnung_zeilen_lesen(os.path.join(args.ausgabe, DATEI_ZUORDNUNG))
    if not alte_zeilen:
        raise PersonenFehler(
            "Die bestehende Zuordnung ist leer — ohne sie gibt es nichts zum Andocken.")
    if not alt_kennungen:
        raise PersonenFehler(
            "Keine alten Mittelpunkte (kennungen.json) — ohne sie gibt es nichts zum Andocken.")
    eingelesen = gesichter_lesen(pfade, katalog, min_score=args.min_score)
    if args.min_score is not None:
        print(f"Mindest-Erkennungssicherheit: {float(args.min_score):.2f} "
              f"(Voreinstellung {_cluster.MIN_SCORE:.2f})")
    lauf = nachtrag_rechnen(
        eingelesen, alte_zeilen, alt_kennungen,
        beispiele_alt=beispiele_lesen(os.path.join(args.ausgabe, DATEI_BEISPIELE)),
        bestaetigt=bestaetigt_lesen(args.bestaetigt),
        vorgaben=vorgaben_lesen(args.vorgaben),
        zuordnung=args.zuordnung, min_groesse=args.min_groesse)
    print(nachtrag_bericht_text(lauf["bericht"]))
    if not schreiben_an:
        print("Ohne --schreiben wurde NICHTS geschrieben.")
        return 0
    if (not lauf["bericht"]["neue_gesichter"]
            and not lauf["bericht"]["korrigierte_altgesichter"]):
        print("Nichts zu tun: keine neuen Gesichter oder alten Korrekturen "
              "(es wurde NICHTS geschrieben).")
        return 0
    ergebnis = nachtrag_schreiben(lauf, args.ausgabe, alte_zeilen)
    for pfad in ergebnis["sicherungen"]:
        print(f"gesichert: {os.path.basename(pfad)}")
    for pfad in ergebnis["geschrieben"]:
        print(f"geschrieben: {os.path.basename(pfad)}")
    return 0


def main(argv=None) -> int:
    zerleger = argparse.ArgumentParser(
        description="Gruppiert alle Gesichter zu Personen (Mittelpunkt-Verfahren, "
                    "cannot-link je Bild) und schreibt Zuordnung + Quiz-Beispiele. "
                    "Loescht nichts, ruft kein Netz, zeigt nur Zahlen.")
    zerleger.add_argument("--vektoren", action="append", default=None,
                          help="Vektordatei (wiederholbar); Standard: die drei "
                               "Dateien aus Aufgabe 1, Aufgabe 3 und Videos")
    zerleger.add_argument("--ausgabe", default=STANDARD_AUSGABE,
                          help="Ausgabeordner (PFLICHT ausserhalb des Repos)")
    zerleger.add_argument("--ausgabe-kandidat", default=STANDARD_KANDIDAT,
                          help="Kandidatenordner von v2 (Standard: ~/foto_sortierung/"
                               "kandidat_v2); v2 schreibt NIE direkt in --ausgabe")
    zerleger.add_argument("--produktiv", action="store_true",
                          help="v2 in den produktiven Ordner schreiben — nur mit "
                               "gueltiger --freigabe (Auflage 1)")
    zerleger.add_argument("--freigabe", default=None,
                          help="Freigabedatei (JSON) fuer --verfahren v2 --schreiben "
                               "(Auflage 6); ohne sie wird nichts geschrieben")
    zerleger.add_argument("--geraetestand", default=STANDARD_GERAETESTAND,
                          help="Geraetestand des Handys (JSON, G0/Auflage 2) — "
                               "Pflicht fuer jedes Schreiben mit v2")
    zerleger.add_argument("--ohne-geraetenachweis", action="store_true",
                          help="v2 ohne Geraetestand rechnen — nur fuer eine "
                               "TROCKENMESSUNG (schreibt nie etwas; Auflage 2)")
    zerleger.add_argument("--katalog", default=None, help="Personen-Katalog (optional)")
    zerleger.add_argument("--bestaetigt", default=STANDARD_BESTAETIGT)
    zerleger.add_argument("--vorgaben", default=STANDARD_VORGABEN)
    zerleger.add_argument("--zuordnung", type=float, default=ZUORDNUNG_AEHNLICH)
    zerleger.add_argument("--verschmelzen", type=float, default=VERSCHMELZ_AEHNLICH)
    zerleger.add_argument("--zwilling", type=float, default=ZWILLING_AEHNLICH)
    zerleger.add_argument("--min-groesse", type=int, default=MIN_GROESSE)
    zerleger.add_argument("--min-score", type=float, default=None,
                          help="Mindest-Erkennungssicherheit fuer die Gruppierung "
                               "(Standard 0,6; empfohlen 0,8 seit 08.10.2026) — "
                               "gilt auch beim --nachtragen")
    zerleger.add_argument("--nachtragen", action="append", default=None,
                          help="Vektordatei(en) NUR an die bestehenden Gruppen haengen "
                               "(nichts neu rechnen; Trockenlauf ist Standard, "
                               "--schreiben schreibt, vorher *.vorher-Sicherung)")
    zerleger.add_argument("--verfahren", choices=("v1", "v2"), default="v1",
                          help="v1 (Standard): ein Mittelpunkt je Gruppe. v2: sauberer "
                               "Kern, Lebensabschnitte, Andocken (Gruppierung v2)")
    zerleger.add_argument("--bewerten", action="store_true",
                          help="zusaetzlich die Bewertung an den eigenen Entscheidungen "
                               "ausgeben: bestehende Zuordnung gegen diesen Lauf, nur Zahlen")
    zerleger.add_argument("--trocken", action="store_true", help="nichts schreiben (Vorrang)")
    zerleger.add_argument("--schreiben", action="store_true", help="wirklich schreiben")
    args = zerleger.parse_args(argv)

    pruefe_ausserhalb_repo(args.ausgabe)
    nachtragen = list(args.nachtragen or [])
    pfade = args.vektoren or [p for p in STANDARD_VEKTOREN if os.path.isfile(p)]
    schreiben_an = bool(args.schreiben) and not bool(args.trocken)
    # Argument-Widerspruch zuerst (vor G0): --nachtragen kennt nur v1.
    if nachtragen and (args.verfahren != "v1" or args.bewerten):
        print("Fehler: --nachtragen kennt nur das Verfahren v1 und keine "
              "--bewerten-Ausgabe.")
        return 2
    if args.verfahren == "v2":
        try:
            pruefe_ausserhalb_repo(args.ausgabe_kandidat)
        except SystemExit:
            return 2
        except PersonenFehler as problem:
            print(f"Fehler: {problem}")
            return 2
        if schreiben_an and not args.freigabe:
            print("Ohne Freigabe wird v2 nichts geschrieben (Auflage 6): es fehlt "
                  "--freigabe <datei.json>. Es wurde nichts gerechnet und nichts "
                  "geschrieben.")
            return 3
        # G0/G1 (Auflage 2) VOR jedem Rechnen: Pflichtquellen, Geraetenachweis,
        # Zustand der Grundwahrheit. Die Reihenfolge ist bewusst: erst das
        # Schreib-Tor der Auflage 6 (Exit 3 ohne --freigabe), dann die Grundlage.
        try:
            g0 = g0_pruefen(args, schreiben_an)
        except PersonenFehler as problem:
            print(f"Fehler: {problem}")
            print("Es wurde nichts gerechnet und nichts geschrieben (Exit 2).")
            return 2
        if g0["code"] is not None:
            return g0["code"]
        bestaetigt_v2, vorgaben_v2 = g0["bestaetigt"], g0["vorgaben"]
    try:
        if nachtragen:
            return _nachtragen_main(args, nachtragen, schreiben_an)
        if not pfade:
            raise PersonenFehler("Keine Vektordatei gefunden (Standardpfade fehlen).")
        katalog = _cluster.katalog_lesen(args.katalog) if args.katalog else {}
        altbestand = _cluster.altbestand_lesen_datei(
            os.path.join(args.ausgabe, DATEI_KENNUNGEN))
        print("Personen gruppieren — " + ("Schreiben ist eingeschaltet" if schreiben_an
                                           else "Trockenlauf (es wird NICHTS geschrieben)"))
        if args.min_score is not None:
            print(f"Mindest-Erkennungssicherheit: {args.min_score:.2f}")
        eingelesen = gesichter_lesen(pfade, katalog, min_score=args.min_score)
        if args.verfahren == "v2":
            # Schon oben mit ``pflicht=True`` gelesen (G0) — hier nichts erneut.
            bestaetigt, vorgaben = bestaetigt_v2, vorgaben_v2
        else:
            bestaetigt = bestaetigt_lesen(args.bestaetigt)
            vorgaben = vorgaben_lesen(args.vorgaben)
        if args.verfahren == "v2":
            lauf = lauf_rechnen_v2(
                eingelesen, altbestand=altbestand, bestaetigt=bestaetigt, vorgaben=vorgaben,
                alte_zuordnung=alte_zuordnung_lesen(os.path.join(args.ausgabe, DATEI_ZUORDNUNG)),
                zuordnung=args.zuordnung, verschmelzen=args.verschmelzen,
                zwilling=args.zwilling, min_groesse=args.min_groesse)
        else:
            lauf = lauf_rechnen(eingelesen, altbestand=altbestand, bestaetigt=bestaetigt,
                                vorgaben=vorgaben,
                                zuordnung=args.zuordnung, verschmelzen=args.verschmelzen,
                                zwilling=args.zwilling, min_groesse=args.min_groesse)
        print(bericht_text(lauf["bericht"]))
        if args.bewerten:
            print("Bewertung an den eigenen Entscheidungen (bestehende Zuordnung = vorher, "
                  "dieser Lauf = nachher; nichts wird dafuer geschrieben):")
            print(bewertung_text(lauf, args.ausgabe, bestaetigt, vorgaben,
                                 args.bestaetigt, args.vorgaben))
        if schreiben_an:
            if args.verfahren == "v2":
                ziel = args.ausgabe if args.produktiv else args.ausgabe_kandidat
                parameter = parameter_stand(args)
                grund = freigabe_pruefen(
                    freigabe_lesen(args.freigabe),
                    eingabe_hash(pfade, args.bestaetigt, args.vorgaben,
                                 os.path.join(args.ausgabe, DATEI_KENNUNGEN),
                                 os.path.join(args.ausgabe, DATEI_ZUORDNUNG), parameter),
                    parameter, lauf.get("sperrzahlen") or {})
                if grund:
                    print(f"Freigabe abgelehnt ({grund}) — es wurde nichts geschrieben.")
                    return 3
                print("Freigabe gueltig (Snapshot-hash, Parameter, Urteil, Sperrzahlen 0).")
                print("Ziel: " + ("PRODUKTIVER Ordner (--produktiv)" if args.produktiv
                                  else "Kandidatenordner"))
                pruefe_ausserhalb_repo(ziel)
                for pfad in _stempel_sichern(ziel):
                    print(f"gesichert: {os.path.basename(pfad)}")
                for pfad in schreiben(lauf, ziel):
                    print(f"geschrieben: {os.path.basename(pfad)}")
            else:
                pruefe_ausserhalb_repo(args.ausgabe)
                for pfad in _stempel_sichern(args.ausgabe):
                    print(f"gesichert: {os.path.basename(pfad)}")
                for pfad in schreiben(lauf, args.ausgabe):
                    print(f"geschrieben: {os.path.basename(pfad)}")
        else:
            print("Ohne --schreiben wurde NICHTS geschrieben.")
        return 0
    except (PersonenFehler, ValueError) as problem:
        print(f"Fehler: {problem}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
