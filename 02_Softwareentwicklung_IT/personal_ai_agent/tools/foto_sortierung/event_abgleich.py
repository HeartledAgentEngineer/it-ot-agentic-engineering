"""Event-Abgleich fuer das Foto-Sortieren (Nachtlauf-Schritt N6e, 27.09.2026).

Wozu dieses Werkzeug:
  Nach N6d steht der Zielpfad fest: ``Agent/Fotos/<Jahr>/<Kategorie>/<Event>``.
  Die Kategorie kommt aus dem Bucket (``foto_kategorien.py``), der Event-Name
  bisher aus dem Datums-Block (``2025-01-06_Anlass-01``). Sebastian hat in
  seiner eigenen Ablage aber **schon** Event-Ordner, teils seit 2013, nach drei
  erkennbaren Mustern (hier als Musterform, mit erfundenen Platzhaltern)::

      Jahr Ort                    2013 <Ausflugsziel>, 2020 <Stadt>
      Jahr_Monat[_Tag] Ereignis   2018_11_25 <Band>, 2019_08 <Festival>
      Jahr Person                 2017 <Vorname>, 2020+ <Vorname>

  Dazu Sonderformen, die real vorkommen und die der Parser kennen muss:
  Jahresspanne (``2015-2018 …``, ``2013_2014 …``), offenes Ende (``2019+ …``),
  Jahr als Suffix (``Beispiel_2019``), Datum mit Punkten und zwei Ziffern
  (``… 10.10.21``), Monatsliste (``2021_08 & 10 …``), Jahr doppelt im Namen,
  Ordner **ohne** jedes Jahr (``<Vorname>``, ``<Bandname>``, ``Spielkonsole``).

  Ziel: **vorschlagen, nicht neu bauen.** Findet sich fuer einen Datums-Block
  ein bestehender Event-Ordner derselben Kategorie, wird dieser als Ziel
  vorgeschlagen — nur wenn es keinen gibt, entsteht ein neuer Name.

  Vorgeschlagen wird nur, was **Tag** oder **Monat** (und Jahr) trifft. Ein bloß
  gleiches Jahr oder eine Jahresspanne ist **kein** Vorschlag, sondern ein
  schwacher Hinweis und wird erst mit ``--auch-schwach`` zum Vorschlag (dann
  ``sicher: false``).

  Dieses Werkzeug ist ein **Vorschlag**, keine Ausfuehrung: es schreibt nichts
  in die pCloud und verschiebt nichts. Es liest ausschliesslich lokale Dateien.

Datenschutz (Regel des Auftrags, hier als Code):
  * Die echten Ordnernamen des Nutzers sind privat und liegen absichtlich
    **ausserhalb** des Repos. Gelesen werden nur lokale Dateien:
    ``~/foto_sortierung/kategorien.json`` (Bestand),
    ``~/foto_sortierung/kategorie_zuordnung.json`` (Bucket -> Ordner),
    ``~/foto_sortierung/themen.jsonl`` (je Zeile ein Anlass) und
    ``~/foto_sortierung/themen/<Jahr>/<Anlass>.json`` (Kachel-Beschreibungen).
  * Es gibt in dieser Datei **keine** pCloud-Schnittstelle: kein Dienst, kein
    ``liste``-Aufruf, kein ``thumb``. Der Parameter ``service`` von ``main``
    bleibt nur, weil alle Nachbarwerkzeuge ihn haben — er wird **nicht** benutzt.
  * Es gibt in dieser Datei **keine** Loeschfunktion und kein Verschieben. Die
    einzige Schreiboperation ist die Vorschlagsdatei, und die liegt zwingend
    **ausserhalb** des Repos (Schutzfunktion des Nachbarmoduls).

Wie ein Anlass aussieht (das, was die reinen Funktionen bekommen)::

    {"titel": "2025-01-06_Anlass-01",   # Datums-Block
     "datum": "2025-01-06",             # ISO-Datum
     "jahr": 2025, "thema": "Konzert und Buehne",
     "kacheln": [{"kurz": "…"}, …]}     # Kachel-Kurzbeschreibungen

  ``titel``, ``jahr``, ``monat``, ``tag`` und ``datum`` sind austauschbar:
  fehlt das Datum, wird es aus ``titel`` gelesen (``2025-01-06_Anlass-01``);
  fehlen ``monat``/``tag``, kommen sie aus ``datum``. Kacheln duerfen Dicts mit
  ``kurz`` oder blanke Texte sein.

Die sieben sauberen Bausteine:

  1. ``ordner_datum_lesen(name)`` — zerlegt einen vorhandenen Ordnernamen in
     Datums-Belege (Jahre, Spanne, offenes Jahr, Monat, Tag, ``rest``).
  2. ``datum_stufe(anlass, ordner)`` — genau eine Stufe: ``tag`` > ``monat`` >
     ``jahr`` > ``spanne`` > ``ohne_jahr``.
  3. ``kandidaten(anlass, unterordner)`` — alle Unterordner der Ziel-Kategorie,
     deterministisch sortiert (Stufe, dann Wortueberlappung, dann alphabetisch).
  4. ``vorschlag_fuer(anlass, unterordner, auch_schwach=False)`` — der beste
     Kandidat oder ``None``. **Vorschlag** ist nur, was die Stufe ``tag`` oder
     ``monat`` traegt; ``jahr``/``spanne`` sind ein **schwacher Hinweis** und
     werden erst mit ``auch_schwach=True`` ein Vorschlag (dann ``sicher: False``).
  5. ``hinweis_text(anlass, unterordner, auch_schwach=False)`` — Klartextzeile je
     Anlass.
  6. ``trefferquote(anlaesse, kategorien[, zuordnung[, auch_schwach]])`` — reiner
     Zahlenbericht; **Vorschlag (tag/monat)** und **schwacher Hinweis
     (jahr/spanne)** stehen getrennt.
  7. ``vorschlaege_schreiben(pfad, daten, trocken=True)`` — nur ausserhalb des
     Repos, atomar, nur bei echter Aenderung.

Aufruf (Kommandozeile)::

    python tools/foto_sortierung/event_abgleich.py --zeigen
    python tools/foto_sortierung/event_abgleich.py --zeigen --stichprobe 20
    python tools/foto_sortierung/event_abgleich.py --auch-schwach --zeigen
    python tools/foto_sortierung/event_abgleich.py --schreiben   # nur mit Absicht

Ohne ``--schreiben`` wird **nichts** geschrieben.

Als Modul (Tests, Skripte): ``main(argv=[...], service=None)``.
"""

from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import os
import re

HIER = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HIER))            # .../personal_ai_agent

