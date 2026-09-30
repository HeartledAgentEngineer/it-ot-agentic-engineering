"""Personen-Andockung der Ereignis-Knoten (N27 Schritt 4 von 5, 29.09.2026).

Warum dieses Werkzeug:
  Schritt 1 (``ereignisse_bauen.py``) hat je Anlass einen **Ereignis-Knoten**
  gelegt, Schritt 2 (``chat_andocken.py``) die Chats angebunden, Schritt 3
  (``kalender_andocken.py``) den Kalender. Schritt 4 dockt die **Personen** an:
  zu jedem Anlass wird gefragt, welche **Gesichts-Cluster** (``Person_001`` …)
  auf seinen Bildern liegen, wie viele Bilder und Gesichter das sind — und
  welcher **Name** dazu passt. Damit laesst sich ein Tag spaeter mit den
  Menschen verbinden, die dazugehoeren.

Die **Kernregel** dieses Schritts (nicht verhandelbar):
  Das Werkzeug **schlaegt vor**, es **benennt nicht**. Ein Name erscheint nur,
  wenn er in der Bestaetigungsdatei ``personen_bestaetigt.json`` steht, die der
  Nutzer pflegt. Ein Vorschlag darf sich **niemals selbst bestaetigen**:
  ``vorschlag`` und ``name`` sind zwei verschiedene Felder, und
  ``bestaetigung_anwenden`` liest **ausschliesslich** aus der Datei.

Was dieses Werkzeug bewusst NICHT tut:
  * **Kein Nachrichtentext.** Aus ``chat_andockung.jsonl`` werden nur
    ``anlass_id``, ``chat_name`` und — als **Rueckfall**, wenn ``chat_name``
    leer ist — die **Namen** der ``beteiligte`` gelesen: nie der
    Nachrichteninhalt, nie die Nachrichten-Kennungen, nie ein Inhaltsfeld.
    Als Namens**vorschlag** zaehlt ``chat_name`` (siehe
    ``_namenskandidaten``); die Nummern-Maske der ``beteiligte`` wird nie
    gelesen.
  * **Keine Rufnummern.** Es wird nie eine Nummern-Maske gelesen; die Ausgabe
    enthaelt keinen Maskentext und keine Ziffernfolge einer Rufnummer.
  * **Kein Bild, kein Netz.** Kein Bildwerkzeug, kein Netz-Baustein, kein
    Cloud-Aufruf, kein Download. Es wird keine Bilddatei geoeffnet. Gelesen
    werden ausschliesslich lokale JSON/JSONL-Dateien; gerechnet wird mit
    ``personen_cluster`` (Standardbibliothek + ``numpy``).
  * **Kein Schreiben ins Repo.** Ein Ausgabeziel im Repo ergibt eine deutsche
    Klartextmeldung und ``SystemExit(2)`` — geschrieben wird dann nichts
    (Wiederverwendung von ``personen_cluster.pruefe_ausserhalb_repo``).
  * **Keine Loeschung** ausser der **eigenen** temp-Datei beim atomaren
    Schreiben; es gibt keine Loeschfunktion, auch nicht "zur Sicherheit".
  * **Keine Kennungs-Verwaltung.** Dieses Werkzeug schreibt **keinen**
    Altbestand — der Kennungs-Altbestand des Nachbarmoduls wird **nicht**
    geschrieben (sonst verschoeben sich die Kennungen).
  * **Kein Schreiben ohne ``--schreiben``.** Der Standard ist der Trockenlauf.

Eingaben (alle **nur lesend**, alle per CLI ueberschreibbar, alle ausserhalb
des Repos):

  ``--ereignisse``       ``~/foto_sortierung/ereignisse.jsonl``
  ``--vektoren``         ``~/foto_sortierung/personen_vektoren_n9e.jsonl`` und
                         ``…_n9e_burst.jsonl`` (wiederholbarer Schalter)
  ``--alt-kennungen``    ``~/foto_sortierung/personen_n9f/kennungen.json``
  ``--chat-andockung``   ``~/foto_sortierung/chat_andockung.jsonl``
  ``--bestaetigung``     ``~/foto_sortierung/personen_bestaetigt.json``
                         (**darf fehlen** — dann bleibt jede Person unbenannt)

Ausgaben (nur mit ``--schreiben``):

  ``~/foto_sortierung/personen_andockung.jsonl``  (JSONL, eine Zeile je Anlass)
  ``~/foto_sortierung/personen_vorschlaege.json`` (Uebersicht fuer das Handy)

  Die Ziele sind per ``--ausgabe-knoten``/``--ausgabe-vorschlaege``
  ueberschreibbar (noetig fuer Probeschreiblaeufe in einen frischen Ordner; die
  beauftragten Standardwerte bleiben genau wie oben).

Ausgabeschema ``personen_andockung.jsonl`` (eingefroren, ``sort_keys=True``)::

    {"art": "personen_andockung", "anlass_id": "…", "kennung": "E-…",
     "datum": "…",
     "personen": [{"kennung": "Person_001", "bilder": 3, "gesichter": 4,
                   "bestaetigt": false, "name": null}],
     "quellen": {"personen": "personen_vektoren_*.jsonl+personen_cluster.lauf_rechnen",
                 "anlass": "ereignisse.jsonl"},
     "stand": "…"}

Ausgabeschema ``personen_vorschlaege.json``::

    {"art": "personen_vorschlaege", "stand": "…", "anzahl_personen": 12,
     "anzahl_bestaetigt": 0,
     "hinweis": "Namen nur nach Bestaetigung; Vorschlaege sind Vorschlaege.",
     "personen": [{"kennung": "Person_001", "anzahl_anlaesse": 2,
                   "anzahl_bilder": 5, "anzahl_gesichter": 6, "von": "…",
                   "bis": "…", "namen": [{"name": "…", "anzahl": 7}],
                   "vorschlag": "…", "bestaetigt": false,
                   "bestaetigter_name": null}]}

Bestätigungsdatei (der Nutzer pflegt sie, z. B. am Handy/PC)::

    {"hinweis": "Nur hier eingetragene Namen werden verwendet.",
     "bestaetigt": {"Person_001": "Beispielname"}}

  Fehlt die Datei oder ist ein Eintrag leer ⇒ die Person bleibt **unbenannt**.

Aufruf (Kommandozeile)::

    python tools/foto_sortierung/personen_andocken.py --trocken
    python tools/foto_sortierung/personen_andocken.py --ausgabe-knoten C:/tmp/p.jsonl --schreiben --stand 2026-09-29T02:00:00+02:00

Als Modul (Tests, spaetere Schritte): ``main(argv=[...])`` (Alias ``haupt``)
sowie die oeffentlichen Funktionen ``vektoren_lesen``, ``ereignisse_lesen``,
``ereignis_index``, ``personen_je_bild``, ``andocken``,
``kandidaten_je_person``, ``vorschlaege_bauen``, ``bestaetigung_lesen``,
``bestaetigung_anwenden``, ``knotenzeilen_bauen``, ``schreiben``,
``bericht_bauen``.
"""

from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HIER))            # .../personal_ai_agent

