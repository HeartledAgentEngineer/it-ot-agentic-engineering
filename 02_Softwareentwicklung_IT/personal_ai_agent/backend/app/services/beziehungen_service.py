"""Beziehungen an einem Tag abfragen — „wer war mit wem wo" (N28, 29.09.2026).

Warum dieses Modul
------------------
Der Nachtlauf-Schritt N27e hat je Anlass **belegbare** Aussagen „wer war mit
wem wo" mit Datum und Quelle in ``~/foto_sortierung/beziehungen.jsonl``
abgeleitet (15.051 Aussagen, 645 Tage, 2016-05-04 bis 2025-08-16). Diese Datei
lag bisher **nur auf dem PC** und wurde von niemandem gelesen: die Datenbank ist
voll, die App konnte nichts davon zeigen. Dieses Modul LIEST sie (und die kleine
Übersicht ``~/foto_sortierung/beziehungen.json``) und macht daraus

  * einen Tagesbefund (:func:`aussagen_fuer_datum`) für ein Datum — wie viele
    Aussagen belegbar sind und welche,
  * eine Chat-Anhängung (:func:`text_antwort`) für Fragen wie „was war am
    27.12.2019?"; fehlt die Datei, sagt der Text das ehrlich, statt zu raten,
  * eine Datumserkennung (:func:`datum_erkennen`) für deutsche und ISO-Formen,
  * einen Zustandsblock (:func:`status_block`) mit immer denselben Schlüsseln
    für das Selbsttest-Blatt.

Eiserne Regeln
--------------
  * **Kein Netz.** Kein ``httpx``/``requests``, kein pCloud-Aufruf, kein
    LLM-Aufruf. Gelesen werden ausschließlich die beiden lokalen Dateien.
  * **Keine Bilder.** Es wird keine Bilddatei geöffnet, kopiert oder
    gespeichert; die Dateien tragen nur Kennungen, Zahlen und Texte.
  * **Nie ein Wurf.** :func:`beziehungen_laden`, :func:`aussagen_fuer_datum`
    und :func:`status_block` fangen jeden Fehler ab und liefern deutsche
    ``error``-Texte. Defekte JSON-Zeilen sind eine Zählung, kein Abbruch.
  * **Nur lesend.** Beide Dateien werden ausschließlich gelesen; dieses Modul
    kennt **keine** Schreibfunktion.
  * **Keine Geheimnisse.** Ausgegeben werden Zahlen, Datum, Stand, der
    Dateiname der Quelle und das, was **in der Datei steht** — kein Schlüssel,
    kein Token. Ein Name wird nur genannt, wenn er in der Datei steht; es wird
    **nie** ein Name erfunden.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import date as _date
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Vorgabepfade: außerhalb des Repos, im selben Ordner wie der Sortierplan.
BEZIEHUNGEN_ORDNER = "foto_sortierung"
BEZIEHUNGEN_DATEINAME = "beziehungen.jsonl"
UEBERSICHT_DATEINAME = "beziehungen.json"

# Die Aussagen-Datei (JSONL, je Zeile eine Aussage).
STANDARD_PFAD = os.path.join(os.path.expanduser("~"), BEZIEHUNGEN_ORDNER,
                             BEZIEHUNGEN_DATEINAME)
# Die kleine Übersicht (JSON) mit den Kennzahlen.
STANDARD_UEBERSICHT = os.path.join(os.path.expanduser("~"), BEZIEHUNGEN_ORDNER,
                                   UEBERSICHT_DATEINAME)

# Erwarteter ``art``-Wert der Übersicht.
ERWARTETE_ART = "beziehungen"

# Die drei Aussage-Arten in fester Reihenfolge — die Reihenfolge der Anzeige
# entspricht der im Werkzeug ``beziehungen_ableiten.py`` (N27e).
UNTERART_FOTOS = "fotos"
UNTERART_CHAT = "gemeinsam_im_chat"
UNTERART_FOTOS_UND_CHAT = "fotos_und_chat"
UNTERART_REIHENFOLGE = (UNTERART_FOTOS, UNTERART_CHAT, UNTERART_FOTOS_UND_CHAT)
UNTERART_RANG = {name: stelle for stelle, name in enumerate(UNTERART_REIHENFOLGE)}

# Grenzen für ``limit``: unten 1 (eine leere Antwort ist keine Antwort), oben
# 200 (die Datei bleibt klein, ein Chat-Anhang darf es auch).
LIMIT_STANDARD = 50
LIMIT_MIN = 1
LIMIT_MAX = 200

# Für die Chat-Anhängung: höchstens so viele Aussagen zeigen und den Text hart
# begrenzen — ein Chat-Anhang darf nicht zum Roman werden.
TEXT_ANZAHL = 10
TEXT_MAX_ZEICHEN = 2000

# Der Schlusssatz jeder Antwort: die ehrliche Abgrenzung aus N27e.
ABGRENZUNG = ("Chat-Mitgliedschaft belegt keine Anwesenheit, Foto-Nähe keine "
              "Beziehung.")

# Deutsche Monatsnamen. ``märz`` und ``maerz`` sind beide erlaubt (der
# Schlüssel wird kleingeschrieben verglichen).
_MONATE = {
    "januar": 1, "februar": 2, "maerz": 3, "märz": 3, "april": 4, "mai": 5,
    "juni": 6, "juli": 7, "august": 8, "september": 9, "oktober": 10,
    "november": 11, "dezember": 12,
}

# Datumsmuster. Bewusst streng: nur ein vollständiges Datum öffnet das Tor,
# eine bloße Jahreszahl („2019") ergibt **kein** Datum.
_MUSTER_ISO = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
_MUSTER_MONAT = re.compile(r"\b(\d{1,2})\.\s*([A-Za-zÄÖÜäöüß]+)\s+(\d{4}|\d{2})\b")
_MUSTER_PUNKT = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4}|\d{2})\b")


# ── Pfade ────────────────────────────────────────────────────────────────────

def aussagen_pfad() -> str:
    """Ort der Aussagen-Datei (``beziehungen.jsonl``).

    Standard ist ``~/foto_sortierung/beziehungen.jsonl``; Tests biegen die
    Modulkonstante :data:`STANDARD_PFAD` über ``monkeypatch`` um.
    """
    return STANDARD_PFAD


def uebersicht_pfad() -> str:
    """Ort der Übersicht (``beziehungen.json``).

    Standard ist ``~/foto_sortierung/beziehungen.json``; Tests biegen die
    Modulkonstante :data:`STANDARD_UEBERSICHT` über ``monkeypatch`` um.
    """
    return STANDARD_UEBERSICHT


# ── kleine Helfer ────────────────────────────────────────────────────────────

def _als_zahl(wert: Any) -> Optional[int]:
    """Wert als ganze Zahl lesen — sonst ``None``.

    ``True``/``False`` gelten bewusst NICHT als Zahl (in JSON wäre ``true``
    sonst stillschweigend eine 1).
    """
    if isinstance(wert, bool):
        return None
    if isinstance(wert, int):
        return wert
    if isinstance(wert, float) and wert.is_integer():
        return int(wert)
    if isinstance(wert, str) and wert.strip():
        roh = wert.strip()
        if roh.lstrip("+-").isdigit():
            return int(roh)
    return None


def _text_oder_none(wert: Any) -> Optional[str]:
    """Wert als nicht-leeren Text lesen — sonst ``None``."""
    if isinstance(wert, str) and wert.strip():
        return wert.strip()
    return None


def _limit_begrenzen(limit: Any) -> int:
    """``limit`` auf :data:`LIMIT_MIN` … :data:`LIMIT_MAX` begrenzen.

    Unbrauchbare Eingaben (``None``, Text, 0) fallen auf
    :data:`LIMIT_STANDARD` bzw. die Untergrenze zurück — nie auf einen Fehler.
    """
    zahl = _als_zahl(limit)
    if zahl is None:
        return LIMIT_STANDARD
    return max(LIMIT_MIN, min(LIMIT_MAX, zahl))


# ── Datum erkennen ───────────────────────────────────────────────────────────

def _jahr_wert(roh: str) -> int:
    """Jahr aus Text: vierstellig wie angegeben, zweistellig als ``20xx``."""
    jahr = int(roh)
    if len(roh) == 2:
        jahr += 2000
    return jahr


def _datum_bauen(jahr: int, monat: int, tag: int) -> Optional[str]:
    """Aus Zahlen ein Datum ``JJJJ-MM-TT`` bauen — unplausible Tage → ``None``.

    Die Plausibilitätsprüfung läuft über :class:`datetime.date`; so wird
    ``31.02.2020`` zu ``None`` statt zu einem erfundenen Tag.
    """
    try:
        gueltig = _date(jahr, monat, tag)
    except (ValueError, OverflowError):
        return None
    return f"{gueltig.year:04d}-{gueltig.month:02d}-{gueltig.day:02d}"


def datum_erkennen(text: Any) -> Optional[str]:
    """Deutsches/ISO-Datum aus einem Text ziehen — sonst ``None``.

    Erkannt werden **nur eindeutige** Datumsangaben:

      * ``2019-12-27`` (ISO),
      * ``27.12.2019`` und ``27.12.19`` (zweistelliges Jahr wird ``20xx``),
      * ``27. Dezember 2019`` (deutsche Monatsnamen, ``märz`` und ``maerz``),
      * ``am 3.1.2022`` (das Wort davor stört nicht).

    Eine bloße Jahreszahl (``2019``) ergibt ``None`` — es wird kein Tag
    erfunden. Ein unplausibles Datum (``31.02.2020``, ``99.99.9999``) ergibt
    ebenfalls ``None``. Diese Funktion wirft nie.
    """
    if not isinstance(text, str) or not text.strip():
        return None

    # 1) ISO: JJJJ-MM-TT
    for treffer in _MUSTER_ISO.finditer(text):
        gebaut = _datum_bauen(int(treffer.group(1)), int(treffer.group(2)),
                              int(treffer.group(3)))
        if gebaut:
            return gebaut

    # 2) Tag. Monatsname Jahr
    for treffer in _MUSTER_MONAT.finditer(text):
        monat = _MONATE.get(treffer.group(2).strip().lower())
        if monat is None:
            continue
        gebaut = _datum_bauen(_jahr_wert(treffer.group(3)), monat,
                              int(treffer.group(1)))
        if gebaut:
            return gebaut

    # 3) Tag.Monat.Jahr
    for treffer in _MUSTER_PUNKT.finditer(text):
        gebaut = _datum_bauen(_jahr_wert(treffer.group(3)), int(treffer.group(2)),
                              int(treffer.group(1)))
        if gebaut:
            return gebaut

    return None


# ── Aussagen-Datei lesen ─────────────────────────────────────────────────────

def _aussagen_lesen(pfad: str, datum: Optional[str] = None,
                    ) -> Tuple[List[Dict[str, Any]], int]:
    """Aussage-Zeilen lesen — defekte Zeilen werden gezählt, nicht geworfen.

    Gibt ``(aussagen, defekt)`` zurück. Ist ``datum`` gesetzt, werden nur
    Zeilen mit genau diesem ``datum`` behalten. Eine Zeile, die kein JSON ist
    oder kein Objekt ergibt, erhöht nur ``defekt``; I/O-Fehler reicht die
    Funktion an den Aufrufer weiter, der sie in einen deutschen Text wandelt.
    """
    aussagen: List[Dict[str, Any]] = []
    defekt = 0
    with open(pfad, "r", encoding="utf-8") as datei:
        for zeile in datei:
            zeile = zeile.strip()
            if not zeile:
                continue
            try:
                eintrag = json.loads(zeile)
            except ValueError:
                defekt += 1
                continue
            if not isinstance(eintrag, dict):
                defekt += 1
                continue
            if datum is not None and eintrag.get("datum") != datum:
                continue
            aussagen.append(eintrag)
    return aussagen, defekt


def _aussagen_sortieren(aussagen: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Nach Unterart-Reihenfolge (fotos → chat → kreuz), dann ``anlass_id``."""
    def _rang(eintrag: Dict[str, Any]) -> Tuple[int, str]:
        unterart = eintrag.get("unterart")
        stelle = UNTERART_RANG.get(unterart) if isinstance(unterart, str) else None
        return (stelle if stelle is not None else len(UNTERART_REIHENFOLGE),
                str(eintrag.get("anlass_id") or ""))

    return sorted(aussagen, key=_rang)