# Vorgabepfade: ausserhalb des Repos — dort liegen die privaten Ordnernamen.
STANDARD_BASIS = os.path.join(os.path.expanduser("~"), "foto_sortierung")
STANDARD_KATEGORIEN = os.path.join(STANDARD_BASIS, "kategorien.json")
STANDARD_ZUORDNUNG = os.path.join(STANDARD_BASIS, "kategorie_zuordnung.json")
STANDARD_THEMEN = os.path.join(STANDARD_BASIS, "themen.jsonl")
STANDARD_VORSCHLAEGE = os.path.join(STANDARD_BASIS, "vorschlaege.json")

# Rueckfall-Text fuer Anlaesse ohne Thema (Auflage aus N7: kein Abbruch).
OHNE_THEMA = "Ohne-Thema"


def _modul_aus_pfad(pfad: str, name: str):
    """Ein Nachbarmodul per Pfad laden (Muster aus ``foto_kategorien.py``)."""
    spez = importlib.util.spec_from_file_location(name, pfad)
    if spez is None or spez.loader is None:
        raise RuntimeError(f"Modul nicht gefunden: {pfad}")
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


# Das Nachbarmodul N6d: es liefert Bestand, Zuordnung, Bucket-Uebersetzung und
# die Schutzfunktionen (Namensbereinigung, Repo-Schutz, atomares Schreiben).
_kategorien = _modul_aus_pfad(os.path.join(HIER, "foto_kategorien.py"),
                              "foto_kategorien")

pfad_saeubern = _kategorien.pfad_saeubern
kategorien_laden = _kategorien.kategorien_laden
zuordnung_laden = _kategorien.zuordnung_laden
bucket_fuer_thema = _kategorien.bucket_fuer_thema
ziel_kategorie = _kategorien.ziel_kategorie
OHNE_NAME = _kategorien.OHNE_NAME
KategorienFehler = _kategorien.KategorienFehler
JAHR_MIN = _kategorien.JAHR_MIN
JAHR_MAX = _kategorien.JAHR_MAX


class EventFehler(Exception):
    """Fehler dieses Werkzeugs — deutsche Klartextmeldung, kein Absturz."""


# ── Datums-Belege aus einem Ordnernamen lesen ──────────────────────────────

# Vierstellige Zahl als eigenes Wort (kein Ausschnitt aus einer laengeren Zahl).
_JAHR_RE = re.compile(r"(?<!\d)(?P<jahr>\d{4})(?!\d)")

# Zwei Jahre mit ``-`` oder ``_`` verbunden: Spanne ``2015-2018``, ``2013_2014``.
_SPANNE_RE = re.compile(
    r"(?<!\d)(?P<von>\d{4})\s*[-_]\s*(?P<bis>\d{4})(?!\d)")

# Offenes Ende: ``2019+`` heisst "ab 2019".
_OFFEN_RE = re.compile(r"(?<!\d)(?P<jahr>\d{4})\s*\+")

# Blanke Zahl DIREKT an ein Jahr angeschlossen — nur so gilt sie als Monat:
# ``2019_08``, ``2018-11``, ``2018_11_25``, ``2018_3``. Mit Leerzeichen davor
# (``Spiel A 2``) oder ohne Jahr davor (``9.Klasse``, ``108``) ist es kein
# Monat. Der Tag kommt nur aus der Dreier-Form.
_ANGEDOCKT_RE = re.compile(
    r"(?<!\d)(?P<jahr>\d{4})(?P<trenner>[-_.])(?P<a>\d{1,2})"
    r"(?:(?P<trenner2>[-_])(?P<b>\d{1,2}))?(?!\d)")

# Punkt-Datum mit zwei ODER vier Ziffern im Jahr: ``10.10.21``, ``10.10.2021``.
_PUNKT_RE = re.compile(
    r"(?<!\d)(?P<tag>\d{1,2})\.(?P<monat>\d{1,2})\.(?P<jahr>\d{2}|\d{4})(?!\d)")


def _zahl_im_jahrbereich(wert) -> int | None:
    """Eine vierstellige Zahl als Jahr lesen — nur 1900–2100, sonst ``None``."""
    try:
        jahr = int(wert)
    except (TypeError, ValueError):
        return None
    return jahr if JAHR_MIN <= jahr <= JAHR_MAX else None


def _jahr_aus_zwei_ziffern(wert) -> int | None:
    """``21`` -> ``2021`` (Punkt-Datum mit zwei Ziffern im Jahr).

    Zweistellige Jahre gibt es in diesem Bestand nur im Punkt-Datum
    (``… 10.10.21``) und sie liegen alle nach der Jahrtausendwende; die
    Aufloesung ist deshalb fest ``2000 + wert`` und wird geprueft.
    """
    try:
        kurz = int(wert)
    except (TypeError, ValueError):
        return None
    return _zahl_im_jahrbereich(2000 + kurz)