# ── Wiederverwendung statt Nachbau ────────────────────────────────────────
# Das Rechenmodul der Personen-Stufe wird **nicht** nachgebaut: Clustering,
# Altbestand und Repo-Schutz kommen aus ``personen_cluster``. Weil dieses Modul
# in Tests ueber den Dateipfad geladen wird (dort steht das Werkzeugverzeichnis
# nicht auf ``sys.path``), gibt es einen Rueckfall-Lader auf dieselbe Datei.
try:
    import personen_cluster as _personen_cluster
except ImportError:                       # pragma: no cover — Test-Ladeweg
    _spez = importlib.util.spec_from_file_location(
        "personen_cluster", os.path.join(HIER, "personen_cluster.py"))
    if _spez is None or _spez.loader is None:      # pragma: no cover
        raise ImportError(
            "personen_cluster.py liegt nicht neben personen_andocken.py.")
    _personen_cluster = importlib.util.module_from_spec(_spez)
    _spez.loader.exec_module(_personen_cluster)

# Repo-Schutz und Fehlertyp kommen woertlich aus dem Nachbarmodul.
pruefe_ausserhalb_repo = _personen_cluster.pruefe_ausserhalb_repo
PersonenFehler = _personen_cluster.PersonenFehler

# ── Vorgabepfade: ausserhalb des Repos — dort liegen Biometrie und Namen ──
STANDARD_BASIS = os.path.join(os.path.expanduser("~"), "foto_sortierung")
STANDARD_EREIGNISSE = os.path.join(STANDARD_BASIS, "ereignisse.jsonl")
STANDARD_VEKTOREN = (
    os.path.join(STANDARD_BASIS, "personen_vektoren_n9e.jsonl"),
    os.path.join(STANDARD_BASIS, "personen_vektoren_n9e_burst.jsonl"),
)
STANDARD_ALT_KENNUNGEN = os.path.join(STANDARD_BASIS, "personen_n9f",
                                      "kennungen.json")
STANDARD_CHAT_ANDOCKUNG = os.path.join(STANDARD_BASIS, "chat_andockung.jsonl")
STANDARD_BESTAETIGUNG = os.path.join(STANDARD_BASIS,
                                     "personen_bestaetigt.json")
STANDARD_AUSGABE_KNOTEN = os.path.join(STANDARD_BASIS,
                                       "personen_andockung.jsonl")
STANDARD_AUSGABE_VORSCHLAEGE = os.path.join(STANDARD_BASIS,
                                            "personen_vorschlaege.json")

# Die beiden Ausgabe-Arten (stehen so im ``art``-Feld).
ART_KNOTEN = "personen_andockung"
ART_VORSCHLAEGE = "personen_vorschlaege"

# Der ehrliche Hinweis der Vorschlagsdatei (woertlich beauftragt).
HINWEIS_VORSCHLAEGE = ("Namen nur nach Bestaetigung; Vorschlaege sind "
                       "Vorschlaege.")

# Herkunft der Felder (fuer den ``quellen``-Block, ehrlich benannt).
QUELLE_PERSONEN = "personen_vektoren_*.jsonl+personen_cluster.lauf_rechnen"
QUELLE_ANLASS = "ereignisse.jsonl"

# Hoechstzahl der Vorschlagsnamen je Person (``--namen-je-person``).
NAMEN_JE_PERSON = 5

# Kennungs-Muster: ``Person_001`` … (drei Stellen) — nur solche Schluessel
# zaehlen in der Bestaetigungsdatei als Person.
KENNUNG_MUSTER = r"^Person_\d{3}$"

# Die Schluessel des eingefrorenen Ausgabeschemas (bindend fuer Folgeschritte).
KNOTEN_SCHLUESSEL = ("art", "anlass_id", "kennung", "datum", "personen",
                     "quellen", "stand")
KNOTEN_PERSON_SCHLUESSEL = ("kennung", "bilder", "gesichter", "bestaetigt",
                            "name")
VORSCHLAG_SCHLUESSEL = ("anzahl_anlaesse", "anzahl_bilder", "anzahl_gesichter",
                        "bestaetigt", "bestaetigter_name", "bis", "kennung",
                        "namen", "von", "vorschlag")
VORSCHLAG_NAME_SCHLUESSEL = ("anzahl", "name")
VORSCHLAEGE_DOKUMENT_SCHLUESSEL = ("art", "stand", "anzahl_personen",
                                   "anzahl_bestaetigt", "hinweis", "personen")

# Feste Reihenfolge der Bild-Arten im Bericht (wie die Sollwert-Tabelle).
ART_REIHENFOLGE = ("gruppe", "leer", "menge", "unklar")


# ── Kleine Helfer (tolerant lesen, nie raten) ─────────────────────────────

def _text(wert) -> str:
    """Ein Feld als Text lesen — Nicht-Text und ``None`` werden zu ``""``."""
    return wert.strip() if isinstance(wert, str) else ""


def _zahl(n) -> str:
    """Eine Zahl mit deutschen Tausenderpunkten (nur fuer die Ausgabe)."""
    try:
        return f"{int(n):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(n)


def _als_int(wert):
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


def _ist_person(wert) -> bool:
    """Ob ein Schluessel eine Personen-Kennung ``Person_001`` ist.

    Es zaehlt genau die Schreibweise, die ``personen_cluster.KENNUNG_MUSTER``
    (``Person_%03d``) erzeugt: mindestens drei Ziffern, ohne zusaetzliche
    fuehrende Nullen — ``Person_001`` und ab der 1.000. Gruppe ``Person_1000``,
    aber nicht ``Person_01`` oder ``Person_0001``. (Bis 30.09.2026 galten nur
    genau drei Ziffern; ab 1.000 Gruppen waeren Namen still ignoriert worden.)
    Fremde Schluessel sind keine Person und werden gezaehlt statt geraten.
    """
    text = _text(wert)
    if not text.startswith("Person_"):
        return False
    rest = text[len("Person_"):]
    return rest.isdigit() and "%03d" % int(rest) == rest


def _stand_jz(stand=None) -> str:
    """Den Zeitstempel lesen — ohne Angabe der aktuelle (mit Zeitzone)."""
    text = _text(stand)
    if text:
        return text
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


# ── Zaehl-Container: eine Liste/ein Dict, das seine Zahlen mitbringt ──────
#
# Die beauftragten Rueckgabetypen sind ``list[dict]`` bzw. ``dict`` — die
# geforderten Zaehlungen (defekte Zeilen, Kollisionen, Bilder ohne Anlass,
# fremde Schluessel) brauchen aber einen Platz. Sie reisen als Attribute am
# Ergebnis mit: ``ergebnis.defekt`` ist zugleich ``len(ergebnis)``-kompatibel,
# weil die Klasse von ``list``/``dict`` erbt.

class ZaehlListe(list):
    """Eine Liste mit Zusatzzahlen (``defekt``, ``ohne_anlass`` …) als Attribute."""

    def __init__(self, werte=(), **zahlen):
        super().__init__(werte)
        for name, wert in zahlen.items():
            setattr(self, name, wert)


