"""Beziehungs-Ableitung „wer war mit wem wo" (N27 Schritt 5 von 5, 29.09.2026).

Warum dieses Werkzeug:
  Schritt 1 (``ereignisse_bauen.py``) hat je Anlass einen **Ereignis-Knoten**
  gelegt, Schritt 2 die Chats angebunden, Schritt 3 den Kalender, Schritt 4 die
  **Personen** (``personen_andocken.py``). Schritt 5 zieht daraus die
  **belegbaren Aussagen** der Form „wer war mit wem wo": je Anlass die
  Personen-Paare auf denselben Fotos, je Chat die Paare der benannten
  Kontakte und beide Quellen nebeneinander. Jede Aussage traegt **Datum,
  Belegzahlen und Quellenangabe**.

Die **Kernregel** dieses Schritts (nicht verhandelbar):
  Abgeleitet wird **nur**, was in den vorhandenen Verknuepfungsdaten steht —
  **nichts wird geraten**. Das Werkzeug **nament keine Gesichtskennung**: eine
  Personen-Kennung ``Person_00x`` traegt einen ``name`` **nur**, wenn er in
  der Bestaetigungsdatei ``personen_bestaetigt.json`` steht (die der Nutzer
  pflegt); sonst bleibt ``name: null``. Ein Name aus einer Kandidatenliste
  (Vorschlagsdatei) wird **nie** uebernommen — unbestätigte Kennungen sind
  **keine** Namen. Chat-Kontakte tragen dagegen ihren Namen, weil dieser
  bereits in ``chat_andockung.jsonl`` aus der Kontaktzuordnung des Nutzers
  steht (nicht geraten, sondern vorhanden).

Ehrliche Abgrenzung (steht als ``hinweis`` in jeder Aussagezeile):
  * „im selben Chat" ist **Mitgliedschaft** — **kein** Beleg fuer koerperliche
    Anwesenheit.
  * „auf Fotos am selben Anlass" ist **Bildbeleg** — **kein** Beleg fuer eine
    Beziehung.
  * Beides nebeneinander ist **kein** Beweis fuer irgendetwas; es sind zwei
    Belege, mehr nicht.

Was dieses Werkzeug bewusst NICHT tut:
  * **Kein Nachrichtentext.** Aus ``chat_andockung.jsonl`` werden nur
    ``anlass_id``, ``datum``, je Chat ``chat_name``, ``art`` und ``nachrichten``
    sowie je Beteiligtem ``name`` und ``nachrichten`` gelesen: **nie** der
    Nachrichteninhalt, **nie** eine Nachrichten-Kennung, **nie** eine
    Nummern-Maske.
  * **Keine Rufnummern.** Die Masken der Beteiligten werden nicht gelesen; die
    Ausgabe enthaelt keinen Maskentext. Ein Kontaktname, der wie eine Maske
    aussieht (Sternchen oder nur Ziffern), zaehlt **nicht** als Kontakt.
  * **Kein Bild, kein Netz.** Kein Bildwerkzeug, kein Netz-Baustein, kein
    Cloud-Aufruf. Es wird keine Bilddatei geoeffnet; gelesen werden
    ausschliesslich lokale JSON/JSONL-Dateien.
  * **Kein Schreiben ins Repo.** Ein Ausgabeziel im Repo ergibt eine deutsche
    Klartextmeldung auf ``stderr`` und **Exit 2** — geschrieben wird dann
    nichts, auch im Trockenlauf nicht.
  * **Keine Loeschung** ausser der **eigenen** temp-Datei beim atomaren
    Schreiben; es gibt keine Loeschfunktion, auch nicht „zur Sicherheit", und
    keine Verschiebe-Funktion.
  * **Kein Schreiben ohne ``--schreiben``.** Der Standard ist der Trockenlauf.

Eingaben (alle **nur lesend**, alle per CLI ueberschreibbar, alle ausserhalb
des Repos):

  ``--ereignisse``        ``~/foto_sortierung/ereignisse.jsonl`` (N27a)
  ``--andockung``         ``~/foto_sortierung/personen_andockung.jsonl`` (N27d)
  ``--chat-andockung``    ``~/foto_sortierung/chat_andockung.jsonl`` (N27b)
  ``--bestaetigung``      ``~/foto_sortierung/personen_bestaetigt.json``
                          (**darf fehlen** — dann bleibt jede Kennung unbenannt)

Ausgaben (nur mit ``--schreiben``, sonst Trockenlauf):

  ``--ausgabe``            ``~/foto_sortierung/beziehungen.jsonl`` (JSONL)
  ``--ausgabe-uebersicht`` ``~/foto_sortierung/beziehungen.json``  (JSON)

Drei Aussage-Arten (getrennt gehalten, nie vermischt):

  1. ``fotos``             je Anlass mit **>= 2** verschiedenen
                           Personen-Kennungen: je Kennungs-Paar **eine**
                           Aussage.
  2. ``gemeinsam_im_chat`` je Chat-Andockung (ein Chat an einem Tag) mit
                           **>= 2** verschiedenen **benannten** Kontakten:
                           je Namens-Paar **eine** Aussage.
  3. ``fotos_und_chat``    je Anlass mit **>= 1** Foto-Person **und**
                           **>= 1** benanntem Chat-Kontakt: je Paar
                           (Person x Kontakt) **eine** Aussage.

Ausgabeschema ``beziehungen.jsonl`` (eingefroren, ``sort_keys=True``):::

    {"anlass_id": "…", "art": "beziehung",
     "beleg": {"bilder": 4, "gesichter": 4},
     "datum": "2014-03-30", "ereignis_kennung": "E-…",
     "hinweis": "Bildbeleg: …", "kategorie": "…",
     "personen": [{"bestaetigt": false, "bilder": 3, "gesichter": 4,
                   "kennung": "Person_001", "name": null}, …],
     "quellen": {"andockung": "personen_andockung.jsonl:3"},
     "stand": "…", "thema": "…", "unterart": "fotos",
     "ziel_ordner": "Agent/Fotos/…"}

  Je ``unterart`` traegt ``beleg`` die passenden Zahlen:
  ``fotos`` = Summen aus ``bilder``/``gesichter`` beider Personen;
  ``gemeinsam_im_chat`` = ``nachrichten`` beider Beteiligter, dazu
  ``chat_name`` und ``chat_art``; ``fotos_und_chat`` = beides zusammen.

Ausgabeschema ``beziehungen.json`` (Uebersicht):::

    {"art": "beziehungen", "stand": "…",
     "anzahl": {"fotos": 23, "gemeinsam_im_chat": 14902, "fotos_und_chat": 126},
     "anzahl_personen_kennungen": 12, "anzahl_namen_bestaetigt": 0,
     "anzahl_kontakte": 342, "datum_von": "…", "datum_bis": "…",
     "quellen": {"andockung": "…", "chat": "…", "ereignisse": "…",
                 "bestaetigung": "…"},
     "hinweis": "…"}

Aufruf (Kommandozeile):::

    python tools/foto_sortierung/beziehungen_ableiten.py --trocken
    python tools/foto_sortierung/beziehungen_ableiten.py --datum 2014-03-30
    python tools/foto_sortierung/beziehungen_ableiten.py --ausgabe C:/tmp/b.jsonl \
        --ausgabe-uebersicht C:/tmp/b.json --schreiben --stand 2026-09-29T03:00:00+02:00

Als Modul (Tests, spaetere Schritte): ``main(argv=[...])`` (Zweitname ``haupt``)
sowie die oeffentlichen Funktionen ``ereignisse_lesen``, ``ereignis_index``,
``personen_andockung_lesen``, ``chat_andockung_lesen``, ``kontaktnamen``,
``fotos_aussagen``, ``chat_aussagen``, ``fotos_und_chat_aussagen``,
``beziehungen_bauen``, ``aussagen_filtern``, ``uebersicht_bauen``,
``schreiben``, ``bericht_bauen``.
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
# Der Bestaetigungs-Leser und der Fehlertyp kommen woertlich aus dem
# Nachbarmodul ``personen_andocken`` (N27 Schritt 4). Weil dieses Modul in
# Tests ueber den Dateipfad geladen wird (dort steht das Werkzeugverzeichnis
# nicht auf ``sys.path``), gibt es einen Rueckfall-Lader auf dieselbe Datei.
try:
    import personen_andocken as _personen_andocken
except ImportError:                       # pragma: no cover — Test-Ladeweg
    _spez = importlib.util.spec_from_file_location(
        "personen_andocken", os.path.join(HIER, "personen_andocken.py"))
    if _spez is None or _spez.loader is None:      # pragma: no cover
        raise ImportError(
            "personen_andocken.py liegt nicht neben beziehungen_ableiten.py.")
    _personen_andocken = importlib.util.module_from_spec(_spez)
    _spez.loader.exec_module(_personen_andocken)

bestaetigung_lesen = _personen_andocken.bestaetigung_lesen
PersonenFehler = _personen_andocken.PersonenFehler

# ── Vorgabepfade: ausserhalb des Repos — dort liegen private Kennungen ────
STANDARD_BASIS = os.path.join(os.path.expanduser("~"), "foto_sortierung")
STANDARD_EREIGNISSE = os.path.join(STANDARD_BASIS, "ereignisse.jsonl")
STANDARD_ANDOCKUNG = os.path.join(STANDARD_BASIS, "personen_andockung.jsonl")
STANDARD_CHAT_ANDOCKUNG = os.path.join(STANDARD_BASIS, "chat_andockung.jsonl")
STANDARD_BESTAETIGUNG = os.path.join(STANDARD_BASIS, "personen_bestaetigt.json")
STANDARD_AUSGABE = os.path.join(STANDARD_BASIS, "beziehungen.jsonl")
STANDARD_AUSGABE_UEBERSICHT = os.path.join(STANDARD_BASIS, "beziehungen.json")

# Die Aussage-Art (steht so im ``art``-Feld jeder Zeile).
ART_AUSSAGE = "beziehung"
ART_UEBERSICHT = "beziehungen"

# Die drei Unterarten — fester Name, feste Reihenfolge.
UNTERART_FOTOS = "fotos"
UNTERART_CHAT = "gemeinsam_im_chat"
UNTERART_FOTOS_UND_CHAT = "fotos_und_chat"
UNTERART_REIHENFOLGE = (UNTERART_FOTOS, UNTERART_CHAT, UNTERART_FOTOS_UND_CHAT)
UNTERART_RANG = {name: stelle for stelle, name in enumerate(UNTERART_REIHENFOLGE)}

# Der Kontaktname, der keine Person benennt: er zaehlt nicht als Kontakt.
NAME_UNBEKANNT = "unbekannt"

# Die Ehrlichen Hinweise (woertlich je Unterart).
HINWEIS_FOTOS = ("Bildbeleg: dasselbe Anlass-Foto zeigt zwei Personen-Kennungen "
                 "- das belegt weder eine Beziehung noch gemeinsame "
                 "Anwesenheit; die Kennungen sind keine Namen.")
HINWEIS_CHAT = ("Mitgliedschaft: derselbe Chat am selben Tag belegt keine "
                "koerperliche Anwesenheit und keine Beziehung.")
HINWEIS_FOTOS_UND_CHAT = ("Bildbeleg und Chat-Mitgliedschaft nebeneinander: "
                          "weder die Fotos noch der Chat belegen eine Beziehung "
                          "oder Anwesenheit.")
HINWEIS_UEBERSICHT = ("Abgeleitet aus vorhandenen Verknuepfungsdaten; nichts "
                      "geraten. Unbestaetigte Kennungen sind keine Namen und "
                      "werden nie aus Kandidatenlisten uebernommen. Chat-"
                      "Mitgliedschaft belegt keine Anwesenheit, Foto-Naehe "
                      "keine Beziehung.")
HINWEIS_JE_UNTERART = {
    UNTERART_FOTOS: HINWEIS_FOTOS,
    UNTERART_CHAT: HINWEIS_CHAT,
    UNTERART_FOTOS_UND_CHAT: HINWEIS_FOTOS_UND_CHAT,
}

# Die Schluessel des eingefrorenen Aussage-Schemas (bindend fuer Folgeschritte).
AUSSAGE_SCHLUESSEL = ("anlass_id", "art", "beleg", "datum", "ereignis_kennung",
                      "hinweis", "kategorie", "personen", "quellen", "stand",
                      "thema", "unterart", "ziel_ordner")
AUSSAGE_PERSON_SCHLUESSEL = ("bestaetigt", "bilder", "gesichter", "kennung",
                             "name")
UEBERSICHT_SCHLUESSEL = ("anzahl", "anzahl_kontakte", "anzahl_namen_bestaetigt",
                         "anzahl_personen_kennungen", "art", "datum_bis",
                         "datum_von", "hinweis", "quellen", "stand")

# Kennungs-Muster: ``Person_001`` … (drei Stellen) — nur solche Schluessel
# zaehlen in der Bestaetigungsdatei als Person (wie im Nachbarmodul).
KENNUNG_MUSTER = r"^Person_\d{3}$"


# ── Kleine Helfer (tolerant lesen, nie raten) ─────────────────────────────

def _text(wert) -> str:
    """Ein Feld als Text lesen — Nicht-Text und ``None`` werden zu ``\"\"``."""
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
    """Ob ein Text eine Personen-Kennung ``Person_001`` ist (genau drei Ziffern)."""
    text = _text(wert)
    if not text.startswith("Person_"):
        return False
    rest = text[len("Person_"):]
    return len(rest) == 3 and rest.isdigit()