# ── Tagesbefund ──────────────────────────────────────────────────────────────

def aussagen_fuer_datum(datum: Any, limit: int = LIMIT_STANDARD) -> Dict[str, Any]:
    """Alle belegbaren Aussagen eines Tages — **immer dieselben Schlüssel**.

    ``datum`` (normalisiert ``JJJJ-MM-TT``), ``gueltig``, ``anzahl``
    (Gesamtzahl des Tages **vor** dem Limit), ``anzahl_je_unterart``,
    ``aussagen`` (höchstens ``limit``, sortiert nach Unterart-Reihenfolge und
    dann ``anlass_id``), ``gekuerzt``, ``error``.

    Ein unplausibles Datum ergibt ``gueltig: False`` und einen deutschen
    ``error`` — **kein Wurf**. Ein Tag **ohne** Aussagen ist **kein** Fehler:
    ``gueltig: True``, ``anzahl: 0``. Fehlt die Datei, steht das als deutscher
    ``error`` drin.
    """
    ergebnis: Dict[str, Any] = {
        "datum": None,
        "gueltig": False,
        "anzahl": 0,
        "anzahl_je_unterart": {name: 0 for name in UNTERART_REIHENFOLGE},
        "aussagen": [],
        "gekuerzt": False,
        "error": None,
    }

    normalisiert = datum_erkennen(datum)
    if normalisiert is None:
        ergebnis["error"] = (
            f"Kein gültiges Datum erkannt ({datum!r}); erwartet wird ein Tag "
            "wie 27.12.2019 oder 2019-12-27."
        )
        return ergebnis

    ergebnis["datum"] = normalisiert
    ergebnis["gueltig"] = True

    try:
        pfad = aussagen_pfad()
    except Exception as e:  # noqa: BLE001 – nie ein Wurf nach außen
        logger.warning("Beziehungen: Pfad nicht bestimmbar (%s).", type(e).__name__)
        ergebnis["error"] = f"Beziehungen: Pfad nicht bestimmbar ({type(e).__name__})"
        return ergebnis

    try:
        if not os.path.isfile(pfad):
            ergebnis["error"] = (
                f"Beziehungen liegen noch auf dem PC ({BEZIEHUNGEN_DATEINAME} "
                "nicht gefunden; die Datei entsteht mit beziehungen_ableiten.py)."
            )
            return ergebnis
        gefunden, _defekt = _aussagen_lesen(pfad, normalisiert)
    except OSError as e:
        logger.warning("Beziehungen nicht lesbar (%s): %s", pfad, e)
        ergebnis["error"] = f"Beziehungen nicht lesbar ({type(e).__name__})"
        return ergebnis
    except Exception as e:  # noqa: BLE001 – nie ein Wurf nach außen
        logger.warning("Beziehungen nicht auswertbar: %s", e)
        ergebnis["error"] = f"Beziehungen nicht auswertbar ({type(e).__name__})"
        return ergebnis

    gefunden = _aussagen_sortieren(gefunden)

    je_unterart = {name: 0 for name in UNTERART_REIHENFOLGE}
    for eintrag in gefunden:
        unterart = eintrag.get("unterart")
        if isinstance(unterart, str) and unterart:
            je_unterart[unterart] = je_unterart.get(unterart, 0) + 1

    grenze = _limit_begrenzen(limit)
    ergebnis["anzahl"] = len(gefunden)
    ergebnis["anzahl_je_unterart"] = je_unterart
    ergebnis["aussagen"] = gefunden[:grenze]
    ergebnis["gekuerzt"] = len(gefunden) > grenze
    return ergebnis