def ordner_datum_lesen(name) -> dict:
    """Einen vorhandenen Ordnernamen in Datums-Belege zerlegen (rein, kein I/O).

    Rueckgabe::

        {"jahre": [int, …],          # aufsteigend, ohne Doppelung, 1900–2100
         "spanne": bool,             # zwei Jahre mit ``-``/``_`` verbunden
         "offen_ab": bool,           # Jahr mit ``+`` (ab diesem Jahr)
         "monat": int|None, "tag": int|None,
         "rest": str}                # der Name ohne die Datums-Bestandteile

    Regeln:
      * Jahre sind **vierstellige** Zahlen 1900–2100. ``108``, ``21`` und
        ``1899`` sind keine Jahre; ``2019_2019`` ergibt **ein** Jahr (Doppelung
        faellt weg), setzt aber ``spanne`` — es sind zwei verbundene Jahresangaben.
      * Monat/Tag kommen aus ``JJJJ_MM``, ``JJJJ-MM``, ``JJJJ.MM``,
        ``JJJJ_MM_TT``, ``JJJJ-MM-TT`` und aus dem Punkt-Datum ``TT.MM.JJ`` bzw.
        ``TT.MM.JJJJ``. **Fehltreffer-Regel:** eine blanke Zahl 1–12 zaehlt nur
        als Monat, wenn sie **direkt an ein Jahr anschliesst** (Trennzeichen
        ``_``, ``-`` oder ``.``) — ``Spiel A 2``, ``Spiel B 3``, ``9.Klasse``
        und ``108`` sind **keine** Monate. Ein Tag kommt nur aus der
        Dreier-Form bzw. dem Punkt-Datum.
      * Ein zweistelliges Jahr im Punkt-Datum wird als ``20xx`` gelesen und
        erscheint auch in ``jahre`` (sonst waere ``… 10.10.21`` ohne Jahr).
      * ``rest`` ist der Name ohne die erkannten Datums-Bestandteile und laeuft
        durch ``pfad_saeubern``. Steht im Namen sonst nichts, ist ``rest`` der
        Rueckfallname ``Ohne-Name`` (leerer Name waere kein Name).
      * Nicht-Text und ``None`` ergeben leere Belege statt einer Ausnahme.

    Die Funktion ist rein: kein Dateizugriff, kein Netz, keine Ausnahme.
    """
    leer = {"jahre": [], "spanne": False, "offen_ab": False,
            "monat": None, "tag": None, "rest": OHNE_NAME}
    if not isinstance(name, str) or not name.strip():
        return leer

    jahre: list[int] = []
    for treffer in _JAHR_RE.finditer(name):
        jahr = _zahl_im_jahrbereich(treffer.group("jahr"))
        if jahr is not None and jahr not in jahre:
            jahre.append(jahr)

    spanne = False
    for treffer in _SPANNE_RE.finditer(name):
        von = _zahl_im_jahrbereich(treffer.group("von"))
        bis = _zahl_im_jahrbereich(treffer.group("bis"))
        if von is not None and bis is not None:
            spanne = True
            for jahr in (von, bis):
                if jahr not in jahre:
                    jahre.append(jahr)

    offen_ab = False
    for treffer in _OFFEN_RE.finditer(name):
        jahr = _zahl_im_jahrbereich(treffer.group("jahr"))
        if jahr is not None:
            offen_ab = True

    monat = None
    tag = None
    angedockt = _ANGEDOCKT_RE.search(name)
    if angedockt is not None:
        jahr = _zahl_im_jahrbereich(angedockt.group("jahr"))
        if jahr is not None:
            moeglich = int(angedockt.group("a"))
            if 1 <= moeglich <= 12:
                monat = moeglich
                if angedockt.group("b") is not None:
                    moeglich_tag = int(angedockt.group("b"))
                    if 1 <= moeglich_tag <= 31:
                        tag = moeglich_tag

    # Das Punkt-Datum ist die ausdruecklichere Angabe und gewinnt fuer Monat/Tag.
    punkt = _PUNKT_RE.search(name)
    if punkt is not None:
        tag_moeglich = int(punkt.group("tag"))
        monat_moeglich = int(punkt.group("monat"))
        roh_jahr = punkt.group("jahr")
        jahr_punkt = (_jahr_aus_zwei_ziffern(roh_jahr) if len(roh_jahr) == 2
                      else _zahl_im_jahrbereich(roh_jahr))
        if (jahr_punkt is not None and 1 <= tag_moeglich <= 31
                and 1 <= monat_moeglich <= 12):
            tag = tag_moeglich
            monat = monat_moeglich
            if jahr_punkt not in jahre:
                jahre.append(jahr_punkt)

    rest_roh = name
    for muster in (_SPANNE_RE, _PUNKT_RE, _OFFEN_RE, _ANGEDOCKT_RE, _JAHR_RE):
        rest_roh = muster.sub(" ", rest_roh)
    # Trennzeichen, die nur zum entfernten Datum gehoerten, fallen an den
    # Raendern weg (``Beispiel_2019`` -> ``Beispiel``, ``2019_Festival`` -> ``Festival``).
    rest_roh = rest_roh.strip(" ._-")

    return {"jahre": sorted(jahre),
            "spanne": spanne,
            "offen_ab": offen_ab,
            "monat": monat,
            "tag": tag,
            "rest": pfad_saeubern(rest_roh)}


# ── Den Anlass lesen (ohne I/O) ────────────────────────────────────────────

# Datums-Block am Anfang: ``2025-01-06_Anlass-01`` oder ``2025-01-06``.
_BLOCK_RE = re.compile(r"(?<!\d)(?P<jahr>\d{4})-(?P<monat>\d{2})-(?P<tag>\d{2})")


def _int_oder_none(wert) -> int | None:
    """Zahl tolerant lesen — ``None`` statt Ausnahme, ``bool`` zaehlt nicht."""
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


def anlass_teile(anlass) -> dict:
    """``(jahr, monat, tag, datum)`` eines Anlasses lesen (rein, kein I/O).

    Quellen in dieser Reihenfolge: ausdrueckliche Felder ``jahr``/``monat``/
    ``tag``, dann das Feld ``datum``, dann der Datums-Block am Anfang von
    ``titel`` (``2025-01-06_Anlass-01``). Was fehlt, bleibt ``None`` — es wird
    **nichts geraten**. Ein blanker Text wird selbst als Datums-Block gelesen.
    """
    ergebnis = {"jahr": None, "monat": None, "tag": None, "datum": ""}
    if isinstance(anlass, str):
        anlass = {"titel": anlass}
    if not isinstance(anlass, dict):
        return ergebnis

    ergebnis["jahr"] = _int_oder_none(anlass.get("jahr"))
    ergebnis["monat"] = _int_oder_none(anlass.get("monat"))
    ergebnis["tag"] = _int_oder_none(anlass.get("tag"))

    for quelle in ("datum", "titel"):
        wert = anlass.get(quelle)
        if not isinstance(wert, str):
            continue
        treffer = _BLOCK_RE.search(wert)
        if treffer is None:
            continue
        if not ergebnis["datum"]:
            ergebnis["datum"] = treffer.group(0)
        if ergebnis["jahr"] is None:
            ergebnis["jahr"] = _zahl_im_jahrbereich(treffer.group("jahr"))
        if ergebnis["monat"] is None:
            ergebnis["monat"] = _int_oder_none(treffer.group("monat"))
        if ergebnis["tag"] is None:
            ergebnis["tag"] = _int_oder_none(treffer.group("tag"))
    return ergebnis


def anlass_datum(anlass) -> str:
    """Das Datum eines Anlasses als Klartext — leer, wenn keines erkennbar ist."""
    return anlass_teile(anlass)["datum"]


def anlass_thema(anlass) -> str:
    """Das Thema eines Anlasses als Text — leer, wenn keines da ist."""
    if isinstance(anlass, dict):
        thema = anlass.get("thema")
    elif isinstance(anlass, str):
        thema = None
    else:
        return ""
    return thema.strip() if isinstance(thema, str) and thema.strip() else ""


def _kacheln_texte(anlass) -> list[str]:
    """Die Kachel-Kurzbeschreibungen eines Anlasses (Dicts mit ``kurz`` oder Text)."""
    if not isinstance(anlass, dict):
        return []
    kacheln = anlass.get("kacheln")
    if not isinstance(kacheln, list):
        return []
    texte: list[str] = []
    for eintrag in kacheln:
        if isinstance(eintrag, dict):
            kurz = eintrag.get("kurz")
        else:
            kurz = eintrag
        if isinstance(kurz, str) and kurz.strip():
            texte.append(kurz.strip())
    return texte