class ZaehlDict(dict):
    """Ein Dict mit Zusatzzahlen (``kollisionen``, ``fremde`` …) als Attribute."""

    def __init__(self, werte=(), **zahlen):
        super().__init__(werte)
        for name, wert in zahlen.items():
            setattr(self, name, wert)


# ── 1. Lesen (lokal, nur lesend, kein Netz) ───────────────────────────────

def vektoren_lesen(pfade) -> dict:
    """Die Vektordateien (JSONL) lesen — nur lesend, kein Netz, kein Bild.

    ``pfade`` ist ein Pfad oder eine Liste von Pfaden. Je brauchbarer Zeile
    (ein JSON-**Objekt**) kommt genau ein Eintrag in ``zeilen``; eine leere
    Zeile oder eine Zeile ohne JSON-Objekt zaehlt in ``defekt`` und bricht
    nichts ab (kaputte Zeile zaehlt, Rest wird gelesen). Eine **fehlende**
    Datei ist dagegen ein ``PersonenFehler`` mit Klartextmeldung (nichts wird
    geraten).

    Rueckgabe ``{"zeilen": [dict, …], "defekt": n, "dateien": [Pfad, …]}``.
    """
    if isinstance(pfade, (str, os.PathLike)):
        pfade = [pfade]
    elif isinstance(pfade, (list, tuple)):
        pfade = list(pfade)
    else:
        raise PersonenFehler("Fuer die Vektoren fehlt eine Pfadliste.")
    zeilen: list = []
    defekt = 0
    dateien: list = []
    for roh_pfad in pfade:
        pfad = _text(roh_pfad if isinstance(roh_pfad, str) else str(roh_pfad))
        if not pfad:
            raise PersonenFehler("Ein Vektorpfad ist leer.")
        if not os.path.isfile(pfad):
            raise PersonenFehler(f"Vektordatei nicht gefunden: {pfad}")
        dateien.append(pfad)
        try:
            with open(pfad, encoding="utf-8") as datei:
                for zeile in datei:
                    roh = zeile.strip()
                    if not roh:
                        defekt += 1
                        continue
                    try:
                        daten = json.loads(roh)
                    except ValueError:
                        defekt += 1
                        continue
                    if not isinstance(daten, dict):
                        defekt += 1
                        continue
                    zeilen.append(daten)
        except OSError as problem:
            raise PersonenFehler(
                f"Vektordatei nicht lesbar ({problem.__class__.__name__}): "
                f"{pfad}") from None
    return {"zeilen": zeilen, "defekt": defekt, "dateien": dateien}


def ereignisse_lesen(pfad) -> ZaehlListe:
    """Die Ereignis-Knoten lesen — **nur** Zeilen mit ``art == "ereignis"``.

    Andere Zeilenarten (falls es sie gibt) und defekte Zeilen werden gezaehlt
    (``ergebnis.defekt``) und uebersprungen; nichts bricht ab. Eine fehlende
    Datei ist ein ``PersonenFehler``. Je Knoten bleiben ``anlass_id``,
    ``kennung``, ``datum`` und ``datei_kennungen`` erhalten; die Reihenfolge
    der Datei bleibt.
    """
    pfad = _text(pfad)
    if not pfad:
        raise PersonenFehler("Kein Pfad fuer die Ereignisse angegeben.")
    if not os.path.isfile(pfad):
        raise PersonenFehler(f"Ereignisse nicht gefunden: {pfad}")
    ereignisse: list = []
    defekt = 0
    try:
        with open(pfad, encoding="utf-8") as datei:
            for zeile in datei:
                roh = zeile.strip()
                if not roh:
                    defekt += 1
                    continue
                try:
                    daten = json.loads(roh)
                except ValueError:
                    defekt += 1
                    continue
                if not isinstance(daten, dict) or daten.get("art") != "ereignis":
                    defekt += 1
                    continue
                ereignisse.append(daten)
    except OSError as problem:
        raise PersonenFehler(
            f"Ereignisse nicht lesbar ({problem.__class__.__name__}): "
            f"{pfad}") from None
    return ZaehlListe(ereignisse, defekt=defekt)


def ereignis_index(ereignisse) -> ZaehlDict:
    """``str(datei_kennung) -> ereignis`` bauen — **erste** Zuordnung gewinnt.

    Die Schluessel sind die Datei-Kennungen der Ereignisse (als Text, weil die
    Bild-Kennungen der Vektoren Text sind). Nennt mehr als ein Ereignis
    dieselbe Datei-Kennung, bleibt die **erste** Zuordnung stehen; jede weitere
    zaehlt in ``ergebnis.kollisionen`` (gemeldet, nicht stillschweigend
    ueberschrieben).
    """
    index: dict = {}
    kollisionen = 0
    for ereignis in ereignisse if isinstance(ereignisse, (list, tuple)) else []:
        if not isinstance(ereignis, dict):
            continue
        kennungen = ereignis.get("datei_kennungen")
        if not isinstance(kennungen, (list, tuple)):
            continue
        for datei_kennung in kennungen:
            if datei_kennung is None or isinstance(datei_kennung, bool):
                continue
            schluessel = str(datei_kennung).strip()
            if not schluessel:
                continue
            if schluessel in index:
                kollisionen += 1
                continue
            index[schluessel] = ereignis
    return ZaehlDict(index, kollisionen=kollisionen)


def _chat_knoten_lesen(pfad) -> ZaehlListe:
    """Die Chat-Andockungs-Knoten lesen — nur ``anlass_id`` und ``chats``.

    Gelesen werden ausschliesslich ``anlass_id`` und je Chat ``chat_name``
    sowie — als Rueckfall, wenn ``chat_name`` leer ist — die **Namen** der
    ``beteiligte``: **nie** ein Nachrichtentext, nie
    die Nachrichten-Kennungen, nie eine Nummern-Maske. Defekte Zeilen werden
    gezaehlt (``ergebnis.defekt``), nichts bricht ab; eine fehlende Datei ist
    ein ``PersonenFehler``.
    """
    pfad = _text(pfad)
    if not pfad:
        raise PersonenFehler("Kein Pfad fuer die Chat-Andockung angegeben.")
    if not os.path.isfile(pfad):
        raise PersonenFehler(f"Chat-Andockung nicht gefunden: {pfad}")
    knoten: list = []
    defekt = 0
    try:
        with open(pfad, encoding="utf-8") as datei:
            for zeile in datei:
                roh = zeile.strip()
                if not roh:
                    defekt += 1
                    continue
                try:
                    daten = json.loads(roh)
                except ValueError:
                    defekt += 1
                    continue
                if not isinstance(daten, dict) or "anlass_id" not in daten:
                    defekt += 1
                    continue
                knoten.append(daten)
    except OSError as problem:
        raise PersonenFehler(
            f"Chat-Andockung nicht lesbar ({problem.__class__.__name__}): "
            f"{pfad}") from None
    return ZaehlListe(knoten, defekt=defekt)


# ── 2. Personen auf Bilder zurueckfuehren ─────────────────────────────────