# ── Übersicht lesen ──────────────────────────────────────────────────────────

def beziehungen_laden(pfad: Optional[str] = None,
                      uebersicht: Optional[str] = None) -> Dict[str, Any]:
    """Kennzahlen der Beziehungen lesen. **Wirft nie.**

    Rückgabe hat immer dieselben Schlüssel: ``pfad``, ``existiert``, ``stand``,
    ``anzahl`` (dict je Unterart), ``anzahl_gesamt``, ``datum_von``,
    ``datum_bis``, ``anzahl_personen_kennungen``, ``anzahl_namen_bestaetigt``,
    ``anzahl_kontakte``, ``error``.

    Die Kennzahlen kommen aus der **Übersicht** (``beziehungen.json``); die
    Aussagen selbst werden nicht in dieses dict geladen. Fehlt die
    Aussagen-Datei oder die Übersicht, ist ``existiert`` falsch und ``error``
    trägt einen deutschen Text (kein Wurf).

    ``pfad``/``uebersicht`` übersteuern die Vorgabeorte; ohne Angabe gelten
    :func:`aussagen_pfad` und :func:`uebersicht_pfad`.
    """
    ergebnis: Dict[str, Any] = {
        "pfad": None,
        "existiert": False,
        "stand": None,
        "anzahl": {},
        "anzahl_gesamt": None,
        "datum_von": None,
        "datum_bis": None,
        "anzahl_personen_kennungen": None,
        "anzahl_namen_bestaetigt": None,
        "anzahl_kontakte": None,
        "error": None,
    }

    try:
        aussagen_ziel = pfad if pfad and str(pfad).strip() else aussagen_pfad()
        uebersicht_ziel = (uebersicht if uebersicht and str(uebersicht).strip()
                           else uebersicht_pfad())
    except Exception as e:  # noqa: BLE001 – nie ein Wurf nach außen
        logger.warning("Beziehungen: Pfad nicht bestimmbar (%s).", type(e).__name__)
        ergebnis["error"] = f"Beziehungen: Pfad nicht bestimmbar ({type(e).__name__})"
        return ergebnis

    ergebnis["pfad"] = aussagen_ziel

    if not os.path.isfile(aussagen_ziel):
        ergebnis["error"] = (
            f"Beziehungen liegen noch auf dem PC ({BEZIEHUNGEN_DATEINAME} nicht "
            "gefunden; die Datei entsteht mit beziehungen_ableiten.py)."
        )
        return ergebnis

    try:
        with open(uebersicht_ziel, "r", encoding="utf-8") as datei:
            daten = json.load(datei)
    except OSError as e:
        logger.warning("Beziehungen-Übersicht nicht lesbar (%s): %s", uebersicht_ziel, e)
        ergebnis["error"] = f"Beziehungen-Übersicht nicht lesbar ({type(e).__name__})"
        return ergebnis
    except UnicodeDecodeError:
        ergebnis["error"] = "Beziehungen-Übersicht ist nicht als UTF-8 lesbar"
        return ergebnis
    except ValueError:
        ergebnis["error"] = "Beziehungen-Übersicht ist kein gültiges JSON"
        return ergebnis
    except Exception as e:  # noqa: BLE001 – nie ein Wurf nach außen
        logger.warning("Beziehungen-Übersicht nicht auswertbar (%s): %s",
                       uebersicht_ziel, e)
        ergebnis["error"] = f"Beziehungen-Übersicht nicht auswertbar ({type(e).__name__})"
        return ergebnis

    if not isinstance(daten, dict):
        ergebnis["error"] = "Beziehungen-Übersicht hat ein unerwartetes Format (kein Objekt)"
        return ergebnis

    art = daten.get("art")
    if art is not None and art != ERWARTETE_ART:
        ergebnis["error"] = f"Beziehungen-Übersicht hat eine unerwartete Art ({art})"
        return ergebnis

    ergebnis["existiert"] = True
    ergebnis["stand"] = _text_oder_none(daten.get("stand"))

    anzahl = daten.get("anzahl")
    if isinstance(anzahl, dict):
        ergebnis["anzahl"] = {str(schluessel): _als_zahl(wert)
                              for schluessel, wert in anzahl.items()}
    zahlen = [wert for wert in ergebnis["anzahl"].values() if isinstance(wert, int)]
    ergebnis["anzahl_gesamt"] = sum(zahlen) if zahlen else None

    ergebnis["datum_von"] = _text_oder_none(daten.get("datum_von"))
    ergebnis["datum_bis"] = _text_oder_none(daten.get("datum_bis"))
    ergebnis["anzahl_personen_kennungen"] = _als_zahl(daten.get("anzahl_personen_kennungen"))
    ergebnis["anzahl_namen_bestaetigt"] = _als_zahl(daten.get("anzahl_namen_bestaetigt"))
    ergebnis["anzahl_kontakte"] = _als_zahl(daten.get("anzahl_kontakte"))
    return ergebnis