def _stand_jz(stand=None) -> str:
    """Den Zeitstempel lesen — ohne Angabe der aktuelle (mit Zeitzone)."""
    text = _text(stand)
    if text:
        return text
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


# Lesbares Datum = echte Kalenderangabe in der Form JJJJ-MM-TT (ASCII).
DATUM_MUSTER = r"^\d{4}-\d{2}-\d{2}$"


def _datum_lesen(wert):
    """Ein Datum als ``JJJJ-MM-TT`` lesen — sonst ``None`` (nichts geraten)."""
    text = _text(wert)
    if len(text) != 10 or text[4] != "-" or text[7] != "-":
        return None
    try:
        datetime.date.fromisoformat(text)
    except ValueError:
        return None
    return text


def _ist_maske(name: str) -> bool:
    """Ob ein Text wie eine Nummern-Maske aussieht (Sternchen oder nur Ziffern)."""
    if "*" in name or "#" in name:
        return True
    return name.isdigit()


# ── Zaehl-Container: eine Liste/ein Dict, das seine Zahlen mitbringt ──────

class ZaehlListe(list):
    """Eine Liste mit Zusatzzahlen (``defekt``, ``zeilennummern`` …) als Attribute."""

    def __init__(self, werte=(), **zahlen):
        super().__init__(werte)
        for name, wert in zahlen.items():
            setattr(self, name, wert)