# Nur Buchstaben (inkl. Umlaute) sind Woerter fuer den Vergleich — Zahlen und
# Satzzeichen trennen. Woerter unter drei Zeichen fallen weg (Rauschen).
_WORT_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


def _worte(text) -> set[str]:
    """Wortmenge eines Textes: kleingeschrieben, nur Buchstaben, ab 3 Zeichen."""
    if not isinstance(text, str):
        return set()
    return {wort.casefold() for wort in _WORT_RE.findall(text)
            if len(wort) >= 3}


def _rest_worte(belege: dict) -> set[str]:
    """Die Vergleichswoerter des ``rest`` — der Rueckfallname zaehlt nicht."""
    rest = belege.get("rest")
    if not isinstance(rest, str) or rest == OHNE_NAME:
        return set()
    return _worte(rest)


def _anlass_worte(anlass) -> set[str]:
    """Die Vergleichswoerter des Anlasses (Thema + Kachel-Kurzbeschreibungen)."""
    teile = [anlass_thema(anlass)] + _kacheln_texte(anlass)
    return _worte(" ".join(teile))


# ── Stage: wie gut passt der Ordner zum Anlass ─────────────────────────────

STUFE_TAG = "tag"
STUFE_MONAT = "monat"
STUFE_JAHR = "jahr"
STUFE_SPANNE = "spanne"
STUFE_OHNE_JAHR = "ohne_jahr"

# Absteigend: die Reihenfolge ist zugleich die Sortierreihenfolge.
STUFEN: list[str] = [STUFE_TAG, STUFE_MONAT, STUFE_JAHR, STUFE_SPANNE,
                     STUFE_OHNE_JAHR]

# Nur diese beiden Stufen gelten als sicherer Vorschlag (Tag bzw. Monat+Jahr).
SICHERE_STUFEN = (STUFE_TAG, STUFE_MONAT)

# Nur diese beiden Stufen ergeben ueberhaupt einen Vorschlag. Ein bloß gleiches
# Jahr ist **kein** Vorschlag: in einer Kategorie mit mehreren Ordnern desselben
# Jahres entstuenden damit reihenweise falsche Ziele (Sichtprobe der Runde 1) —
# das ist ein falscher Beleg, kein schwacher. ``jahr``/``spanne`` sind deshalb
# nur ein **schwacher Hinweis** und werden erst mit ``auch_schwach=True`` ein
# Vorschlag (dann ``sicher: False``).
STUFEN_VORSCHLAG = (STUFE_TAG, STUFE_MONAT)

# Die schwachen Stufen: sie werden gezaehlt und genannt, aber nicht vorgeschlagen.
STUFEN_SCHWACH = (STUFE_JAHR, STUFE_SPANNE)


def _stufe_rang(stufe) -> int:
    """Zahl zu einer Stufe; Unbekanntes sortiert hinter alles Bekannte."""
    try:
        return STUFEN.index(stufe)
    except ValueError:
        return len(STUFEN)


def _belege_von(ordner) -> dict:
    """Belege eines Ordners — ein Name wird gelesen, ein Beleg-Dict durchgereicht."""
    if isinstance(ordner, dict) and "jahre" in ordner:
        return ordner
    return ordner_datum_lesen(ordner)


def datum_stufe(anlass, ordner) -> str:
    """Genau eine Stufe fuer "wie gut passt dieser Ordner zu diesem Anlass".

    Absteigend, die erste passende gewinnt:

      * ``"tag"`` — Tag **und** Monat **und** Jahr gleich (staerkster Beleg),
      * ``"monat"`` — Monat **und** Jahr gleich,
      * ``"jahr"`` — das Anlass-Jahr steht im Namen,
      * ``"spanne"`` — das Anlass-Jahr liegt in einer Spanne oder ab einem
        offenen Jahr (``2015-2018`` bzw. ``2019+``),
      * ``"ohne_jahr"`` — kein Jahres-Bezug (Name ohne Jahr, fremdes Jahr oder
        Jahr ausserhalb jeder Spanne).

    Fehlende Teile zaehlen **nie** als Treffer: hat der Anlass keinen Tag oder
    keinen Monat, kann die Stufe ``tag``/``monat`` nicht entstehen — verglichen
    wird nur, was auf beiden Seiten da ist.

    Bewusste Entscheidungen (im Auftrag offen gelassen, hier festgelegt):
      * Steht im Namen ein Monat, der **nicht** passt, das Jahr aber schon,
        lautet die Stufe ``jahr`` — der Jahres-Beleg stimmt ja. Die Stufe
        ``jahr`` ist kein sicherer Vorschlag, die Abweichung steht in der
        Begruendung.
      * Ein Name mit einem **fremden** Jahr (weder genannt noch in einer Spanne)
        hat keinen Jahres-Bezug und ergibt ``ohne_jahr``; ein solcher Ordner
        wird nie vorgeschlagen.
      * Ist das Anlass-Jahr ein Randjahr der Spanne (``2015-2018`` und 2015),
        gewinnt die Stufe ``jahr`` (Reihenfolge absteigend).
    """
    belege = _belege_von(ordner)
    jahre = belege.get("jahre") or []
    teile = anlass_teile(anlass)
    jahr = teile["jahr"]
    monat = teile["monat"]
    tag = teile["tag"]

    if not jahre or jahr is None:
        return STUFE_OHNE_JAHR

    if (tag is not None and belege.get("tag") is not None
            and monat is not None and belege.get("monat") is not None
            and tag == belege["tag"] and monat == belege["monat"]
            and jahr in jahre):
        return STUFE_TAG

    if (monat is not None and belege.get("monat") is not None
            and monat == belege["monat"] and jahr in jahre):
        return STUFE_MONAT

    if jahr in jahre:
        return STUFE_JAHR

    if belege.get("spanne") and jahre[0] <= jahr <= jahre[-1]:
        return STUFE_SPANNE

    if belege.get("offen_ab") and jahr >= jahre[-1]:
        return STUFE_SPANNE

    return STUFE_OHNE_JAHR