def personen_je_bild(lauf) -> dict:
    """Aus einem Clustering-Lauf ``Person_00x -> [bild_id, …]`` bauen.

    Quelle sind ``lauf["kennungen"]`` (mit ``indizes`` = Stellen in
    ``lauf["eintraege"]``) und ``lauf["eintraege"]`` (je Eintrag ein Gesicht
    mit ``bild_id``). **Je Gesicht** kommt ein ``bild_id``-Eintrag: eine Person
    mit mehreren Gesichtern im selben Foto hat dieselbe ``bild_id`` mehrfach —
    nur so laesst sich spaeter zwischen **Bildern** (verschiedene ``bild_id``)
    und **Gesichtern** (Eintraege) unterscheiden. Jede Liste ist **sortiert**.

    Unbrauchbare Indizes (kein int, ausserhalb) und Eintraege ohne ``bild_id``
    fallen weg; es wird nichts geraten. Unbekannte Kennungen sind erlaubt.
    """
    daten = lauf if isinstance(lauf, dict) else {}
    eintraege = daten.get("eintraege")
    eintraege = eintraege if isinstance(eintraege, (list, tuple)) else []
    ergebnis: dict = {}
    for eintrag in daten.get("kennungen") or []:
        if not isinstance(eintrag, dict):
            continue
        kennung = _text(eintrag.get("kennung"))
        if not kennung:
            continue
        bilder: list = []
        for stelle in eintrag.get("indizes") or []:
            index = _als_int(stelle)
            if index is None or index < 0 or index >= len(eintraege):
                continue
            gesicht = eintraege[index]
            if not isinstance(gesicht, dict):
                continue
            bild_id = gesicht.get("bild_id")
            if bild_id is None or isinstance(bild_id, bool):
                continue
            text = str(bild_id).strip()
            if not text:
                continue
            bilder.append(text)
        bilder.sort()
        ergebnis[kennung] = bilder
    return ergebnis


# ── 3. Die Andockung bauen (rein, ohne I/O) ───────────────────────────────

def _leerer_anlass(anlass_id: str, kennung: str, datum) -> dict:
    """Einen Anlass-Eintrag mit leerer Personen-Menge anlegen."""
    return {"anlass_id": anlass_id, "kennung": kennung, "datum": datum,
            "personen": {}}


def andocken(personen_bilder, ereignis_index) -> ZaehlListe:
    """Je Anlass die Personen sammeln — **reine** Funktion ohne Datei/Netz.

    ``personen_bilder`` ist ``Person_00x -> [bild_id, …]`` (siehe
    ``personen_je_bild``), ``ereignis_index`` ist ``str(datei_kennung) ->
    ereignis`` (siehe ``ereignis_index``). Ueber die Bilder einer Person wird
    der Anlass gefunden; je Anlass entsteht **ein** Eintrag mit den beteiligten
    Personen::

        {"anlass_id", "kennung", "datum",
         "personen": [{"kennung", "bilder", "gesichter"}, …],
         "quellen": {"personen": …, "anlass": …}}

    ``bilder`` = Zahl **verschiedener** Bilder des Anlasses, ``gesichter`` =
    Zahl der Gesichts-Eintraege. Ausgegeben werden **nur** Anlaesse mit
    mindestens einer Person, sortiert nach ``anlass_id``; die Personen eines
    Anlasses stehen nach ``kennung`` sortiert.

    Bilder, die in **keinem** Ereignis stehen, werden gezaehlt und **nie**
    stillschweigend verworfen: ``ergebnis.ohne_anlass`` = Zahl der Bilder ohne
    Anlass-Zuordnung, ``ergebnis.personen_ohne_anlass`` = Zahl der Personen,
    die auf keinem Anlass liegen.
    """
    index = ereignis_index if isinstance(ereignis_index, dict) else {}
    eintraege: dict = {}
    bilder_ohne: set = set()
    personen_ohne: list = []
    for kennung in sorted(personen_bilder if isinstance(personen_bilder, dict)
                          else {}):
        bilder = personen_bilder.get(kennung)
        bilder = bilder if isinstance(bilder, (list, tuple)) else []
        getroffen = False
        for bild_id in bilder:
            schluessel = str(bild_id).strip()
            if not schluessel:
                continue
            ereignis = index.get(schluessel)
            if not isinstance(ereignis, dict):
                bilder_ohne.add(schluessel)
                continue
            getroffen = True
            anlass_id = _text(ereignis.get("anlass_id"))
            eintrag = eintraege.get(anlass_id)
            if eintrag is None:
                eintrag = _leerer_anlass(
                    anlass_id, _text(ereignis.get("kennung")) or ("E-" + anlass_id),
                    ereignis.get("datum"))
                eintraege[anlass_id] = eintrag
            person = eintrag["personen"].get(kennung)
            if person is None:
                person = {"bilder": set(), "gesichter": 0}
                eintrag["personen"][kennung] = person
            person["bilder"].add(schluessel)
            person["gesichter"] += 1
        if not getroffen:
            personen_ohne.append(kennung)

    knoten: list = []
    for anlass_id in sorted(eintraege):
        eintrag = eintraege[anlass_id]
        personen = []
        for kennung in sorted(eintrag["personen"]):
            person = eintrag["personen"][kennung]
            personen.append({"kennung": kennung,
                             "bilder": len(person["bilder"]),
                             "gesichter": person["gesichter"]})
        knoten.append({
            "anlass_id": eintrag["anlass_id"],
            "kennung": eintrag["kennung"],
            "datum": eintrag["datum"],
            "personen": personen,
            "quellen": {"personen": QUELLE_PERSONEN, "anlass": QUELLE_ANLASS},
        })
    return ZaehlListe(knoten, ohne_anlass=len(bilder_ohne),
                      personen_ohne_anlass=len(personen_ohne))


# ── 4. Kandidatennamen aus der Chat-Andockung ─────────────────────────────

def _chats_nach_anlass(chat_knoten) -> dict:
    """Chat-Knoten auf ``anlass_id -> knoten`` bringen (Liste oder Dict)."""
    if isinstance(chat_knoten, dict):
        return {str(k): v for k, v in chat_knoten.items()
                if isinstance(v, dict)}
    ergebnis: dict = {}
    for knoten in chat_knoten if isinstance(chat_knoten, (list, tuple)) else []:
        if not isinstance(knoten, dict):
            continue
        anlass_id = _text(knoten.get("anlass_id"))
        if anlass_id and anlass_id not in ergebnis:
            ergebnis[anlass_id] = knoten       # erste Zuordnung gewinnt
    return ergebnis


def _namenskandidaten(knoten) -> list:
    """Die Namensvorschlaege eines Anlasses sammeln — nur Namen, kein Text.

    Quelle je Chat ist **``chat_name``** (der Anzeigename des Chats, wie ihn
    ``chat_andocken.py`` gesetzt hat) und — falls der ``chat_name`` leer ist —
    die **Namen** der ``beteiligte``. Gelesen wird **kein** Nachrichtentext,
    **keine** Nummern-Maske, **keine** Nachrichten-Kennung.
    """
    namen: list = []
    for chat in knoten.get("chats") or []:
        if not isinstance(chat, dict):
            continue
        name = _text(chat.get("chat_name"))
        if name:
            namen.append(name)
            continue
        for beteiligter in chat.get("beteiligte") or []:
            if not isinstance(beteiligter, dict):
                continue
            weiterer = _text(beteiligter.get("name"))
            if weiterer:
                namen.append(weiterer)
    return namen