class ZaehlDict(dict):
    """Ein Dict mit Zusatzzahlen (``defekt``, ``doppelte`` …) als Attribute."""

    def __init__(self, werte=(), **zahlen):
        super().__init__(werte)
        for name, wert in zahlen.items():
            setattr(self, name, wert)


# ── 1. Lesen (lokal, nur lesend, kein Netz) ───────────────────────────────

def _jsonl_lesen(pfad, was: str) -> ZaehlListe:
    """Eine JSONL-Datei zeilenweise lesen — nur JSON-Objekte, Zeile zaehlt.

    Jede brauchbare Zeile kommt als Paar ``(Zeilennummer, Datensatz)`` in die
    Liste (die Nummer wandert spaeter in die ``quellen`` der Aussage). Eine
    leere Zeile, kein JSON oder ein JSON-Wert ohne Objekt zaehlt in
    ``defekt`` und bricht nichts ab. Eine **fehlende** Datei ist ein
    ``PersonenFehler`` mit Klartextmeldung (nichts wird geraten).
    """
    pfad = _text(pfad)
    if not pfad:
        raise PersonenFehler(f"Kein Pfad fuer {was} angegeben.")
    if not os.path.isfile(pfad):
        raise PersonenFehler(f"{was} nicht gefunden: {pfad}")
    eintraege: list = []
    defekt = 0
    try:
        with open(pfad, encoding="utf-8") as datei:
            for nummer, zeile in enumerate(datei, 1):
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
                eintraege.append((nummer, daten))
    except OSError as problem:
        raise PersonenFehler(
            f"{was} nicht lesbar ({problem.__class__.__name__}): {pfad}") \
            from None
    return ZaehlListe(eintraege, defekt=defekt, pfad=pfad,
                      dateiname=os.path.basename(pfad))


def personen_andockung_lesen(pfad) -> ZaehlListe:
    """Die Personen-Andockung (N27d) lesen — nur ``anlass_id``/``datum``/``personen``.

    Je Zeile kommt ein Paar ``(Zeilennummer, Datensatz)``. Gelesen werden
    ausschliesslich ``anlass_id``, ``datum`` und je Person ``kennung``,
    ``bilder``, ``gesichter``; defekte Zeilen zaehlen (``ergebnis.defekt``),
    nichts bricht ab. Eine fehlende Datei ist ein ``PersonenFehler``.
    """
    return _jsonl_lesen(pfad, "Personen-Andockung")


def chat_andockung_lesen(pfad) -> ZaehlListe:
    """Die Chat-Andockung (N27b) lesen — ohne jeden Nachrichtentext.

    Je Zeile kommt ein Paar ``(Zeilennummer, Datensatz)``. Gelesen werden nur
    ``anlass_id``, ``datum`` und die ``chats``; aus einem Chat nur ``chat_name``,
    ``art``, ``nachrichten`` und die ``beteiligte`` (je ``name`` und
    ``nachrichten``). **Nie** ein Nachrichtentext, **nie** eine
    Nachrichten-Kennung, **nie** eine Nummern-Maske. Defekte Zeilen zaehlen
    (``ergebnis.defekt``), nichts bricht ab; fehlende Datei ⇒ ``PersonenFehler``.
    """
    return _jsonl_lesen(pfad, "Chat-Andockung")


def ereignisse_lesen(pfad) -> ZaehlDict:
    """Die Ereignis-Knoten (N27a) lesen — Index ``anlass_id -> Kopfdaten``.

    Zurueck kommt ein Dict ``anlass_id -> {"kennung", "thema", "kategorie",
    "ziel_ordner", "datum"}``; weitere Felder werden nicht gebraucht. Zeilen
    ohne ``anlass_id`` zaehlen in ``defekt`` (``ergebnis.defekt``). Eine
    fehlende Datei ist ein ``PersonenFehler``.
    """
    gelesen = _jsonl_lesen(pfad, "Ereignisse")
    index: dict = {}
    doppelt = 0
    ohne_anlass = 0
    for _nummer, knoten in gelesen:
        anlass_id = _text(knoten.get("anlass_id"))
        if not anlass_id:
            ohne_anlass += 1
            continue
        if anlass_id in index:
            doppelt += 1
            continue                        # erste Zuordnung gewinnt
        index[anlass_id] = {
            "kennung": _text(knoten.get("kennung")),
            "thema": _text(knoten.get("thema")),
            "kategorie": _text(knoten.get("kategorie")),
            "ziel_ordner": _text(knoten.get("ziel_ordner")),
            "datum": _datum_lesen(knoten.get("datum")),
        }
    return ZaehlDict(index, defekt=(getattr(gelesen, "defekt", 0) + ohne_anlass),
                     doppelte=doppelt, pfad=getattr(gelesen, "pfad", ""))