def _begruendung(anlass, belege: dict, ueberlappung: int) -> str:
    """Klartext-Begruendung zu einer Stufe (deterministisch, ohne DOM)."""
    teile = anlass_teile(anlass)
    jahr = teile["jahr"]
    monat = teile["monat"]
    stufe = datum_stufe(anlass, belege)
    jahre = belege.get("jahre") or []

    if stufe == STUFE_TAG:
        kern = (f"Tag {belege['tag']}, Monat {belege['monat']} und "
                f"Jahr {jahr} gleich")
    elif stufe == STUFE_MONAT:
        kern = f"Monat {belege['monat']} und Jahr {jahr} gleich"
    elif stufe == STUFE_JAHR:
        kern = f"Jahr {jahr} gleich"
        if (belege.get("monat") is not None and monat is not None
                and belege["monat"] != monat):
            kern += f", Monat {belege['monat']} im Namen weicht ab"
    elif stufe == STUFE_SPANNE:
        if belege.get("offen_ab") and jahr is not None and jahr > jahre[-1]:
            kern = f"Jahr {jahr} liegt ab dem offenen Jahr {jahre[-1]}"
        else:
            kern = (f"Jahr {jahr} liegt in der Spanne "
                    f"{jahre[0]}-{jahre[-1]}")
    else:
        if not jahre:
            kern = "kein Jahr im Namen"
        elif jahr is None:
            kern = "kein Jahr am Anlass"
        else:
            kern = f"Jahr {jahre[-1]} im Namen passt nicht zu {jahr}"

    if ueberlappung:
        kern += f" ({ueberlappung} Worttreffer)"
    return kern


# ── Kandidaten und Vorschlag ───────────────────────────────────────────────

def kandidaten(anlass, unterordner) -> list[dict]:
    """Alle Unterordner der Ziel-Kategorie als Kandidaten, deterministisch sortiert.

    Sortiert wird nach Stufe (``tag`` -> ``monat`` -> ``jahr`` -> ``spanne`` ->
    ``ohne_jahr``), innerhalb einer Stufe nach Wortueberlappung (absteigend),
    danach alphabetisch. Zwei Laeufe sortieren deshalb **gleich**.

    Je Kandidat::

        {"name": str, "stufe": str,
         "ueberlappung": int,          # gemeinsame Woerter (rest <-> Kacheltexte)
         "begruendung": str}           # Klartext, z. B. "Jahr 2019 gleich"

    Nicht-Text und leere Namen in ``unterordner`` werden uebergangen; ``None``
    zaehlt wie eine leere Liste. Ohne Dateizugriff, ohne Netz.
    """
    if not isinstance(unterordner, list):
        return []
    ergebnis: list[dict] = []
    anlass_worte = _anlass_worte(anlass)
    for eintrag in unterordner:
        if not isinstance(eintrag, str) or not eintrag.strip():
            continue
        name = eintrag.strip()
        belege = ordner_datum_lesen(name)
        ueberlappung = len(_rest_worte(belege) & anlass_worte)
        ergebnis.append({
            "name": name,
            "stufe": datum_stufe(anlass, belege),
            "ueberlappung": ueberlappung,
            "begruendung": _begruendung(anlass, belege, ueberlappung),
        })
    ergebnis.sort(key=lambda k: (_stufe_rang(k["stufe"]), -k["ueberlappung"],
                                 k["name"].casefold(), k["name"]))
    return ergebnis


def vorschlag_fuer(anlass, unterordner, auch_schwach: bool = False) -> dict | None:
    """Den besten Kandidaten als Vorschlag — oder ``None``.

    **Harte Regeln (verschaerft nach der Sichtprobe der Runde 1):**

      * ``ohne_jahr`` reicht **nie** fuer einen Vorschlag (ein Ordner ohne Jahr
        wuerde sonst jeden Anlass dieser Kategorie schlucken).
      * **Nur ``tag`` und ``monat`` ergeben einen Vorschlag** (``STUFEN_VORSCHLAG``).
        Ein bloß gleiches Jahr ist **kein** Vorschlag: die Sichtprobe zeigte,
        dass damit in einer Kategorie mit mehreren Ordnern desselben Jahres
        reihenweise unpassende Ziele entstuenden — ein falscher Beleg, kein
        schwacher.
      * ``jahr`` und ``spanne`` sind ein **schwacher Hinweis**: sie werden
        gezaehlt und genannt, aber erst mit ``auch_schwach=True`` (CLI:
        ``--auch-schwach``) zum Vorschlag — dann ``sicher: False``.

    Rueckgabe: ``None`` oder ``{"name", "stufe", "sicher", "ueberlappung",
    "begruendung"}``.
    """
    alle = kandidaten(anlass, unterordner)
    if not alle:
        return None
    bester = alle[0]
    stufe = bester["stufe"]
    if stufe not in STUFEN_VORSCHLAG and not (
            auch_schwach and stufe in STUFEN_SCHWACH):
        return None
    return {
        "name": bester["name"],
        "stufe": stufe,
        "sicher": stufe in SICHERE_STUFEN,
        "ueberlappung": bester["ueberlappung"],
        "begruendung": bester["begruendung"],
    }


def hinweis_text(anlass, unterordner, auch_schwach: bool = False) -> str:
    """Eine Klartextzeile je Anlass — rein, ohne DOM, ohne I/O.

    ``<Datum> <Thema> -> Vorschlag '<Ordner>' (Stufe, Beleg)`` bzw.
    ``<Datum> <Thema> -> kein Vorschlag, neuer Ordner``. Fehlt das Datum oder
    das Thema, steht dort ``?`` bzw. ``Ohne-Thema`` (kein Abbruch, N7-Auflage).

    ``auch_schwach`` wird an ``vorschlag_fuer`` durchgereicht: ohne das
    Kennzeichen ergeben ``jahr``/``spanne`` **keinen** Vorschlag, sondern die
    Zeile ``kein Vorschlag, neuer Ordner``.
    """
    datum = anlass_datum(anlass) or "?"
    thema = anlass_thema(anlass) or OHNE_THEMA
    vorschlag = vorschlag_fuer(anlass, unterordner, auch_schwach=auch_schwach)
    if vorschlag is None:
        return f"{datum} {thema} \u2192 kein Vorschlag, neuer Ordner"
    return (f"{datum} {thema} \u2192 Vorschlag '{vorschlag['name']}' "
            f"({vorschlag['stufe']}, {vorschlag['begruendung']})")


# ── Bestand, Zuordnung und Kategorien-Zuordnung der Anlaesse ───────────────

def bestand_und_zuordnung(kategorien_pfad: str = STANDARD_KATEGORIEN,
                          zuordnung_pfad: str = STANDARD_ZUORDNUNG):
    """Bestand und Bucket-Zuordnung ueber das Nachbarmodul laden (nur lesend).

    Beide Dateien liegen ausserhalb des Repos. Fehlende/kaputte Dateien und
    unvollstaendige Zuordnungen ergeben ``KategorienFehler`` (Klartext) — es
    wird nichts geraten und nichts stillschweigend ergaenzt.
    """
    bestand = kategorien_laden(kategorien_pfad)
    zuordnung = zuordnung_laden(zuordnung_pfad, bestand)
    return bestand, zuordnung