def kandidaten_je_person(andockung, chat_knoten) -> dict:
    """``Person_00x -> {name: anzahl}`` aus den Chats **ihrer** Anlaesse.

    Fuer jede Person werden die Anlaesse der Andockung besucht und deren Chats
    gezaehlt (siehe ``_namenskandidaten`` — nur ``chat_name`` und die Namen der
    ``beteiligte``, kein Nachrichtentext). Die Namen sind **absteigend** nach
    Zaehlung geordnet, bei Gleichstand **alphabetisch** (fester Zweitschluessel,
    damit das Ergebnis reproduzierbar ist).

    ``chat_knoten`` ist die Liste der Chat-Knoten aus ``chat_andockung.jsonl``
    (oder schon ein Dict ``anlass_id -> knoten``).
    """
    nach_anlass = _chats_nach_anlass(chat_knoten)
    ergebnis: dict = {}
    for knoten in andockung if isinstance(andockung, (list, tuple)) else []:
        if not isinstance(knoten, dict):
            continue
        anlass_id = _text(knoten.get("anlass_id"))
        namen = _namenskandidaten(nach_anlass.get(anlass_id, {}))
        for person in knoten.get("personen") or []:
            if not isinstance(person, dict):
                continue
            kennung = _text(person.get("kennung"))
            if not kennung:
                continue
            zaehler = ergebnis.setdefault(kennung, {})
            for name in namen:
                zaehler[name] = zaehler.get(name, 0) + 1
    return {kennung: _sortierte_namen(zaehler)
            for kennung, zaehler in ergebnis.items()}


def _sortierte_namen(zaehler: dict) -> dict:
    """Ein Namens-Zaehler-Dict in der festen Ordnung: Zahl absteigend, Name auf."""
    return {name: zaehler[name]
            for name in sorted(zaehler, key=lambda n: (-zaehler[n], n))}


# ── 5. Vorschlaege bauen (Vorschlag ist kein Name) ────────────────────────

def _personen_kennzahlen(andockung) -> dict:
    """Je Person Anlaesse, Bilder, Gesichter und Datumsspanne sammeln."""
    kennzahlen: dict = {}
    for knoten in andockung if isinstance(andockung, (list, tuple)) else []:
        if not isinstance(knoten, dict):
            continue
        anlass_id = _text(knoten.get("anlass_id"))
        datum = knoten.get("datum")
        datum_text = _text(datum)
        for person in knoten.get("personen") or []:
            if not isinstance(person, dict):
                continue
            kennung = _text(person.get("kennung"))
            if not kennung:
                continue
            eintrag = kennzahlen.setdefault(
                kennung, {"anlaesse": set(), "bilder": 0, "gesichter": 0,
                          "daten": []})
            eintrag["anlaesse"].add(anlass_id)
            eintrag["bilder"] += _als_int(person.get("bilder")) or 0
            eintrag["gesichter"] += _als_int(person.get("gesichter")) or 0
            if datum_text:
                eintrag["daten"].append(datum_text)
    return kennzahlen


def vorschlaege_bauen(andockung, kandidaten, namen_je_person: int = NAMEN_JE_PERSON) -> list:
    """Je Person einen Vorschlag bauen — **rein**, ohne Datei/Netz.

    Je Person ein Eintrag mit ``kennung``, ``anzahl_anlaesse``,
    ``anzahl_bilder``, ``anzahl_gesichter``, ``von``/``bis`` (fruehestes/letztes
    Anlass-Datum), den Top-``namen_je_person`` als ``namen``
    (``[{"name", "anzahl"}]``), dem **staerksten** Namen als ``vorschlag``
    (oder ``None``), sowie ``bestaetigt: false`` und ``bestaetigter_name:
    null``. Der Vorschlag ist **nicht** bestaetigt — das kann nur die
    Bestaetigungsdatei (``bestaetigung_anwenden``).

    Sortiert nach ``kennung``. Personen ohne Kandidatennamen behalten
    ``vorschlag: None`` und leere ``namen``.
    """
    kennzahlen = _personen_kennzahlen(andockung)
    grenze = _als_int(namen_je_person)
    grenze = grenze if grenze is not None and grenze > 0 else NAMEN_JE_PERSON
    alle = set(kennzahlen)
    if isinstance(kandidaten, dict):
        alle |= set(kandidaten)
    ergebnis: list = []
    for kennung in sorted(alle):
        werte = kennzahlen.get(kennung, {})
        daten = sorted(werte.get("daten") or [])
        zaehler = kandidaten.get(kennung) if isinstance(kandidaten, dict) else None
        zaehler = _sortierte_namen(zaehler) if isinstance(zaehler, dict) else {}
        namen = [{"name": name, "anzahl": anzahl}
                 for name, anzahl in list(zaehler.items())[:grenze]]
        ergebnis.append({
            "kennung": kennung,
            "anzahl_anlaesse": len(werte.get("anlaesse") or ()),
            "anzahl_bilder": werte.get("bilder", 0),
            "anzahl_gesichter": werte.get("gesichter", 0),
            "von": daten[0] if daten else None,
            "bis": daten[-1] if daten else None,
            "namen": namen,
            "vorschlag": namen[0]["name"] if namen else None,
            "bestaetigt": False,
            "bestaetigter_name": None,
        })
    return ergebnis


# ── 6. Bestaetigung lesen und anwenden ───────────────────────────────────

def bestaetigung_lesen(pfad) -> ZaehlDict:
    """Die Bestaetigungsdatei tolerant lesen — fehlend heisst leer.

    Format ``{"bestaetigt": {"Person_001": "Beispielname"}}``; ein fehlender
    Pfad oder eine fehlende Datei ergibt ``{}`` (der erste Lauf hat noch keine
    Bestaetigung). Auch eine flache Datei ohne ``bestaetigt``-Block wird
    gelesen, wenn ihre Schluessel Personen-Kennungen sind.

    Es zaehlen **nur** Schluessel im Muster ``Person_\\d{3}``; fremde Schluessel
    werden **gemeldet** (``ergebnis.fremde``) statt geraten. Leere oder
    nicht-Text-Namen werden gezaehlt (``ergebnis.leer``) und nicht uebernommen
    — eine Person ohne brauchbaren Namen bleibt **unbenannt**.
    """
    ergebnis = ZaehlDict(fremde=0, leer=0)
    pfad = _text(pfad)
    if not pfad or not os.path.isfile(pfad):
        return ergebnis
    try:
        with open(pfad, encoding="utf-8") as datei:
            daten = json.load(datei)
    except OSError as problem:
        raise PersonenFehler(
            f"Bestaetigung nicht lesbar ({problem.__class__.__name__}): "
            f"{pfad}") from None
    except ValueError as problem:
        raise PersonenFehler(
            f"Bestaetigung ist kein gueltiges JSON "
            f"({problem.__class__.__name__}): {pfad}") from None
    if not isinstance(daten, dict):
        raise PersonenFehler(f"Bestaetigung hat kein lesbares Format: {pfad}")
    roh = daten.get("bestaetigt")
    roh = roh if isinstance(roh, dict) else daten
    fremde = 0
    leer = 0
    gefunden: dict = {}
    for schluessel, wert in roh.items():
        if schluessel == "bestaetigt":
            continue                       # der Block-Name ist keine Person
        if not _ist_person(schluessel):
            fremde += 1
            continue
        name = _text(wert)
        if not name:
            leer += 1
            continue
        gefunden[str(schluessel)] = name
    return ZaehlDict(gefunden, fremde=fremde, leer=leer)