def ereignis_index(ereignisse) -> dict:
    """Aus einem ``Anlass -> Knoten``-Bestand den Index bauen (durchreichen).

    Nimmt entweder das Ergebnis von ``ereignisse_lesen`` (ein Dict) oder eine
    Liste von Knoten und liefert ``anlass_id -> Kopfdaten``. Die **erste**
    Zuordnung gewinnt; nichts wird ueberschrieben.
    """
    if isinstance(ereignisse, dict):
        return dict(ereignisse)
    index: dict = {}
    for knoten in ereignisse if isinstance(ereignisse, (list, tuple)) else []:
        if not isinstance(knoten, dict):
            continue
        anlass_id = _text(knoten.get("anlass_id"))
        if anlass_id and anlass_id not in index:
            index[anlass_id] = {
                "kennung": _text(knoten.get("kennung")),
                "thema": _text(knoten.get("thema")),
                "kategorie": _text(knoten.get("kategorie")),
                "ziel_ordner": _text(knoten.get("ziel_ordner")),
                "datum": _datum_lesen(knoten.get("datum")),
            }
    return index


# ── 2. Personen und Kontakte einsammeln ───────────────────────────────────

def _personen_eintraege(knoten, bestaetigung) -> list:
    """Die Personen eines Andockungs-Knotens als Aussage-Eintraege bauen.

    Je Person ein Dict mit ``kennung``, ``name`` (**nur** bestaetigt, sonst
    ``null`` — die Quelle ist allein die Bestaetigungsdatei), ``bestaetigt``,
    ``bilder`` und ``gesichter``. Doppelte Kennungen werden zusammengefasst;
    Kennungen ohne Text fallen weg. Die Liste ist nach ``kennung`` sortiert.
    """
    quelle = bestaetigung if isinstance(bestaetigung, dict) else {}
    gesammelt: dict = {}
    for person in knoten.get("personen") or []:
        if not isinstance(person, dict):
            continue
        kennung = _text(person.get("kennung"))
        if not kennung:
            continue
        eintrag = gesammelt.get(kennung)
        if eintrag is None:
            name = quelle.get(kennung)
            name = name if isinstance(name, str) and name.strip() else None
            eintrag = {
                "kennung": kennung,
                "name": name,
                "bestaetigt": bool(name),
                "bilder": 0,
                "gesichter": 0,
            }
            gesammelt[kennung] = eintrag
        eintrag["bilder"] += _als_int(person.get("bilder")) or 0
        eintrag["gesichter"] += _als_int(person.get("gesichter")) or 0
    return [gesammelt[kennung] for kennung in sorted(gesammelt)]


def kontaktnamen(chat) -> ZaehlDict:
    """Die **benannten** Kontakte eines Chats sammeln — ``name -> nachrichten``.

    Gelesen werden je Beteiligtem nur ``name`` und ``nachrichten``: **nie**
    eine Nummern-Maske, **nie** ein Nachrichtentext. ``"unbekannt"``, leere
    Namen und Namen, die wie eine Maske aussehen, zaehlen **nicht** als
    Kontakt; sie werden gezaehlt (``ergebnis.uebersprungen``) statt geraten.
    Doppelte Namen innerhalb eines Chats werden zusammengefasst
    (``ergebnis.doppelte``).
    """
    ergebnis: dict = {}
    uebersprungen = 0
    doppelte = 0
    for beteiligter in chat.get("beteiligte") or []:
        if not isinstance(beteiligter, dict):
            uebersprungen += 1
            continue
        name = _text(beteiligter.get("name"))
        if not name or name.lower() == NAME_UNBEKANNT or _ist_maske(name):
            uebersprungen += 1
            continue
        anzahl = _als_int(beteiligter.get("nachrichten"))
        anzahl = anzahl if anzahl is not None else 0
        if name in ergebnis:
            doppelte += 1
            ergebnis[name] += anzahl            # dasselbe Paar bleibt ein Paar
            continue
        ergebnis[name] = anzahl
    return ZaehlDict(ergebnis, uebersprungen=uebersprungen, doppelte=doppelte)


def _kontakt_eintrag(name: str, nachrichten: int) -> dict:
    """Einen Chat-Kontakt als Aussage-Eintrag bauen (ohne ``kennung``).

    Der Name steht in ``chat_andockung.jsonl`` (Kontaktzuordnung des Nutzers),
    er wird **nicht** geraten; deshalb traegt der Eintrag ``kennung: null`` und
    ``bestaetigt: true`` — im Unterschied zur Gesichtskennung, deren Name nur
    aus der Bestaetigungsdatei kommen darf.
    """
    return {"kennung": None, "name": name, "bestaetigt": True,
            "bilder": 0, "gesichter": 0, "_nachrichten": nachrichten}


def _kontakt_eintrag_oeffentlich(eintrag: dict) -> dict:
    """Den internen ``_nachrichten``-Wert aus einem Kontakt-Eintrag entfernen."""
    return {name: eintrag[name] for name in AUSSAGE_PERSON_SCHLUESSEL}


def _ereignis_felder(anlass_id: str, index: dict) -> dict:
    """``kennung``/``thema``/``kategorie``/``ziel_ordner`` aus dem Index holen."""
    knoten = index.get(anlass_id) if isinstance(index, dict) else None
    knoten = knoten if isinstance(knoten, dict) else {}
    return {
        "ereignis_kennung": _text(knoten.get("kennung")) or None,
        "thema": _text(knoten.get("thema")),
        "kategorie": _text(knoten.get("kategorie")),
        "ziel_ordner": _text(knoten.get("ziel_ordner")) or None,
    }


def _aussage(unterart: str, anlass_id: str, datum, personen: list, beleg: dict,
             quellen: dict, index: dict, stand: str) -> dict:
    """Eine Aussagezeile im eingefrorenen Schema bauen — **rein**, ohne I/O."""
    felder = _ereignis_felder(anlass_id, index)
    return {
        "art": ART_AUSSAGE,
        "unterart": unterart,
        "datum": _datum_lesen(datum),
        "anlass_id": anlass_id,
        "ereignis_kennung": felder["ereignis_kennung"],
        "thema": felder["thema"],
        "kategorie": felder["kategorie"],
        "ziel_ordner": felder["ziel_ordner"],
        "personen": personen,
        "beleg": beleg,
        "quellen": quellen,
        "hinweis": HINWEIS_JE_UNTERART.get(unterart, HINWEIS_UEBERSICHT),
        "stand": stand,
    }


# ── 3. Die drei Aussage-Arten (rein, ohne I/O) ────────────────────────────