def unterordner_von(kategorie, bestand) -> list[str] | None:
    """Die Unterordner einer Kategorie aus dem Bestand — ``None``, wenn es sie nicht gibt.

    ``[]`` heisst "Kategorie vorhanden, hat aber keine Unterordner"; ``None``
    heisst "diese Kategorie steht nicht im Bestand". Das ist ein Unterschied.
    """
    if not isinstance(kategorie, str) or not kategorie.strip():
        return None
    if isinstance(bestand, dict):
        eintraege = bestand.get("kategorien")
    else:
        eintraege = bestand
    if not isinstance(eintraege, list):
        return None
    for eintrag in eintraege:
        if not isinstance(eintrag, dict):
            continue
        if str(eintrag.get("name") or "").strip() != kategorie.strip():
            continue
        unterordner = eintrag.get("unterordner")
        return list(unterordner) if isinstance(unterordner, list) else []
    return None


def kategorie_fuer_anlass(anlass, zuordnung) -> str | None:
    """Den Ziel-Ordnernamen eines Anlasses bestimmen — ``None``, wenn unklar.

    Weg: ausdrueckliches Feld ``kategorie`` am Anlass, sonst das Thema des
    Anlasses -> Bucket (``foto_kategorien.bucket_fuer_thema``) -> echter Ordner
    (``foto_kategorien.ziel_kategorie`` ueber die Zuordnung). Unbekannte Themen
    landen bewusst auf ``Sonstiges`` (Rueckfall des Nachbarmoduls).
    """
    if isinstance(anlass, dict):
        eigenes = anlass.get("kategorie")
        if isinstance(eigenes, str) and eigenes.strip():
            return eigenes.strip()
    thema = anlass_thema(anlass)
    if not thema:
        return None
    return ziel_kategorie(bucket_fuer_thema(thema), zuordnung)


def _kategorie_eintraege(kategorien) -> list[dict]:
    """Die Kategorieneintraege aus einem Bestand holen (auch als blanke Liste)."""
    if isinstance(kategorien, dict):
        kategorien = kategorien.get("kategorien")
    if not isinstance(kategorien, list):
        return []
    return [e for e in kategorien if isinstance(e, dict)]


def trefferquote(anlaesse, kategorien, zuordnung=None,
                 auch_schwach: bool = False) -> str:
    """Reiner Zahlenbericht zum Vorschlags-Erfolg (feste Zeilenreihenfolge).

    **Vorschlag und schwacher Hinweis stehen getrennt** (Auflage der Runde 2):
    als **Vorschlag** zaehlen nur die Stufen ``tag`` und ``monat``; ``jahr`` und
    ``spanne`` sind ein **schwacher Hinweis** und stehen in eigener Zeile — sie
    erscheinen **nicht** in der Vorschlagszahl. Mit ``auch_schwach=True`` kommt
    eine zusaetzliche Zeile dazu, die beide zusammen nennt.

    Gezaehlt wird: Anlaesse gesamt, mit Vorschlag, davon je Stufe, schwacher
    Hinweis je Stufe (und in Summe), ohne Vorschlag, und Anlaesse, deren
    Kategorie im Bestand **fehlt** (dazu zaehlen auch Anlaesse ohne
    bestimmbares Thema). Die letzte Zahl ist eine Teilmenge von "ohne
    Vorschlag" — es gilt ``mit + ohne = gesamt``.

    ``kategorien`` ist der geladene Bestand (``{…, "kategorien": [...]}`` oder
    die Liste selbst); ``zuordnung`` ist die Bucket-Bindung aus
    ``foto_kategorien.zuordnung_laden``. Ohne ``zuordnung`` laesst sich die
    Kategorie eines Anlasses nur ueber ein eigenes Feld ``kategorie`` bestimmen
    — alles andere zaehlt dann als fehlende Kategorie (ehrlich, nicht geraten).
    """
    anlaesse = list(anlaesse) if isinstance(anlaesse, list) else []
    zaehler = {stufe: 0 for stufe in STUFEN_VORSCHLAG + STUFEN_SCHWACH}
    mit_vorschlag = 0
    schwach = 0
    kategorie_fehlt = 0
    for anlass in anlaesse:
        kategorie = kategorie_fuer_anlass(anlass, zuordnung)
        unterordner = unterordner_von(kategorie, {"kategorien": _kategorie_eintraege(kategorien)})
        if unterordner is None:
            kategorie_fehlt += 1
            unterordner = []
        # Ohne ``auch_schwach`` ist ein Vorschlag nur tag/monat; jahr/spanne
        # bleiben ein Hinweis und zaehlen nicht als Vorschlag.
        vorschlag = vorschlag_fuer(anlass, unterordner, auch_schwach=False)
        if vorschlag is not None:
            mit_vorschlag += 1
            if vorschlag["stufe"] in zaehler:
                zaehler[vorschlag["stufe"]] += 1
            continue
        # Kein (sicherer) Vorschlag: schwachen Hinweis getrennt zaehlen.
        alle = kandidaten(anlass, unterordner)
        stufe = alle[0]["stufe"] if alle else None
        if stufe in STUFEN_SCHWACH:
            zaehler[stufe] += 1
            schwach += 1
    ohne = len(anlaesse) - mit_vorschlag
    zeilen = [
        f"Anlaesse gesamt: {len(anlaesse)}",
        f"Mit Vorschlag: {mit_vorschlag}",
        f"Vorschlag Stufe tag: {zaehler[STUFE_TAG]}",
        f"Vorschlag Stufe monat: {zaehler[STUFE_MONAT]}",
        f"Schwacher Hinweis Stufe jahr: {zaehler[STUFE_JAHR]}",
        f"Schwacher Hinweis Stufe spanne: {zaehler[STUFE_SPANNE]}",
        f"Mit schwachem Hinweis: {schwach}",
    ]
    if auch_schwach:
        zeilen.append(f"Mit Vorschlag (auch schwach): {mit_vorschlag + schwach}")
    zeilen += [
        f"Ohne Vorschlag: {ohne}",
        f"Kategorie fehlt im Bestand: {kategorie_fehlt}",
    ]
    return "\n".join(zeilen)


# ── Anlaesse lesen (themen.jsonl oder themen/<Jahr>/*.json) ────────────────

def _anlass_normalisieren(daten, basis_ordner: str | None = None) -> dict:
    """Einen Datei-Eintrag in die Anlass-Form bringen (Kacheln mitlesen)."""
    anlass = dict(daten) if isinstance(daten, dict) else {}
    if not isinstance(anlass.get("kacheln"), list) and basis_ordner:
        datei = anlass.get("datei")
        if isinstance(datei, str) and os.path.isfile(datei):
            try:
                with open(datei, encoding="utf-8") as quelle:
                    anlass.update(json.load(quelle) or {})
            except (OSError, ValueError):
                pass                    # ohne Kacheln weiterarbeiten, nicht abbrechen
    return anlass