def bestaetigung_anwenden(vorschlaege, bestaetigung) -> list:
    """``bestaetigt``/``bestaetigter_name`` **nur** aus der Datei setzen.

    Der ``vorschlag`` bleibt **unveraendert** (Vorschlag ≠ Name): ein Vorschlag
    bestaetigt sich nie selbst. Ohne Eintrag bleibt die Person unbestaetigt
    (``bestaetigt: false``, ``bestaetigter_name: null``). Die Eingaben werden
    nicht veraendert; zurueck kommt eine neue Liste.
    """
    quelle = bestaetigung if isinstance(bestaetigung, dict) else {}
    ergebnis: list = []
    for vorschlag in vorschlaege if isinstance(vorschlaege, (list, tuple)) else []:
        if not isinstance(vorschlag, dict):
            continue
        neu = dict(vorschlag)
        kennung = _text(neu.get("kennung"))
        name = quelle.get(kennung) if kennung else None
        name = name if isinstance(name, str) and name.strip() else None
        neu["vorschlag"] = vorschlag.get("vorschlag")   # unveraendert
        neu["bestaetigt"] = bool(name)
        neu["bestaetigter_name"] = name
        ergebnis.append(neu)
    return ergebnis


# ── 7. Ausgabezeilen und Vorschlagsdokument ──────────────────────────────

def knotenzeilen_bauen(andockung, bestaetigung, stand=None) -> list:
    """Die Ausgabezeilen der ``personen_andockung.jsonl`` bauen — **rein**.

    Je Anlass eine Zeile im eingefrorenen Schema::

        {"art", "anlass_id", "kennung", "datum",
         "personen": [{"kennung", "bilder", "gesichter",
                       "bestaetigt", "name"}],
         "quellen": {"personen", "anlass"}, "stand"}

    Ein ``name`` steht **nur** nach Bestaetigung (sonst ``null``); der Name
    kommt allein aus ``bestaetigung``. ``stand`` ist injizierbar (Tests bleiben
    reproduzierbar); ohne Angabe wird der aktuelle Zeitpunkt gesetzt.
    """
    quelle = bestaetigung if isinstance(bestaetigung, dict) else {}
    stand = _stand_jz(stand)
    zeilen: list = []
    for knoten in andockung if isinstance(andockung, (list, tuple)) else []:
        if not isinstance(knoten, dict):
            continue
        personen = []
        for person in knoten.get("personen") or []:
            if not isinstance(person, dict):
                continue
            kennung = _text(person.get("kennung"))
            name = quelle.get(kennung) if kennung else None
            name = name if isinstance(name, str) and name.strip() else None
            personen.append({
                "kennung": kennung,
                "bilder": _als_int(person.get("bilder")) or 0,
                "gesichter": _als_int(person.get("gesichter")) or 0,
                "bestaetigt": bool(name),
                "name": name,
            })
        zeilen.append({
            "art": ART_KNOTEN,
            "anlass_id": _text(knoten.get("anlass_id")),
            "kennung": _text(knoten.get("kennung")),
            "datum": knoten.get("datum"),
            "personen": personen,
            "quellen": {"personen": QUELLE_PERSONEN,
                        "anlass": QUELLE_ANLASS},
            "stand": stand,
        })
    return zeilen


def vorschlaege_dokument(personen, bestaetigung, stand=None) -> dict:
    """Das Vorschlags-Dokument fuer das Handy bauen — **rein**, ohne I/O.

    Das Dokument traegt Kopf (``art``, ``stand``, ``anzahl_personen``,
    ``anzahl_bestaetigt``, den ehrlichen ``hinweis``) und die Personen-Liste.
    ``anzahl_bestaetigt`` zaehlt nur **wirklich** bestaetigte Personen; der
    Hinweis erinnert daran, dass Vorschlaege Vorschlaege sind.
    """
    liste = [p for p in (personen if isinstance(personen, (list, tuple)) else [])
             if isinstance(p, dict)]
    return {
        "art": ART_VORSCHLAEGE,
        "stand": _stand_jz(stand),
        "anzahl_personen": len(liste),
        "anzahl_bestaetigt": sum(1 for p in liste if p.get("bestaetigt")),
        "hinweis": HINWEIS_VORSCHLAEGE,
        "personen": liste,
    }


# ── 8. Schreiben: atomar, nur ausserhalb des Repos ───────────────────────

def _zeile_text(zeile: dict) -> str:
    """Einen Knoten als eine JSONL-Zeile — ASCII, sortierte Schluessel."""
    return json.dumps(zeile, ensure_ascii=True, sort_keys=True)


def schreiben(pfad, inhalt) -> str:
    """Atomar schreiben — ``list`` als JSONL, ``dict`` als JSON.

    Erst vollstaendig in ``<ziel>.tmp`` im **Zielordner** schreiben, dann per
    ``os.replace`` ersetzen: es entsteht nie eine halbe Datei. Scheitert das
    Schreiben, wird ausschliesslich die **eigene** temp-Datei entfernt (die
    einzige Loeschung im Modul) — eine vorhandene alte Zieldatei bleibt
    unangetastet. Ein Ziel **im Repo** ergibt eine deutsche Klartextmeldung und
    ``SystemExit(2)`` (``personen_cluster.pruefe_ausserhalb_repo``); geschrieben
    wird dann nichts.

    Rueckgabe: der geschriebene Pfad.
    """
    ziel = pruefe_ausserhalb_repo(pfad)
    ordner = os.path.dirname(os.path.abspath(ziel))
    os.makedirs(ordner, exist_ok=True)
    temp_pfad = ziel + ".tmp"
    try:
        with open(temp_pfad, "w", encoding="utf-8", newline="\n") as datei:
            if isinstance(inhalt, dict):
                json.dump(inhalt, datei, ensure_ascii=True, sort_keys=True,
                          indent=1)
                datei.write("\n")
            elif isinstance(inhalt, (list, tuple)):
                for zeile in inhalt:
                    datei.write(_zeile_text(zeile) if isinstance(zeile, dict)
                                else str(zeile))
                    datei.write("\n")
            else:
                raise PersonenFehler(
                    "Zum Schreiben wird eine Liste (JSONL) oder ein "
                    "Woerterbuch (JSON) erwartet.")
        os.replace(temp_pfad, ziel)
    except Exception:
        if os.path.exists(temp_pfad):
            os.remove(temp_pfad)              # nur die eigene temp-Datei
        raise
    return ziel