def fotos_aussagen(andockung, ereignis_index_=None, bestaetigung=None,
                   stand=None) -> ZaehlListe:
    """Unterart ``fotos``: je Anlass ein Paar Personen, die zusammen auf Fotos sind.

    Fuer jeden Anlass mit **mindestens zwei** verschiedenen Personen-Kennungen
    entsteht je Kennungs-Paar **eine** Aussage. Der Beleg sind die **Summen**
    aus ``bilder`` und ``gesichter`` beider Personen. Ohne Bestaetigung bleibt
    ``name: null``. Die Eingaben werden nicht veraendert.

    ``andockung`` ist das Ergebnis von ``personen_andockung_lesen`` (Paare aus
    Zeilennummer und Knoten) oder eine einfache Liste von Knoten.
    """
    stand = _stand_jz(stand)
    index = ereignis_index(ereignis_index_)
    zeilen: list = []
    for nummer, knoten in _paare(andockung):
        anlass_id = _text(knoten.get("anlass_id"))
        personen = _personen_eintraege(knoten, bestaetigung)
        if len(personen) < 2:
            continue
        for links in range(len(personen)):
            for rechts in range(links + 1, len(personen)):
                a = personen[links]
                b = personen[rechts]
                beleg = {"bilder": a["bilder"] + b["bilder"],
                         "gesichter": a["gesichter"] + b["gesichter"]}
                zeilen.append(_aussage(
                    UNTERART_FOTOS, anlass_id, knoten.get("datum"),
                    [dict(a), dict(b)], beleg,
                    {"andockung": _quellen_zeile(andockung, nummer)}, index,
                    stand))
    return ZaehlListe(zeilen)


def chat_aussagen(chat_andockung, ereignis_index_=None, stand=None) -> ZaehlListe:
    """Unterart ``gemeinsam_im_chat``: je Chat ein Paar benannter Kontakte.

    Fuer jede Chat-Andockung (ein Chat an einem Tag) mit **mindestens zwei**
    verschiedenen **benannten** Kontakten entsteht je Namens-Paar **eine**
    Aussage. Der Beleg sind ``nachrichten`` beider Beteiligter sowie
    ``chat_name`` und ``art`` des Chats. Kontakte tragen keine
    Personen-Kennung (``kennung: null``); ``"unbekannt"`` und leere Namen
    zaehlen nicht als Kontakt.
    """
    stand = _stand_jz(stand)
    index = ereignis_index(ereignis_index_)
    zeilen: list = []
    for nummer, knoten in _paare(chat_andockung):
        anlass_id = _text(knoten.get("anlass_id"))
        for chat in knoten.get("chats") or []:
            if not isinstance(chat, dict):
                continue
            namen = kontaktnamen(chat)
            if len(namen) < 2:
                continue
            geordnet = sorted(namen)
            for links in range(len(geordnet)):
                for rechts in range(links + 1, len(geordnet)):
                    a = _kontakt_eintrag(geordnet[links], namen[geordnet[links]])
                    b = _kontakt_eintrag(geordnet[rechts], namen[geordnet[rechts]])
                    beleg = {
                        "chat_name": _text(chat.get("chat_name")),
                        "chat_art": _text(chat.get("art")) or None,
                        "nachrichten": a["_nachrichten"] + b["_nachrichten"],
                    }
                    zeilen.append(_aussage(
                        UNTERART_CHAT, anlass_id, knoten.get("datum"),
                        [_kontakt_eintrag_oeffentlich(a),
                         _kontakt_eintrag_oeffentlich(b)], beleg,
                        {"chat": _quellen_zeile(chat_andockung, nummer)},
                        index, stand))
    return ZaehlListe(zeilen)


def fotos_und_chat_aussagen(andockung, chat_andockung, ereignis_index_=None,
                            bestaetigung=None, stand=None) -> ZaehlListe:
    """Unterart ``fotos_und_chat``: je Anlass Person x benannter Chat-Kontakt.

    Fuer jeden Anlass mit **mindestens einer** Foto-Person **und**
    **mindestens einem** benannten Chat-Kontakt entsteht je Paar **eine**
    Aussage. Der Beleg traegt die Zahlen aus **beiden** Quellen
    (``bilder``/``gesichter`` der Person, ``nachrichten`` des Kontakts) und je
    die Herkunftsdatei in ``quellen``.
    """
    stand = _stand_jz(stand)
    index = ereignis_index(ereignis_index_)

    # Personen je Anlass (nur diese Unterart braucht einen Kreuzbezug).
    personen_je_anlass: dict = {}
    quellen_person: dict = {}
    daten_person: dict = {}
    for nummer, knoten in _paare(andockung):
        anlass_id = _text(knoten.get("anlass_id"))
        if not anlass_id or anlass_id in personen_je_anlass:
            continue
        personen_je_anlass[anlass_id] = _personen_eintraege(knoten, bestaetigung)
        quellen_person[anlass_id] = _quellen_zeile(andockung, nummer)
        daten_person[anlass_id] = knoten.get("datum")

    # Kontakte je Anlass (über alle Chats des Anlasses zusammengefuehrt).
    kontakte_je_anlass: dict = {}
    quellen_chat: dict = {}
    daten_chat: dict = {}
    chat_info: dict = {}
    for nummer, knoten in _paare(chat_andockung):
        anlass_id = _text(knoten.get("anlass_id"))
        if not anlass_id:
            continue
        quellen_chat.setdefault(anlass_id, _quellen_zeile(chat_andockung, nummer))
        daten_chat.setdefault(anlass_id, knoten.get("datum"))
        sammlung = kontakte_je_anlass.setdefault(anlass_id, {})
        for chat in knoten.get("chats") or []:
            if not isinstance(chat, dict):
                continue
            for name, anzahl in kontaktnamen(chat).items():
                if name in sammlung:
                    sammlung[name]["_nachrichten"] += anzahl
                    continue
                eintrag = _kontakt_eintrag(name, anzahl)
                sammlung[name] = eintrag
                chat_info.setdefault(
                    anlass_id, {"chat_name": _text(chat.get("chat_name")),
                                "chat_art": _text(chat.get("art")) or None})

    zeilen: list = []
    for anlass_id in sorted(kontakte_je_anlass):
        personen = personen_je_anlass.get(anlass_id) or []
        kontakte = kontakte_je_anlass[anlass_id]
        if not personen or not kontakte:
            continue
        info = chat_info.get(anlass_id) or {"chat_name": "", "chat_art": None}
        for person in personen:
            for name in sorted(kontakte):
                kontakt = kontakte[name]
                beleg = {
                    "bilder": person["bilder"],
                    "gesichter": person["gesichter"],
                    "nachrichten": kontakt["_nachrichten"],
                    "chat_name": info["chat_name"],
                    "chat_art": info["chat_art"],
                }
                zeilen.append(_aussage(
                    UNTERART_FOTOS_UND_CHAT, anlass_id,
                    daten_person.get(anlass_id) or daten_chat.get(anlass_id),
                    [dict(person), _kontakt_eintrag_oeffentlich(kontakt)], beleg,
                    {"andockung": quellen_person.get(anlass_id, ""),
                     "chat": quellen_chat.get(anlass_id, "")}, index, stand))
    return ZaehlListe(zeilen)


# ── 4. Zusammenbau, Ordnung und Filter ────────────────────────────────────