def anlaesse_laden(pfad: str = STANDARD_THEMEN) -> list[dict]:
    """Anlaesse aus ``themen.jsonl`` (Datei) oder ``themen/<Jahr>/…`` (Ordner) lesen.

    Beide Formen sind zugelassen:

      * **Datei** (``themen.jsonl``): eine JSON-Zeile je Anlass. Fehlt in der
        Zeile die Kachel-Beschreibung, wird sie aus der in ``datei`` genannten
        Anlass-Datei nachgelesen (die Kacheln braucht der Wortvergleich).
        Unlesbare Zeilen werden gezaehlt und uebergangen, nicht verschluckt.
      * **Ordner** (``themen/``): alle ``*.json`` unter den Jahres-Ordnern,
        jede Datei ist ein Anlass.

    Rueckgabe ist eine nach ``(datum, titel)`` sortierte Liste — damit ist die
    Reihenfolge (und die Stichprobe) bei jedem Lauf gleich. Fehlt der Pfad,
    gibt es ``EventFehler`` mit Klartextmeldung.
    """
    if not isinstance(pfad, str) or not pfad:
        raise EventFehler("Kein Pfad fuer die Themen angegeben.")
    if os.path.isdir(pfad):
        dateien = sorted(str(d) for d in _json_dateien(pfad))
    elif os.path.isfile(pfad):
        dateien = [pfad]
    else:
        raise EventFehler(f"Themen nicht gefunden: {pfad}")

    anlaesse: list[dict] = []
    uebersprungen = 0
    for datei in dateien:
        if os.path.isdir(pfad):
            try:
                with open(datei, encoding="utf-8") as quelle:
                    daten = json.load(quelle)
            except (OSError, ValueError):
                uebersprungen += 1
                continue
            if isinstance(daten, dict):
                anlaesse.append(_anlass_normalisieren(daten))
            else:
                uebersprungen += 1
            continue
        try:
            with open(datei, encoding="utf-8", errors="replace") as quelle:
                zeilen = quelle.read().splitlines()
        except OSError:
            raise EventFehler(f"Themen nicht lesbar: {datei}") from None
        for zeile in zeilen:
            if not zeile.strip():
                continue
            try:
                daten = json.loads(zeile)
            except ValueError:
                uebersprungen += 1
                continue
            if not isinstance(daten, dict):
                uebersprungen += 1
                continue
            anlaesse.append(_anlass_normalisieren(daten, os.path.dirname(datei)))

    anlaesse.sort(key=lambda a: (anlass_datum(a),
                                 str(a.get("titel") or "")))
    if uebersprungen:
        print(f"Hinweis: {uebersprungen} unlesbare Eintraege uebergangen.")
    return anlaesse


def _json_dateien(ordner: str):
    """Alle ``*.json`` unter einem Ordner, Jahr fuer Jahr, sortiert."""
    for wurzel, unterordner, dateien in os.walk(ordner):
        unterordner.sort()
        for name in sorted(dateien):
            if name.lower().endswith(".json"):
                yield os.path.join(wurzel, name)


# ── Vorschlaege bauen und schreiben ────────────────────────────────────────

def vorschlaege_bauen(anlaesse, bestand, zuordnung,
                      auch_schwach: bool = False) -> list[dict]:
    """Je Anlass eine Vorschlagszeile bauen (rein, deterministisch sortiert).

    Ohne ``auch_schwach`` tragen nur ``tag``/``monat`` einen Vorschlag; ``jahr``
    und ``spanne`` bleiben ``kein Vorschlag, neuer Ordner``. Mit
    ``auch_schwach=True`` werden auch sie ein Vorschlag (``sicher: False``).

    Je Zeile::

        {"anlass": str, "datum": str, "thema": str, "kategorie": str|None,
         "kategorie_im_bestand": bool, "vorschlag": str|None, "stufe": str|None,
         "sicher": bool, "begruendung": str}

    Sortiert wird nach ``(datum, anlass)`` — damit ist die Ausgabedatei bei
    gleichem Bestand byte-identisch.
    """
    zeilen: list[dict] = []
    for anlass in anlaesse if isinstance(anlaesse, list) else []:
        kategorie = kategorie_fuer_anlass(anlass, zuordnung)
        unterordner = unterordner_von(kategorie, bestand)
        vorschlag = vorschlag_fuer(anlass, unterordner or [],
                                   auch_schwach=auch_schwach)
        zeilen.append({
            "anlass": str((anlass or {}).get("titel") or "") if isinstance(anlass, dict) else "",
            "datum": anlass_datum(anlass),
            "thema": anlass_thema(anlass) or OHNE_THEMA,
            "kategorie": kategorie,
            "kategorie_im_bestand": unterordner is not None,
            "vorschlag": vorschlag["name"] if vorschlag else None,
            "stufe": vorschlag["stufe"] if vorschlag else None,
            "sicher": bool(vorschlag["sicher"]) if vorschlag else False,
            "begruendung": vorschlag["begruendung"] if vorschlag else
                           "kein Vorschlag, neuer Ordner",
        })
    zeilen.sort(key=lambda z: (z["datum"], z["anlass"]))
    return zeilen


def _schreibe_atomar(ziel: str, inhalt: dict) -> None:
    """JSON atomar schreiben — uebernimmt ``foto_kategorien._schreibe_atomar``."""
    return _kategorien._schreibe_atomar(ziel, inhalt)


def _ohne_stand(inhalt) -> dict:
    """Inhalt ohne das Feld ``stand`` — fuer den Wiederholbarkeitsvergleich."""
    return _kategorien._inhalt_ohne_stand(inhalt)