# ── Zustandsblock für den Selbsttest ─────────────────────────────────────────

def status_block() -> Dict[str, Any]:
    """Zustand der Beziehungen — **immer dieselben Schlüssel**.

    ``quelle`` (Dateiname), ``pfad``, ``existiert``, ``stand``, ``aussagen``,
    ``personen_kennungen``, ``namen_bestaetigt``, ``kontakte``, ``datum_von``,
    ``datum_bis``, ``error``. ``quelle`` ist der Dateiname der Aussagen-Datei
    ohne Verzeichnis und steht auch dann darin, wenn die Datei fehlt. Alle
    Fehler landen als deutscher Text in ``error`` — diese Funktion wirft nie.
    """
    block: Dict[str, Any] = {
        "quelle": None,
        "pfad": None,
        "existiert": False,
        "stand": None,
        "aussagen": None,
        "personen_kennungen": None,
        "namen_bestaetigt": None,
        "kontakte": None,
        "datum_von": None,
        "datum_bis": None,
        "error": None,
    }

    try:
        pfad = aussagen_pfad()
    except Exception as e:  # noqa: BLE001 – nie ein Wurf
        logger.warning("Beziehungen: Pfad nicht bestimmbar (%s).", type(e).__name__)
        block["error"] = f"Beziehungen: Pfad nicht bestimmbar ({type(e).__name__})"
        return block

    block["pfad"] = pfad
    block["quelle"] = os.path.basename(pfad) or BEZIEHUNGEN_DATEINAME

    daten = beziehungen_laden(pfad)
    block["existiert"] = bool(daten.get("existiert"))
    block["error"] = daten.get("error")
    if not block["existiert"]:
        return block

    block["stand"] = daten.get("stand")
    block["aussagen"] = daten.get("anzahl_gesamt")
    block["personen_kennungen"] = daten.get("anzahl_personen_kennungen")
    block["namen_bestaetigt"] = daten.get("anzahl_namen_bestaetigt")
    block["kontakte"] = daten.get("anzahl_kontakte")
    block["datum_von"] = daten.get("datum_von")
    block["datum_bis"] = daten.get("datum_bis")
    return block