def _paare(bestand):
    """Eine Leserliste als ``(Zeilennummer, Knoten)``-Paare durchlaufen.

    Nimmt das Ergebnis der Leser (Paare mit Zeilennummer) **oder** eine
    einfache Liste von Knoten (dann ist die Zeilennummer ``0``). Nichts wird
    geraten: ein Element ohne Dict faellt weg.
    """
    liste = bestand if isinstance(bestand, (list, tuple)) else []
    for stelle, element in enumerate(liste, 1):
        if isinstance(element, dict):
            yield 0, element
        elif isinstance(element, (list, tuple)) and len(element) == 2 \
                and isinstance(element[1], dict):
            nummer = _als_int(element[0])
            yield (nummer if nummer is not None else 0), element[1]


def _quellen_zeile(bestand, nummer: int) -> str:
    """``dateiname:zeile`` bauen — der Dateiname kommt aus dem Leser."""
    name = getattr(bestand, "dateiname", "") or ""
    if not name:
        return f"Zeile {nummer}" if nummer else ""
    return f"{name}:{nummer}" if nummer else name


def _sortierschluessel(aussage: dict):
    """Feste Ordnung: Datum, Anlass, Unterart, dann die beteiligten Personen."""
    personen = tuple(
        (_text(p.get("kennung")), _text(p.get("name")))
        for p in (aussage.get("personen") or []) if isinstance(p, dict))
    return (_text(aussage.get("datum")), _text(aussage.get("anlass_id")),
            UNTERART_RANG.get(_text(aussage.get("unterart")), 9), personen)


def beziehungen_bauen(andockung, chat_andockung, ereignis_index_=None,
                      bestaetigung=None, stand=None) -> ZaehlListe:
    """Alle drei Unterarten bauen und in fester Ordnung zusammenfuehren — **rein**.

    Die Eingaben werden nicht veraendert. Zurueck kommt eine ``ZaehlListe`` von
    Aussagezeilen (siehe Modulkopf) in fester, reproduzierbarer Ordnung;
    ``ergebnis.defekt`` traegt die Zahl der defekten Eingabezeilen.
    """
    index = ereignis_index(ereignis_index_)
    stand = _stand_jz(stand)
    alle: list = []
    alle.extend(fotos_aussagen(andockung, index, bestaetigung, stand))
    alle.extend(chat_aussagen(chat_andockung, index, stand))
    alle.extend(fotos_und_chat_aussagen(andockung, chat_andockung, index,
                                        bestaetigung, stand))
    alle.sort(key=_sortierschluessel)
    defekt = (getattr(andockung, "defekt", 0)
              + getattr(chat_andockung, "defekt", 0))
    return ZaehlListe(alle, defekt=defekt)


def aussagen_filtern(aussagen, datum=None, nur_bestaetigt: bool = False) -> ZaehlListe:
    """Aussagen nach Tag und Bestaetigung filtern — **rein**, ohne I/O.

    ``datum`` (``JJJJ-MM-TT`` oder ``None``) behaelt nur Aussagen dieses Tages.
    ``nur_bestaetigt`` behaelt nur die Unterarten ``fotos``/``fotos_und_chat``
    mit **mindestens einer** bestaetigten Person; ``gemeinsam_im_chat`` faellt
    dabei weg (dort gibt es keine Personen-Kennung). Ein Tag, der kein lesbares
    Datum ist, ergibt eine deutsche ``PersonenFehler``-Meldung.
    """
    tag = _datum_lesen(datum) if datum is not None else None
    if datum is not None and tag is None:
        raise PersonenFehler(
            f"Das Datum '{_text(datum)}' ist kein gueltiges Datum "
            "(erwartet JJJJ-MM-TT).")
    ergebnis: list = []
    for aussage in aussagen if isinstance(aussagen, (list, tuple)) else []:
        if not isinstance(aussage, dict):
            continue
        if tag is not None and _text(aussage.get("datum")) != tag:
            continue
        if nur_bestaetigt:
            unterart = _text(aussage.get("unterart"))
            if unterart not in (UNTERART_FOTOS, UNTERART_FOTOS_UND_CHAT):
                continue
            if not any(_text(p.get("kennung")) and p.get("bestaetigt")
                       for p in aussage.get("personen") or []
                       if isinstance(p, dict)):
                continue
        ergebnis.append(aussage)
    return ZaehlListe(ergebnis)


# ── 5. Uebersicht und Bericht ─────────────────────────────────────────────

def _kennzahlen(aussagen) -> ZaehlDict:
    """Kennzahlen der Aussagen sammeln (je Unterart, Kennungen, Kontakte, Tage)."""
    anzahl = {name: 0 for name in UNTERART_REIHENFOLGE}
    kennungen: set = set()
    namen_bestaetigt: set = set()
    kontakte: set = set()
    daten: list = []
    for aussage in aussagen if isinstance(aussagen, (list, tuple)) else []:
        if not isinstance(aussage, dict):
            continue
        unterart = _text(aussage.get("unterart"))
        if unterart in anzahl:
            anzahl[unterart] += 1
        tag = _text(aussage.get("datum"))
        if tag:
            daten.append(tag)
        for person in aussage.get("personen") or []:
            if not isinstance(person, dict):
                continue
            kennung = _text(person.get("kennung"))
            if kennung:
                kennungen.add(kennung)
                if person.get("bestaetigt"):
                    namen_bestaetigt.add(kennung)
            else:
                name = _text(person.get("name"))
                if name:
                    kontakte.add(name)
    return ZaehlDict(anzahl=anzahl, personen_kennungen=len(kennungen),
                     namen_bestaetigt=len(namen_bestaetigt),
                     kontakte=len(kontakte),
                     datum_von=min(daten) if daten else None,
                     datum_bis=max(daten) if daten else None,
                     kontaktliste=sorted(kontakte))


def uebersicht_bauen(aussagen, quellen=None, stand=None) -> dict:
    """Das Uebersichts-Dokument bauen — **rein**, ohne I/O.

    Traegt ``art``, ``stand``, ``anzahl`` je Unterart,
    ``anzahl_personen_kennungen``, ``anzahl_namen_bestaetigt`` (nur wirklich
    bestaetigte Kennungen — ohne Bestaetigungsdatei also ``0``),
    ``anzahl_kontakte``, ``datum_von``/``datum_bis``, ``quellen`` und den
    ehrlichen ``hinweis``.
    """
    zahlen = _kennzahlen(aussagen)
    return {
        "art": ART_UEBERSICHT,
        "stand": _stand_jz(stand),
        "anzahl": dict(getattr(zahlen, "anzahl", {})),
        "anzahl_personen_kennungen": getattr(zahlen, "personen_kennungen", 0),
        "anzahl_namen_bestaetigt": getattr(zahlen, "namen_bestaetigt", 0),
        "anzahl_kontakte": getattr(zahlen, "kontakte", 0),
        "datum_von": getattr(zahlen, "datum_von", None),
        "datum_bis": getattr(zahlen, "datum_bis", None),
        "quellen": dict(quellen) if isinstance(quellen, dict) else {},
        "hinweis": HINWEIS_UEBERSICHT,
    }