def vorschlaege_schreiben(pfad: str, daten, trocken: bool = True) -> dict:
    """Die Vorschlagsliste schreiben — atomar, nur ausserhalb des Repos, idempotent.

    ``pfad`` MUSS ausserhalb des Repos liegen; die Pruefung uebernimmt
    ``foto_kategorien._pruefe_ziel_ausserhalb_repo`` (bei einem Ziel im Repo:
    deutsche Meldung und ``SystemExit(2)`` — es wird nichts geschrieben).

    ``daten`` ist die Vorschlagsliste (oder ein fertiges Objekt mit dem Schluessel
    ``vorschlaege``). Geschrieben wird ``{"stand": <Zeit>, "vorschlaege": [...]}``
    atomar (temp-Datei + ``os.replace``) und **nur bei echter Aenderung**: Der
    neue Inhalt ohne ``stand`` wird mit dem vorhandenen Inhalt ohne ``stand``
    verglichen; ist beides gleich, bleibt die Datei byte-identisch (Meldung
    "unveraendert"). ``trocken=True`` zeigt nur, was geschrieben wuerde.

    Rueckgabe: ``{"geschrieben", "unveraendert", "trocken", "ziel", "anzahl"}``.
    """
    ziel = _kategorien._pruefe_ziel_ausserhalb_repo(pfad)
    if isinstance(daten, dict):
        inhalt: dict = dict(daten)
    else:
        inhalt = {"vorschlaege": list(daten) if isinstance(daten, list) else []}
    vorschlaege = inhalt.get("vorschlaege")
    if not isinstance(vorschlaege, list):
        vorschlaege = []
        inhalt["vorschlaege"] = vorschlaege
    anzahl = len(vorschlaege)

    vorhanden = None
    if os.path.isfile(ziel):
        try:
            with open(ziel, encoding="utf-8") as datei:
                vorhanden = json.load(datei)
        except (OSError, ValueError):
            vorhanden = None                  # kaputt -> wird ersetzt

    if vorhanden is not None and _ohne_stand(vorhanden) == _ohne_stand(inhalt):
        print(f"Vorschlaege unveraendert: {ziel} ({anzahl} Zeilen)")
        return {"geschrieben": False, "unveraendert": True,
                "trocken": bool(trocken), "ziel": ziel, "anzahl": anzahl}

    inhalt["stand"] = datetime.datetime.now().isoformat(timespec="seconds")
    if trocken:
        print(f"Trockenlauf: {ziel} wuerde geschrieben ({anzahl} Zeilen).")
        return {"geschrieben": False, "unveraendert": False, "trocken": True,
                "ziel": ziel, "anzahl": anzahl}

    _schreibe_atomar(ziel, inhalt)
    print(f"Vorschlaege geschrieben: {ziel} ({anzahl} Zeilen)")
    return {"geschrieben": True, "unveraendert": False, "trocken": False,
            "ziel": ziel, "anzahl": anzahl}


# ── Kommandozeile ──────────────────────────────────────────────────────────

def _stichprobe_zeilen(anlaesse, bestand, zuordnung, anzahl: int,
                       auch_schwach: bool = False) -> list[str]:
    """Bis zu ``anzahl`` Klartextzeilen (Datum/Thema -> Vorschlag oder Neubau)."""
    zeilen: list[str] = []
    for anlass in anlaesse[:max(0, anzahl)]:
        kategorie = kategorie_fuer_anlass(anlass, zuordnung)
        unterordner = unterordner_von(kategorie, bestand) or []
        zeilen.append(hinweis_text(anlass, unterordner, auch_schwach=auch_schwach))
    return zeilen


def main(argv=None, service=None) -> int:
    """Kommandozeilen-Teil: anzeigen (Standard) oder die Vorschlaege schreiben.

    ``service`` bleibt unbenutzt — dieses Werkzeug liest ausschliesslich lokale
    Dateien und ruft **keine** pCloud-Funktion auf; der Parameter existiert nur,
    weil alle Nachbarwerkzeuge ihn fuehren.
    """
    zerleger = argparse.ArgumentParser(
        description="Event-Abgleich: bestehende Event-Ordner als Vorschlag "
                    "statt Neubau (nur lesend, nur lokale Dateien).")
    zerleger.add_argument("--zeigen", action="store_true",
                          help="Vorschlaege und Trefferquote anzeigen "
                               "(Standard, wenn nicht --schreiben)")
    zerleger.add_argument("--stichprobe", type=int, default=5,
                          dest="stichprobe",
                          help="so viele Beispielzeilen mit Begruendung zeigen "
                               "(Standard 5, 0 = keine)")
    zerleger.add_argument("--kategorien-pfad", dest="kategorien_pfad",
                          default=STANDARD_KATEGORIEN,
                          help="Bestandsdatei (ausserhalb des Repos)")
    zerleger.add_argument("--zuordnung-pfad", dest="zuordnung_pfad",
                          default=STANDARD_ZUORDNUNG,
                          help="Zuordnung Bucket -> Ordner (ausserhalb des Repos)")
    zerleger.add_argument("--themen-pfad", dest="themen_pfad",
                          default=STANDARD_THEMEN,
                          help="themen.jsonl (Datei) oder themen/ (Ordner)")
    zerleger.add_argument("--vorschlaege-pfad", dest="vorschlaege_pfad",
                          default=STANDARD_VORSCHLAEGE,
                          help="Zieldatei der Vorschlagsliste (ausserhalb des Repos)")
    zerleger.add_argument("--auch-schwach", action="store_true",
                          dest="auch_schwach",
                          help="auch die Stufen 'jahr' und 'spanne' als Vorschlag "
                               "zulassen (dann sicher: false; Standard: nur "
                               "schwacher Hinweis)")
    zerleger.add_argument("--schreiben", action="store_true",
                          help="die Vorschlagsliste wirklich schreiben "
                               "(atomar, nur ausserhalb des Repos)")
    args = zerleger.parse_args(argv)

    try:
        bestand, zuordnung = bestand_und_zuordnung(args.kategorien_pfad,
                                                   args.zuordnung_pfad)
        anlaesse = anlaesse_laden(args.themen_pfad)
        print("Event-Abgleich (nur Vorschlaege, kein Verschieben)")
        print(f"Bestand: {args.kategorien_pfad}")
        print(f"Zuordnung: {args.zuordnung_pfad}")
        print(f"Themen: {args.themen_pfad} ({len(anlaesse)} Anlaesse)")
        eintraege = _kategorie_eintraege(bestand)
        print(f"Kategorien im Bestand: {len(eintraege)}   "
              f"Unterordner gesamt: "
              f"{sum(len(e.get('unterordner') or []) for e in eintraege)}")
        print(trefferquote(anlaesse, bestand, zuordnung,
                           auch_schwach=args.auch_schwach))

        if args.stichprobe:
            print(f"Stichprobe ({args.stichprobe}):")
            for zeile in _stichprobe_zeilen(anlaesse, bestand, zuordnung,
                                            args.stichprobe,
                                            auch_schwach=args.auch_schwach):
                print("  " + zeile)

        if args.schreiben:
            daten = vorschlaege_bauen(anlaesse, bestand, zuordnung,
                                      auch_schwach=args.auch_schwach)
            ergebnis = vorschlaege_schreiben(args.vorschlaege_pfad, daten,
                                             trocken=False)
            print(f"Zeilen in der Vorschlagsliste: {ergebnis['anzahl']}")
        else:
            print("Ohne --schreiben wurde NICHTS geschrieben.")
        return 0
    except (EventFehler, KategorienFehler) as problem:
        print(f"Fehler: {problem}")
        return 2
    except SystemExit:
        raise


if __name__ == "__main__":
    raise SystemExit(main())