# ── Chat-Anhängung ───────────────────────────────────────────────────────────

_UNTERART_TITEL = {
    UNTERART_FOTOS: "Fotos",
    UNTERART_CHAT: "Gemeinsam im Chat",
    UNTERART_FOTOS_UND_CHAT: "Fotos und Chat",
}


def _unterart_titel(unterart: Any) -> str:
    """Überschrift je Unterart — unbekannte Arten bleiben neutral."""
    return _UNTERART_TITEL.get(unterart, "Aussagen")


def _personen_text(personen: Any) -> str:
    """Personen einer Zeile als Text: Kennung, Name nur wenn vorhanden.

    Ein Name wird **nur** genannt, wenn er in der Datei steht (nicht ``null``);
    es wird nie ein Name erfunden. Ohne Kennung und ohne Namen bleibt die
    Person weg.
    """
    if not isinstance(personen, list):
        return ""
    teile: List[str] = []
    for person in personen:
        if not isinstance(person, dict):
            continue
        kennung = _text_oder_none(person.get("kennung"))
        name = _text_oder_none(person.get("name"))
        if kennung and name:
            teile.append(f"{kennung} ({name})")
        elif kennung:
            teile.append(kennung)
        elif name:
            teile.append(name)
    return ", ".join(teile)


def _aussage_zeile(eintrag: Dict[str, Any]) -> str:
    """Eine Aussage als Chat-Zeile: Datum, Thema/Kategorie, Personen."""
    teile: List[str] = [_text_oder_none(eintrag.get("datum")) or "?"]
    thema = _text_oder_none(eintrag.get("thema"))
    kategorie = _text_oder_none(eintrag.get("kategorie"))
    if thema:
        teile.append(thema)
    if kategorie:
        teile.append(kategorie)
    personen = _personen_text(eintrag.get("personen"))
    if personen:
        teile.append(personen)
    return " · ".join(teile)