def bericht_bauen(zahlen) -> str:
    """Die Zahlen des Laufs als mehrzeiliger deutscher Klartext.

    Feste Zeilen (damit der Trockenlauf die Sollwerte Zeile fuer Zeile nennt):
    gelesene Zeilen und defekte Zeilen · die drei Unterarten einzeln ·
    Aussagen gesamt · Personen-Kennungen · bestaetigte Namen in der Ausgabe ·
    benannte Kontakte · Datumsspanne · Kontakte je Anlass. Fehlende Felder
    ergeben ``0`` bzw. ``-`` statt eines Absturzes. Es stehen hier **keine**
    Klarnamen (nur Zaehlungen).
    """
    z = zahlen if isinstance(zahlen, dict) else {}

    def ganz(name: str) -> int:
        wert = _als_int(z.get(name))
        return wert if wert is not None else 0

    anzahl = z.get("anzahl")
    anzahl = anzahl if isinstance(anzahl, dict) else {}

    def unterart(name: str) -> int:
        wert = _als_int(anzahl.get(name))
        return wert if wert is not None else 0

    gesamt = sum(unterart(name) for name in UNTERART_REIHENFOLGE)
    zeilen = [
        f"Beziehungen N27 Schritt 5 - Stand {_text(z.get('stand')) or 'unbekannt'}",
        f"Zeilen gelesen: Person {_zahl(ganz('andockung_zeilen'))} x "
        f"Chat {_zahl(ganz('chat_zeilen'))} x "
        f"Ereignis {_zahl(ganz('ereignis_zeilen'))}   "
        f"defekte Zeilen: {_zahl(ganz('defekte_zeilen'))}",
        f"Aussagen fotos: {_zahl(unterart(UNTERART_FOTOS))}   "
        f"gemeinsam_im_chat: {_zahl(unterart(UNTERART_CHAT))}   "
        f"fotos_und_chat: {_zahl(unterart(UNTERART_FOTOS_UND_CHAT))}",
        f"Aussagen gesamt: {_zahl(gesamt)}",
        f"Personen-Kennungen: {_zahl(ganz('personen_kennungen'))}   "
        f"bestaetigte Namen in der Ausgabe: {_zahl(ganz('namen_bestaetigt'))}   "
        f"benannte Kontakte: {_zahl(ganz('kontakte'))}",
        f"Datum von: {_text(z.get('datum_von')) or '-'}   "
        f"bis: {_text(z.get('datum_bis')) or '-'}",
        f"Anlaesse mit Foto-Personen: {_zahl(ganz('anlaesse_fotos'))}   "
        f"Anlaesse mit Chat: {_zahl(ganz('anlaesse_chat'))}",
        HINWEIS_UEBERSICHT,
    ]
    return "\n".join(zeilen)


# ── 6. Schreiben: atomar, nur ausserhalb des Repos ───────────────────────

def pruefe_ausserhalb_repo(pfad) -> str:
    """Sicherstellen, dass ein Ausgabeziel AUSSERHALB des Repos liegt.

    Geprueft wird der absolut aufgeloeste Pfad (Gross-/Kleinschreibung und
    Schraeg-/Rueckwaertsstriche spielen keine Rolle). Liegt das Ziel im Repo,
    gibt es eine deutsche ``PersonenFehler``-Meldung (die Kommandozeile gibt
    sie auf ``stderr`` aus und endet mit Exit 2) — geschrieben wird dann
    nichts.
    """
    if not isinstance(pfad, str) or not pfad.strip():
        raise PersonenFehler("Kein Ausgabeziel angegeben.")
    ziel = os.path.normcase(os.path.abspath(pfad))
    repo = os.path.normcase(os.path.abspath(REPO))
    try:
        gemeinsam = os.path.commonpath([ziel, repo])
    except ValueError:                        # anderes Laufwerk: nie im Repo
        return pfad
    if gemeinsam == repo:
        raise PersonenFehler(
            f"Ausgabeziel liegt IM Repo und ist nicht erlaubt: {pfad}\n"
            "Die Beziehungen gehoeren ausserhalb des Repos (Standard: "
            f"{STANDARD_BASIS}); es wird NICHTS geschrieben.")
    return pfad


def _zeile_text(zeile: dict) -> str:
    """Eine Aussage als eine JSONL-Zeile — ASCII, sortierte Schluessel."""
    return json.dumps(zeile, ensure_ascii=True, sort_keys=True)