# ── 9. Der Bericht als Klartext (deutsch) ────────────────────────────────

def bericht_bauen(zahlen) -> str:
    """Die Zahlen des Laufs als mehrzeiliger deutscher Klartext.

    Feste Zeilen (damit der Trockenlauf die Sollwerte Zeile fuer Zeile nennt):
    Vektorzeilen · Bilder-Arten · Personen (Gruppen, neu/wiederverwendet) ·
    Gruppengroessen · Personen ohne Anlass-Zuordnung · Anlaesse mit mindestens
    einer Person · Personen mit Kandidatennamen · verschiedene Kandidatennamen ·
    Kandidaten je Person · Namen bestaetigt/in der Ausgabe · der Hinweis.
    Fehlende Felder ergeben ``0`` bzw. ``-`` statt eines Absturzes. Es stehen
    hier **keine** Klarnamen (nur Zaehlungen).
    """
    z = zahlen if isinstance(zahlen, dict) else {}

    def ganz(name: str) -> int:
        wert = _als_int(z.get(name))
        return wert if wert is not None else 0

    def reihe(name: str) -> str:
        werte = z.get(name)
        if not isinstance(werte, (list, tuple)) or not werte:
            return "-"
        return ", ".join(_zahl(_als_int(wert) or 0) for wert in werte)

    roh_arten = z.get("je_art")
    arten = roh_arten if isinstance(roh_arten, dict) else {}
    arten_text = "   ".join(
        f"{art}: {_zahl(_als_int(arten.get(art)) or 0)}"
        for art in ART_REIHENFOLGE)
    personen = ganz("personen")
    mit_kandidaten = ganz("personen_mit_kandidaten")
    zeilen = [
        f"Personen-Andockung N27 Schritt 4 - Stand {_text(z.get('stand')) or 'unbekannt'}",
        f"Vektorzeilen gelesen: {_zahl(ganz('vektorzeilen'))}   "
        f"defekte Zeilen: {_zahl(ganz('defekte_zeilen'))}",
        f"Bilder-Arten: {arten_text}",
        f"Personen (Gruppen): {_zahl(personen)}   davon "
        f"{_zahl(ganz('kennungen_neu'))} neu, "
        f"{_zahl(ganz('kennungen_wiederverwendet'))} wiederverwendet",
        f"Gruppengroessen: {reihe('gruppen_groessen')}",
        f"Personen ohne Anlass-Zuordnung: {_zahl(ganz('personen_ohne_anlass'))}   "
        f"Bilder ohne Anlass-Zuordnung: {_zahl(ganz('ohne_anlass'))}",
        f"Anlaesse mit mindestens einer Person: {_zahl(ganz('anlaesse_mit_person'))}   "
        f"davon Personen: {_zahl(ganz('andockung_personen'))}",
        f"Personen mit Kandidatennamen: {_zahl(mit_kandidaten)} von "
        f"{_zahl(personen)}",
        f"verschiedene Kandidatennamen gesamt: {_zahl(ganz('namen_verschieden'))}",
        f"Kandidaten je Person (groesste zuerst): {reihe('kandidaten_groessen')}",
        f"Namen bestaetigt: {_zahl(ganz('namen_bestaetigt'))}   "
        f"Namen in der Ausgabe: {_zahl(ganz('namen_ausgabe'))}   "
        f"fremde Bestaetigungs-Schluessel: {_zahl(ganz('fremde_schluessel'))}",
        HINWEIS_VORSCHLAEGE,
    ]
    return "\n".join(zeilen)


def zahlen_bauen(lauf, personen_bilder, andockung, kandidaten,
                 bestaetigung, vorschlaege, zeilen, stand,
                 defekte_zeilen: int = 0, vektorzeilen: int = 0) -> dict:
    """Alle Berichtszahlen eines Laufs sammeln — **rein**, ohne I/O."""
    bericht = lauf.get("bericht") if isinstance(lauf, dict) else None
    bericht = bericht if isinstance(bericht, dict) else {}
    gruppen_groessen = bericht.get("gruppen_groessen")
    gruppen_groessen = sorted(
        (_als_int(wert) or 0 for wert in gruppen_groessen), reverse=True) \
        if isinstance(gruppen_groessen, (list, tuple)) else []
    kandidaten_groessen = sorted(
        (len(z) for z in kandidaten.values()
         if isinstance(z, dict)), reverse=True) if isinstance(kandidaten, dict) \
        else []
    namen_verschieden = len({name for zaehler in kandidaten.values()
                             if isinstance(zaehler, dict)
                             for name in zaehler}) \
        if isinstance(kandidaten, dict) else 0
    personen_mit = sum(1 for zaehler in kandidaten.values()
                       if isinstance(zaehler, dict) and zaehler) \
        if isinstance(kandidaten, dict) else 0
    andockung_personen = len(personen_bilder) \
        if isinstance(personen_bilder, dict) else 0
    namen_bestaetigt = sum(1 for v in vorschlaege
                           if isinstance(v, dict) and v.get("bestaetigt"))
    namen_ausgabe = sum(1 for zeile in zeilen
                        if isinstance(zeile, dict)
                        for person in zeile.get("personen") or []
                        if isinstance(person, dict) and person.get("name"))
    return {
        "stand": stand,
        "vektorzeilen": _als_int(vektorzeilen) or 0,
        "defekte_zeilen": int(defekte_zeilen) if _als_int(defekte_zeilen)
        is not None else 0,
        "je_art": dict(bericht.get("je_art") or {}),
        "gruppen": _als_int(bericht.get("gruppen")) or 0,
        "gruppen_groessen": gruppen_groessen,
        "kennungen_neu": _als_int(bericht.get("kennungen_neu")) or 0,
        "kennungen_wiederverwendet":
            _als_int(bericht.get("kennungen_wiederverwendet")) or 0,
        "personen": andockung_personen,
        "personen_ohne_anlass": getattr(andockung, "personen_ohne_anlass", 0),
        "ohne_anlass": getattr(andockung, "ohne_anlass", 0),
        "anlaesse_mit_person": len(andockung)
        if isinstance(andockung, (list, tuple)) else 0,
        "andockung_personen": andockung_personen,
        "personen_mit_kandidaten": personen_mit,
        "namen_verschieden": namen_verschieden,
        "kandidaten_groessen": kandidaten_groessen,
        "namen_bestaetigt": namen_bestaetigt,
        "namen_ausgabe": namen_ausgabe,
        "fremde_schluessel": getattr(bestaetigung, "fremde", 0),
    }


# ── 10. Kommandozeile ────────────────────────────────────────────────────