def text_antwort(datum: Any) -> str:
    """Deutscher Text für die Chat-Anhängung zu einem Tag.

    Kopfzeile mit dem Datum, die Zahl der belegbaren Aussagen je Unterart, die
    ersten Aussagen (:data:`TEXT_ANZAHL`) mit Thema/Kategorie und Personen
    sowie **der ``hinweis`` der Zeilen wörtlich** — je Unterart einmal, denn
    der Hinweis ist innerhalb einer Unterart gleich. Am Ende steht **immer**
    die Abgrenzung :data:`ABGRENZUNG`. Ein Tag ohne Aussagen ergibt einen
    ehrlichen Satz, dass keine Andockung vorliegt. Fehlt die Datei, nennt der
    Text, dass sie noch auf dem PC liegt. Der Text ist auf
    :data:`TEXT_MAX_ZEICHEN` Zeichen begrenzt.
    """
    try:
        pfad = aussagen_pfad()
    except Exception as e:  # noqa: BLE001 – nie ein Wurf
        logger.warning("Beziehungen: Pfad nicht bestimmbar (%s).", type(e).__name__)
        return ("\n\n[Beziehungen (N28): Der Ablageort der Beziehungsdaten ist "
                "nicht bestimmbar. Sag das ehrlich — erfinde keine Aussagen.]")

    if not os.path.isfile(pfad):
        return ("\n\n[Beziehungen (N28): Die Datei beziehungen.jsonl liegt noch "
                "auf dem PC; hier ist sie nicht lesbar. Sag dem Nutzer ehrlich, "
                "dass die Beziehungsdaten noch übertragen werden müssen — "
                "erfinde keine Aussagen.]")

    daten = aussagen_fuer_datum(datum, limit=TEXT_ANZAHL)

    if not daten.get("gueltig"):
        return ("\n\n[Beziehungen (N28): Es war kein gültiges Datum zu erkennen. "
                "Nenne dem Nutzer keine erfundenen Aussagen.]")

    if daten.get("error"):
        return (f"\n\n[Beziehungen (N28): {daten['error']} Sag das ehrlich — "
                "erfinde keine Aussagen.]")

    stand = None
    try:
        stand = beziehungen_laden().get("stand")
    except Exception:  # noqa: BLE001 – ein Stand ist Beiwerk, kein Grund zum Wurf
        stand = None

    kopf = "\n\n[Beziehungen (N28, Quelle beziehungen.jsonl"
    if stand:
        kopf += f", Stand {stand}"
    anzahl = daten["anzahl"]
    je_unterart = daten["anzahl_je_unterart"]
    verteilung = " · ".join(f"{name} {je_unterart.get(name, 0)}"
                            for name in UNTERART_REIHENFOLGE)
    kopf += f"): Am {daten['datum']} sind {anzahl} Aussagen belegbar ({verteilung})."

    if anzahl == 0:
        return (kopf + " An diesem Tag liegt keine Andockung vor — das ist kein "
                       f"Fehler, sondern der Befund aus der Datei. {ABGRENZUNG}]")

    gezeigt = daten["aussagen"]
    if daten.get("gekuerzt"):
        kopf += f" Gezeigt werden die ersten {len(gezeigt)} von {anzahl}."

    zeilen: List[str] = [kopf]
    letzte_unterart: Any = object()
    for eintrag in gezeigt:
        unterart = eintrag.get("unterart")
        if unterart != letzte_unterart:
            zeilen.append(f"  [{_unterart_titel(unterart)}]")
            hinweis = _text_oder_none(eintrag.get("hinweis"))
            if hinweis:
                zeilen.append(f"  Hinweis: {hinweis}")
            letzte_unterart = unterart
        zeilen.append("  " + _aussage_zeile(eintrag))
    zeilen.append(ABGRENZUNG + "]")

    text = "\n".join(zeilen)
    if len(text) > TEXT_MAX_ZEICHEN:
        text = text[:TEXT_MAX_ZEICHEN - 1].rstrip() + "]"
    return text