def schreiben(pfad, inhalt) -> str:
    """Atomar schreiben — ``list`` als JSONL, ``dict`` als JSON.

    Erst vollstaendig in ``<ziel>.tmp`` im **Zielordner** schreiben, dann per
    ``os.replace`` ersetzen: es entsteht nie eine halbe Datei. Scheitert das
    Schreiben, wird ausschliesslich die **eigene** temp-Datei entfernt (die
    einzige Loeschung im Modul) — eine vorhandene alte Zieldatei bleibt
    unangetastet. Ein Ziel **im Repo** ergibt eine ``PersonenFehler``-Meldung;
    geschrieben wird dann nichts. Rueckgabe: der geschriebene Pfad.
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


# ── 7. Kommandozeile ─────────────────────────────────────────────────────

def _quellen_namen(andockung, chat_andockung, ereignisse_x) -> dict:
    """Die Herkunfts-Namen fuer die Uebersicht (Dateinamen, keine Pfade)."""
    def name(roh) -> str:
        return os.path.basename(_text(roh)) or _text(roh)
    return {
        "andockung": getattr(andockung, "dateiname", "") or "",
        "chat": getattr(chat_andockung, "dateiname", "") or "",
        "ereignisse": name(ereignisse_x),
        "bestaetigung": "personen_bestaetigt.json",
    }


def main(argv=None) -> int:
    """Kommandozeile: lesen, ableiten, berichten, nur mit ``--schreiben`` ablegen.

    Standard ist der **Trockenlauf**: gerechnet und berichtet wird, geschrieben
    wird **nichts** (``--trocken`` hat Vorrang vor ``--schreiben``).
    Ausgabeziele **im Repo** ergeben Exit 2 und keine Datei — auch im
    Trockenlauf. ``--datum`` behaelt nur Aussagen dieses Tages (ungueltiges
    Datum ⇒ deutsche Meldung, Exit 2). ``--nur-bestaetigt`` behaelt nur
    ``fotos``/``fotos_und_chat`` mit mindestens einer bestaetigten Person.
    Fehlende Eingaben ergeben eine deutsche Meldung auf ``stderr`` und Exit 2.
    """
    zerleger = argparse.ArgumentParser(
        description="Beziehungen N27 Schritt 5: leitet aus der "
                    "Personen-Andockung (N27d), der Chat-Andockung (N27b) und "
                    "den Ereignissen (N27a) belegbare Aussagen der Form 'wer "
                    "war mit wem wo' ab. Jede Aussage mit Datum, Beleg und "
                    "Quelle. Namen nur nach Bestaetigung. Kein "
                    "Nachrichtentext, kein Netz, kein Bild, kein Schreiben ins "
                    "Repo.")
    zerleger.add_argument("--ereignisse", dest="ereignisse",
                          default=STANDARD_EREIGNISSE,
                          help="Ereignis-Knoten aus N27a (JSONL)")
    zerleger.add_argument("--andockung", dest="andockung",
                          default=STANDARD_ANDOCKUNG,
                          help="Personen-Andockung aus N27d (JSONL)")
    zerleger.add_argument("--chat-andockung", dest="chat_andockung",
                          default=STANDARD_CHAT_ANDOCKUNG,
                          help="Chat-Andockung aus N27b (JSONL)")
    zerleger.add_argument("--bestaetigung", dest="bestaetigung",
                          default=STANDARD_BESTAETIGUNG,
                          help="Bestaetigungsdatei des Nutzers (JSON, darf fehlen)")
    zerleger.add_argument("--ausgabe", dest="ausgabe", default=STANDARD_AUSGABE,
                          help="Zieldatei der Aussagen (JSONL, PFLICHT "
                               "ausserhalb des Repos)")
    zerleger.add_argument("--ausgabe-uebersicht", dest="ausgabe_uebersicht",
                          default=STANDARD_AUSGABE_UEBERSICHT,
                          help="Zieldatei der Uebersicht (JSON, PFLICHT "
                               "ausserhalb des Repos)")
    zerleger.add_argument("--stand", dest="stand", default=None,
                          help="fester Zeitstempel fuer 'stand' (Standard: "
                               "jetzt); macht zwei Laeufe byte-gleich")
    zerleger.add_argument("--datum", dest="datum", default=None,
                          help="nur Aussagen dieses Tages (JJJJ-MM-TT)")
    zerleger.add_argument("--nur-bestaetigt", dest="nur_bestaetigt",
                          action="store_true",
                          help="nur fotos/fotos_und_chat mit mindestens einer "
                               "bestaetigten Person")
    zerleger.add_argument("--trocken", dest="trocken", action="store_true",
                          help="nur rechnen und berichten (Standard)")
    zerleger.add_argument("--schreiben", dest="schreiben", action="store_true",
                          help="beide Ausgabedateien schreiben (atomar, nur "
                               "ausserhalb des Repos); --trocken hat Vorrang")
    args = zerleger.parse_args(argv)

    schreiben_gewuenscht = bool(args.schreiben) and not bool(args.trocken)

    try:
        # Repo-Schutz zuerst (auch im Trockenlauf): ein Ziel im Repo ist Exit 2.
        pruefe_ausserhalb_repo(args.ausgabe)
        pruefe_ausserhalb_repo(args.ausgabe_uebersicht)
        if args.datum is not None and _datum_lesen(args.datum) is None:
            raise PersonenFehler(
                f"Das Datum '{_text(args.datum)}' ist kein gueltiges Datum "
                "(erwartet JJJJ-MM-TT).")
        andockung = personen_andockung_lesen(args.andockung)
        chat_andockung = chat_andockung_lesen(args.chat_andockung)
        ereignisse = ereignisse_lesen(args.ereignisse)
        bestaetigung = bestaetigung_lesen(args.bestaetigung)
        stand = _stand_jz(args.stand)
        alle = beziehungen_bauen(andockung, chat_andockung, ereignisse,
                                 bestaetigung, stand)
        gefiltert = aussagen_filtern(alle, args.datum,
                                     bool(args.nur_bestaetigt))
        quellen = _quellen_namen(andockung, chat_andockung, args.ereignisse)
        uebersicht = uebersicht_bauen(gefiltert, quellen, stand)
        zahlen = {
            "stand": stand,
            "andockung_zeilen": len(andockung),
            "chat_zeilen": len(chat_andockung),
            "ereignis_zeilen": len(ereignisse),
            "defekte_zeilen": (getattr(andockung, "defekt", 0)
                               + getattr(chat_andockung, "defekt", 0)
                               + getattr(ereignisse, "defekt", 0)),
            "anzahl": dict(uebersicht["anzahl"]),
            "personen_kennungen": uebersicht["anzahl_personen_kennungen"],
            "namen_bestaetigt": uebersicht["anzahl_namen_bestaetigt"],
            "kontakte": uebersicht["anzahl_kontakte"],
            "datum_von": uebersicht["datum_von"],
            "datum_bis": uebersicht["datum_bis"],
            "anlaesse_fotos": len({a["anlass_id"] for a in gefiltert
                                   if a.get("unterart") == UNTERART_FOTOS}),
            "anlaesse_chat": len({a["anlass_id"] for a in gefiltert
                                  if a.get("unterart") == UNTERART_CHAT}),
        }
    except PersonenFehler as problem:
        print(f"Fehler: {problem}", file=sys.stderr)
        return 2

    print("Beziehungen N27 Schritt 5 - "
          + ("SCHREIBEN" if schreiben_gewuenscht
             else "TROCKENLAUF (es wird nichts geschrieben)"))
    print(f"Personen-Andockung: {args.andockung}")
    print(f"Chat-Andockung: {args.chat_andockung}")
    print(f"Ereignisse: {args.ereignisse}")
    print(f"Bestaetigung: {args.bestaetigung}"
          f" ({'vorhanden' if bestaetigung else 'leer/fehlt'})")
    print(bericht_bauen(zahlen))
    print(f"Geplant: {_zahl(len(gefiltert))} Aussagezeilen")

    if not schreiben_gewuenscht:
        print(f"Trockenlauf: {args.ausgabe} und "
              f"{args.ausgabe_uebersicht} wurden NICHT geschrieben.")
        return 0

    try:
        ziel = schreiben(args.ausgabe, gefiltert)
        ziel_uebersicht = schreiben(args.ausgabe_uebersicht, uebersicht)
    except PersonenFehler as problem:
        print(f"Fehler: {problem}", file=sys.stderr)
        return 2
    print(f"Beziehungen geschrieben: {ziel}")
    print(f"Uebersicht geschrieben: {ziel_uebersicht}")
    return 0


# Zweiter Name derselben Kommandozeile (das Nachbarmodul heisst ``main``).
haupt = main


if __name__ == "__main__":
    raise SystemExit(main())