def main(argv=None) -> int:
    """Kommandozeile: lesen, rechnen, Bericht zeigen, nur mit ``--schreiben`` ablegen.

    Standard ist der **Trockenlauf**: gerechnet und berichtet wird, geschrieben
    wird **nichts** (``--trocken`` hat Vorrang vor ``--schreiben``). Geschrieben
    werden mit ``--schreiben`` **beide** Ausgabedateien (atomar, nur
    ausserhalb des Repos). Ein Ausgabeziel **im Repo** ergibt Exit 2 und keine
    Datei — im Trockenlauf wie beim Schreiben. Fehlende Eingaben ergeben eine
    deutsche Meldung auf ``stderr`` und Exit 2.
    """
    zerleger = argparse.ArgumentParser(
        description="Personen-Andockung N27 Schritt 4: verbindet je Anlass die "
                    "Gesichts-Cluster (Person_00x) mit den Chats des Anlasses "
                    "und schlaegt Namen vor. Namen erscheinen NUR nach "
                    "Bestaetigung. Kein Nachrichtentext, kein Netz, kein Bild, "
                    "kein Schreiben ins Repo.")
    zerleger.add_argument("--ereignisse", dest="ereignisse",
                          default=STANDARD_EREIGNISSE,
                          help="Ereignis-Knoten aus N27a (JSONL)")
    zerleger.add_argument("--vektoren", dest="vektoren", action="append",
                          default=None,
                          help="Vektordatei (JSONL, wiederholbar; Standard: "
                               "die zwei n9e-Dateien)")
    zerleger.add_argument("--alt-kennungen", dest="alt_kennungen",
                          default=STANDARD_ALT_KENNUNGEN,
                          help="Kennungs-Altbestand (JSON, darf fehlen)")
    zerleger.add_argument("--chat-andockung", dest="chat_andockung",
                          default=STANDARD_CHAT_ANDOCKUNG,
                          help="Chat-Andockung aus N27b (JSONL)")
    zerleger.add_argument("--bestaetigung", dest="bestaetigung",
                          default=STANDARD_BESTAETIGUNG,
                          help="Bestaetigungsdatei des Nutzers (JSON, darf fehlen)")
    zerleger.add_argument("--ausgabe-knoten", dest="ausgabe_knoten",
                          default=STANDARD_AUSGABE_KNOTEN,
                          help="Zieldatei der Andockung (JSONL, PFLICHT "
                               "ausserhalb des Repos)")
    zerleger.add_argument("--ausgabe-vorschlaege", dest="ausgabe_vorschlaege",
                          default=STANDARD_AUSGABE_VORSCHLAEGE,
                          help="Zieldatei der Vorschlaege (JSON, PFLICHT "
                               "ausserhalb des Repos)")
    zerleger.add_argument("--namen-je-person", dest="namen_je_person",
                          type=int, default=NAMEN_JE_PERSON,
                          help=f"Vorschlagsnamen je Person (Standard "
                               f"{NAMEN_JE_PERSON})")
    zerleger.add_argument("--stand", dest="stand", default=None,
                          help="fester Zeitstempel fuer 'stand' (Standard: "
                               "jetzt); macht zwei Laeufe byte-gleich")
    zerleger.add_argument("--trocken", dest="trocken", action="store_true",
                          help="nur rechnen und berichten (Standard)")
    zerleger.add_argument("--schreiben", dest="schreiben", action="store_true",
                          help="beide Ausgabedateien schreiben (atomar, nur "
                               "ausserhalb des Repos); --trocken hat Vorrang")
    args = zerleger.parse_args(argv)

    schreiben_gewuenscht = bool(args.schreiben) and not bool(args.trocken)
    grenze = args.namen_je_person if args.namen_je_person is not None else \
        NAMEN_JE_PERSON

    # Repo-Schutz zuerst (auch im Trockenlauf): ein Ziel im Repo ist Exit 2.
    pruefe_ausserhalb_repo(args.ausgabe_knoten)
    pruefe_ausserhalb_repo(args.ausgabe_vorschlaege)

    try:
        if grenze < 1:
            raise PersonenFehler("Die Zahl der Namen je Person muss >= 1 sein.")
        vektorpfade = args.vektoren if args.vektoren else list(STANDARD_VEKTOREN)
        eingelesen = vektoren_lesen(vektorpfade)
        ereignisse = ereignisse_lesen(args.ereignisse)
        index = ereignis_index(ereignisse)
        altbestand = _personen_cluster.altbestand_lesen_datei(args.alt_kennungen)
        chat_knoten = _chat_knoten_lesen(args.chat_andockung)
        bestaetigung = bestaetigung_lesen(args.bestaetigung)

        lauf = _personen_cluster.lauf_rechnen(eingelesen["zeilen"],
                                              altbestand=altbestand)
        personen_bilder = personen_je_bild(lauf)
        andockung = andocken(personen_bilder, index)
        kandidaten = kandidaten_je_person(andockung, chat_knoten)
        vorschlaege = vorschlaege_bauen(andockung, kandidaten, grenze)
        vorschlaege = bestaetigung_anwenden(vorschlaege, bestaetigung)
        stand = _stand_jz(args.stand)
        zeilen = knotenzeilen_bauen(andockung, bestaetigung, stand)
        dokument = vorschlaege_dokument(vorschlaege, bestaetigung, stand)
        zahlen = zahlen_bauen(
            lauf, personen_bilder, andockung, kandidaten, bestaetigung,
            vorschlaege, zeilen, stand,
            defekte_zeilen=(eingelesen["defekt"]
                            + getattr(ereignisse, "defekt", 0)
                            + getattr(chat_knoten, "defekt", 0)),
            vektorzeilen=len(eingelesen["zeilen"]))
    except PersonenFehler as problem:
        print(f"Fehler: {problem}", file=sys.stderr)
        return 2

    print("Personen-Andockung N27 Schritt 4 - "
          + ("SCHREIBEN" if schreiben_gewuenscht
             else "TROCKENLAUF (es wird nichts geschrieben)"))
    print(f"Ereignisse: {args.ereignisse}")
    print(f"Vektoren: {', '.join(str(p) for p in vektorpfade)}")
    print(f"Chat-Andockung: {args.chat_andockung}")
    print(f"Bestaetigung: {args.bestaetigung}"
          f" ({'vorhanden' if bestaetigung else 'leer/fehlt'})")
    print(bericht_bauen(zahlen))
    print(f"Geplant: {_zahl(len(zeilen))} Andockungszeilen, "
          f"{_zahl(dokument['anzahl_personen'])} Personen-Vorschlaege "
          f"(davon bestaetigt: {_zahl(dokument['anzahl_bestaetigt'])})")

    if not schreiben_gewuenscht:
        print(f"Trockenlauf: {args.ausgabe_knoten} und "
              f"{args.ausgabe_vorschlaege} wurden NICHT geschrieben.")
        return 0

    try:
        ziel_knoten = schreiben(args.ausgabe_knoten, zeilen)
        ziel_vorschlaege = schreiben(args.ausgabe_vorschlaege, dokument)
    except PersonenFehler as problem:
        print(f"Fehler: {problem}", file=sys.stderr)
        return 2
    print(f"Personen-Andockung geschrieben: {ziel_knoten}")
    print(f"Personen-Vorschlaege geschrieben: {ziel_vorschlaege}")
    return 0


# Zweiter Name derselben Kommandozeile (das Nachbarmodul heisst ``main``).
haupt = main


if __name__ == "__main__":
    raise SystemExit(main())
