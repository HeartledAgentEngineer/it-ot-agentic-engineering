"""Erzähl-Diashow (Auftrag E8a, 28.09.2026) — Dienst: Ereignisse lesen,
Geschichten anhängen.

Warum es diesen Dienst gibt
---------------------------
Sebastian wählt in der App ein Ereignis, klickt sich durch die Diashow der
Bilder und erzählt zu jedem Bild (tippen oder Mikrofon). Die Ereignisse
selbst liegen als eingefrorenes Schema in ``ereignisse.jsonl`` (gebaut von
``tools/foto_sortierung/ereignisse_bauen.py``, nur PC). Die Geschichten dazu
sind Sebastians eigene Worte — sie werden in einer zweiten Datei
``geschichten.jsonl`` als **Schicht "mensch"** nur angehängt.

Eiserne Regeln (aus dem Auftrag, bindend)
------------------------------------------
  * **Nur lesend** bei ``ereignisse.jsonl``. Defekte Zeilen werden gezählt,
    nicht geworfen.
  * **Nur anhängend** bei ``geschichten.jsonl`` — nie neu schreiben, nie
    löschen (``open(..., "a")`` + ``flush`` + ``os.fsync``).
  * Anker einer Geschichte ist die **Bildkennung** plus ein Schnappschuss von
    Ereignis-Datum/-Titel — das übersteht jede Neuberechnung der Ereignisse.
  * **Korrektur** = neue Zeile mit ``ersetzt: <alte id>``. Beim Lesen liefert
    :func:`geschichten` nur die jeweils neueste Fassung.
  * **Kein Netz.** Es wird ausschließlich lokal gelesen/geschrieben.
  * **Keine Geheimnisse.** Es werden nur Ereignis-/Geschichtendaten
    verarbeitet — kein Schlüssel, kein Token.

Pfade sind über Umgebungsvariablen übersteuerbar (Tests, anderes Gerät):
``ERZAEHL_EREIGNISSE_PFAD`` und ``ERZAEHL_GESCHICHTEN_PFAD``.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Pfade ────────────────────────────────────────────────────────────────────

ERZAEHL_ORDNER = "foto_sortierung"
EREIGNISSE_DATEINAME = "ereignisse.jsonl"
GESCHICHTEN_DATEINAME = "geschichten.jsonl"

SCHICHT_MENSCH = "mensch"
SCHICHT_VERSION = 1

# Erlaubte Quellen einer Geschichte. "import" (Nachtrag 28.09.2026, Planer-
# Auftrag): spätere Übernahme von Erzählungen aus Hermes. Über die
# Oberfläche werden weiterhin nur "tippen"/"sprache" gesetzt — die
# POST-Validierung akzeptiert zusätzlich "import".
QUELLEN_ERLAUBT = ("tippen", "sprache", "import")

TEXT_MAX_LAENGE = 20_000

LIMIT_STANDARD = 200
LIMIT_MIN = 1
LIMIT_MAX = 500

_UMLAUTE = (
    ("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"),
    ("Ä", "ae"), ("Ö", "oe"), ("Ü", "ue"),
)


def ereignisse_pfad() -> str:
    """Ort der (nur lesenden) Ereignisdatei.

    Standard ``~/foto_sortierung/ereignisse.jsonl``, über
    ``ERZAEHL_EREIGNISSE_PFAD`` übersteuerbar (leer/nur Leerzeichen zählt
    nicht).
    """
    ueber = os.environ.get("ERZAEHL_EREIGNISSE_PFAD")
    if ueber and ueber.strip():
        return ueber.strip()
    return os.path.join(os.path.expanduser("~"), ERZAEHL_ORDNER, EREIGNISSE_DATEINAME)


def geschichten_pfad() -> str:
    """Ort der (nur anhängenden) Geschichten-Datei.

    Standard ``~/foto_sortierung/geschichten.jsonl``, über
    ``ERZAEHL_GESCHICHTEN_PFAD`` übersteuerbar (leer/nur Leerzeichen zählt
    nicht).
    """
    ueber = os.environ.get("ERZAEHL_GESCHICHTEN_PFAD")
    if ueber and ueber.strip():
        return ueber.strip()
    return os.path.join(os.path.expanduser("~"), ERZAEHL_ORDNER, GESCHICHTEN_DATEINAME)


# ── kleine Helfer ────────────────────────────────────────────────────────────

def _als_zahl(wert: Any) -> Optional[int]:
    """Wert als ganze Zahl lesen — sonst ``None`` (``bool`` zählt nie)."""
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


def _normalisieren(text: Any) -> str:
    """Text für den Vergleich vereinheitlichen (klein, Umlaute aufgelöst)."""
    if text is None:
        return ""
    zeichenkette = str(text).strip().lower()
    for umlaut, ersatz in _UMLAUTE:
        zeichenkette = zeichenkette.replace(umlaut, ersatz)
    return zeichenkette


def _limit_begrenzen(limit: Any) -> int:
    wert = _als_zahl(limit)
    if wert is None:
        return LIMIT_STANDARD
    return max(LIMIT_MIN, min(LIMIT_MAX, wert))


def _offset_begrenzen(offset: Any) -> int:
    wert = _als_zahl(offset)
    if wert is None or wert < 0:
        return 0
    return wert


def _titel_aus(ereignis: Dict[str, Any]) -> str:
    """Titel-Rückfall: ``event``, sonst ``thema``, sonst „Ohne Titel"."""
    for feld in ("event", "thema"):
        wert = ereignis.get(feld)
        if isinstance(wert, str) and wert.strip():
            return wert.strip()
    return "Ohne Titel"


def _jetzt_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


# ── Eigene Anlass-Titel (06.10.2026) ─────────────────────────────────────────
# Sebastian benennt Anlässe im Erzählen selbst; der Name gewinnt vor dem
# automatischen Titel und wird später zum Ordnernamen beim Sortieren (Plan
# Schritt 3). Nur anhängend wie die Geschichten: je Kennung gilt die neueste
# Zeile, ein leerer Name setzt auf den automatischen Titel zurück.

TITEL_DATEINAME = "anlass_umbenennung.jsonl"
TITEL_MAX_LAENGE = 120


def titel_pfad() -> str:
    """``anlass_umbenennung.jsonl`` im Ordner der Geschichten (Tests leiten ihn mit um)."""
    return os.path.join(os.path.dirname(geschichten_pfad()), TITEL_DATEINAME)


def eigene_titel() -> Dict[str, str]:
    """``{kennung: name}`` — neueste Zeile je Kennung, leerer Name = zurückgesetzt. **Wirft nie.**"""
    pfad = titel_pfad()
    if not os.path.isfile(pfad):
        return {}
    namen: Dict[str, str] = {}
    try:
        with open(pfad, "r", encoding="utf-8") as datei:
            for roh in datei:
                try:
                    eintrag = json.loads(roh)
                except ValueError:
                    continue
                if not isinstance(eintrag, dict):
                    continue
                kennung, name = eintrag.get("kennung"), eintrag.get("name")
                if isinstance(kennung, str) and kennung and isinstance(name, str):
                    namen[kennung] = name.strip()
    except OSError as e:
        logger.warning("Eigene Titel nicht lesbar (%s): %s", pfad, e)
        return {}
    return {k: n for k, n in namen.items() if n}


def _titel_fuer(ereignis: Dict[str, Any], eigene: Dict[str, str]) -> Tuple[str, bool]:
    """(gültiger Titel, eigener?) — der eigene Name gewinnt vor dem automatischen."""
    name = eigene.get(ereignis.get("kennung") or "")
    if name:
        return name, True
    return _titel_aus(ereignis), False


# ── Ereignisse lesen (nur lesend) ────────────────────────────────────────────

FOTOBUCH_DATEINAME = "fotobuch_ereignisse.jsonl"


def fotobuch_pfad() -> str:
    """Seiten des digitalen Fotobuchs (tools/foto_sortierung/fotobuch_lesen.py, 02.10.2026).

    Liegt im selben Ordner wie ``ereignisse.jsonl`` (Standard
    ``~/foto_sortierung/``; leitet ein Test den Ereignis-Pfad um, wandert das
    Fotobuch mit — echte Daten werden so nie versehentlich gelesen),
    übersteuerbar mit ``ERZAEHL_FOTOBUCH_PFAD``. Zeilenformat wie ``ereignisse.jsonl``.
    """
    ueber = os.environ.get("ERZAEHL_FOTOBUCH_PFAD")
    if ueber and ueber.strip():
        return ueber.strip()
    return os.path.join(os.path.dirname(ereignisse_pfad()), FOTOBUCH_DATEINAME)


def _ereignisse_laden() -> Tuple[List[Dict[str, Any]], int]:
    """Fotobuch-Seiten (zuerst, in Buchreihenfolge) + ``ereignisse.jsonl``. **Wirft nie.**"""
    buch, defekt_buch = _datei_ereignisse_laden(fotobuch_pfad())
    rest, defekt_rest = _datei_ereignisse_laden(ereignisse_pfad())
    return buch + rest, defekt_buch + defekt_rest


def _datei_ereignisse_laden(pfad: str) -> Tuple[List[Dict[str, Any]], int]:
    """Eine Ereignis-JSONL zeilenweise lesen. **Wirft nie.**

    Liefert ``(gültige_ereignisse, defekte_zeilen)``. Fehlt die Datei, ist
    das Ergebnis ``([], 0)`` — kein Fehler, die App soll ehrlich „noch nicht
    vorhanden" melden können (das übernimmt der Router).
    """
    ereignisse: List[Dict[str, Any]] = []
    defekt = 0

    if not os.path.isfile(pfad):
        return ereignisse, defekt

    try:
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
                kennung = eintrag.get("kennung")
                if not isinstance(kennung, str) or not kennung.strip():
                    defekt += 1
                    continue
                ereignisse.append(eintrag)
    except OSError as e:
        logger.warning("Ereignisdatei nicht lesbar (%s): %s", pfad, e)
        return [], 0

    return ereignisse, defekt


def _ereignis_datei_kennungen(ereignis: Dict[str, Any]) -> List[int]:
    liste = ereignis.get("datei_kennungen")
    if not isinstance(liste, list):
        return []
    ergebnis: List[int] = []
    for wert in liste:
        zahl = _als_zahl(wert)
        if zahl is not None:
            ergebnis.append(zahl)
    return ergebnis


def ereignisse_existiert() -> bool:
    """Liegt eine Ereignisquelle vor (Ereignisse oder Fotobuch)? (für den Router-Fehlertext)."""
    return os.path.isfile(ereignisse_pfad()) or os.path.isfile(fotobuch_pfad())


def _ereignis_finden(kennung: str) -> Optional[Dict[str, Any]]:
    if not isinstance(kennung, str) or not kennung.strip():
        return None
    ereignisse, _ = _ereignisse_laden()
    for eintrag in ereignisse:
        if eintrag.get("kennung") == kennung:
            return eintrag
    return None


# ── Geschichten lesen (Schicht "mensch") ─────────────────────────────────────

def _geschichten_laden() -> List[Dict[str, Any]]:
    """Alle Zeilen aus ``geschichten.jsonl``. **Wirft nie.**

    Defekte Zeilen werden übersprungen (die Datei wird nur von diesem
    Dienst geschrieben, defekte Zeilen sind hier kein zu meldender
    Normalfall wie bei den Ereignissen — trotzdem kein Absturz).
    """
    pfad = geschichten_pfad()
    if not os.path.isfile(pfad):
        return []
    zeilen: List[Dict[str, Any]] = []
    try:
        with open(pfad, "r", encoding="utf-8") as datei:
            for roh in datei:
                roh = roh.strip()
                if not roh:
                    continue
                try:
                    eintrag = json.loads(roh)
                except ValueError:
                    continue
                if isinstance(eintrag, dict) and isinstance(eintrag.get("id"), str):
                    zeilen.append(eintrag)
    except OSError as e:
        logger.warning("Geschichten nicht lesbar (%s): %s", pfad, e)
        return []
    return zeilen


def _neueste_fassungen(zeilen: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Nur die jeweils neueste Fassung liefern.

    Eine Zeile gilt als ERSETZT, sobald irgendeine andere Zeile sie über
    ``ersetzt`` referenziert — unabhängig davon, an welchem Ereignis/Bild
    sie hängt.
    """
    ersetzte_ids = {
        eintrag.get("ersetzt")
        for eintrag in zeilen
        if isinstance(eintrag.get("ersetzt"), str) and eintrag.get("ersetzt")
    }
    return [eintrag for eintrag in zeilen if eintrag.get("id") not in ersetzte_ids]


def geschichten(ereignis_kennung: Optional[str] = None,
                datei_kennung: Optional[int] = None) -> List[Dict[str, Any]]:
    """Geschichten (nur neueste Fassung), optional gefiltert.

    Ohne Filter kommen alle aktuellen Geschichten zurück. **Wirft nie** —
    fehlt die Datei, ist das Ergebnis eine leere Liste.
    """
    alle = _neueste_fassungen(_geschichten_laden())
    ek = ereignis_kennung.strip() if isinstance(ereignis_kennung, str) else None
    dk = _als_zahl(datei_kennung) if datei_kennung is not None else None

    ergebnis: List[Dict[str, Any]] = []
    for eintrag in alle:
        if ek and eintrag.get("ereignis_kennung") != ek:
            continue
        if dk is not None and _als_zahl(eintrag.get("datei_kennung")) != dk:
            continue
        ergebnis.append(eintrag)
    return ergebnis


# ── Ereignisliste / -detail ──────────────────────────────────────────────────

def ereignisse_liste(jahr: Any = None, suche: Any = None, min_bilder: Any = 1,
                     limit: Any = LIMIT_STANDARD, offset: Any = 0) -> Dict[str, Any]:
    """Gefilterte Ereignisliste fürs Frontend.

    Liefert ``{"eintraege": [...], "gesamt": n, "defekte_zeilen": n}``. Jeder
    Eintrag trägt ``kennung, datum, jahr, titel, kategorie, anzahl_dateien,
    vorschau_kennungen (erste 4), anzahl_geschichten``. **Wirft nie.**
    """
    ereignisse, defekt = _ereignisse_laden()

    jahr_wert = _als_zahl(jahr)
    suche_wert = _normalisieren(suche) or None
    min_bilder_wert = _als_zahl(min_bilder)
    if min_bilder_wert is None or min_bilder_wert < 0:
        min_bilder_wert = 1
    grenze = _limit_begrenzen(limit)
    versatz = _offset_begrenzen(offset)

    eigene = eigene_titel()
    alle_geschichten = _neueste_fassungen(_geschichten_laden())
    geschichten_je_ereignis: Dict[str, int] = {}
    for eintrag in alle_geschichten:
        ek = eintrag.get("ereignis_kennung")
        if isinstance(ek, str) and ek:
            geschichten_je_ereignis[ek] = geschichten_je_ereignis.get(ek, 0) + 1

    treffer: List[Dict[str, Any]] = []
    for ereignis in ereignisse:
        kennung = ereignis.get("kennung")
        if not isinstance(kennung, str) or not kennung.strip():
            continue

        dateien = _ereignis_datei_kennungen(ereignis)
        anzahl_dateien = _als_zahl(ereignis.get("anzahl_dateien"))
        if anzahl_dateien is None:
            anzahl_dateien = len(dateien)
        if anzahl_dateien < min_bilder_wert:
            continue

        if jahr_wert is not None and _als_zahl(ereignis.get("jahr")) != jahr_wert:
            continue

        titel, titel_eigen = _titel_fuer(ereignis, eigene)
        automatisch = _titel_aus(ereignis)
        if suche_wert is not None and suche_wert not in _normalisieren(titel) \
                and suche_wert not in _normalisieren(automatisch):
            continue

        treffer.append({
            "kennung": kennung,
            "datum": ereignis.get("datum") if isinstance(ereignis.get("datum"), str) else None,
            "jahr": _als_zahl(ereignis.get("jahr")),
            "titel": titel,
            "titel_eigen": titel_eigen,
            "titel_automatisch": automatisch,
            "kategorie": ereignis.get("kategorie") if isinstance(ereignis.get("kategorie"), str) else None,
            "anzahl_dateien": anzahl_dateien,
            "vorschau_kennungen": dateien[:4],
            "anzahl_geschichten": geschichten_je_ereignis.get(kennung, 0),
        })

    gesamt = len(treffer)
    seite = treffer[versatz:versatz + grenze]
    return {"eintraege": seite, "gesamt": gesamt, "defekte_zeilen": defekt}


def ereignis_detail(kennung: str) -> Optional[Dict[str, Any]]:
    """Ein Ereignis mit allen Datei-Kennungen und seinen Geschichten.

    ``None``, wenn die Kennung unbekannt ist (oder die Datei fehlt) —
    der Router macht daraus einen ehrlichen Fehlertext.
    """
    ereignis = _ereignis_finden(kennung)
    if ereignis is None:
        return None

    dateien = _ereignis_datei_kennungen(ereignis)
    titel, titel_eigen = _titel_fuer(ereignis, eigene_titel())
    return {
        "kennung": ereignis.get("kennung"),
        "datum": ereignis.get("datum") if isinstance(ereignis.get("datum"), str) else None,
        "jahr": _als_zahl(ereignis.get("jahr")),
        "titel": titel,
        "titel_eigen": titel_eigen,
        "titel_automatisch": _titel_aus(ereignis),
        "kategorie": ereignis.get("kategorie") if isinstance(ereignis.get("kategorie"), str) else None,
        "anzahl_dateien": _als_zahl(ereignis.get("anzahl_dateien")) or len(dateien),
        "datei_kennungen": dateien,
        "geschichten": geschichten(ereignis_kennung=kennung),
    }


# ── Geschichte speichern (nur anhängend) ─────────────────────────────────────

class GeschichteValidierungsfehler(ValueError):
    """Eine POST-Eingabe verletzt eine Regel — deutscher Klartext im Text."""


def geschichte_speichern(ereignis_kennung: str, text: str, quelle: str,
                         datei_kennung: Optional[int] = None,
                         ersetzt: Optional[str] = None) -> Dict[str, Any]:
    """Eine neue Geschichte anhängen (Schicht "mensch").

    Validiert nach den Regeln aus dem Auftrag; wirft
    :class:`GeschichteValidierungsfehler` (deutscher Text) bei ungültiger
    Eingabe. Schreibt **nur anhängend** (``"a"`` + ``flush`` + ``fsync``) und
    liefert die geschriebene Zeile zurück.
    """
    text_wert = text.strip() if isinstance(text, str) else ""
    if not text_wert:
        raise GeschichteValidierungsfehler("Text darf nicht leer sein.")
    if len(text_wert) > TEXT_MAX_LAENGE:
        raise GeschichteValidierungsfehler(
            f"Text ist zu lang ({len(text_wert)} Zeichen, erlaubt sind höchstens "
            f"{TEXT_MAX_LAENGE})."
        )

    quelle_wert = quelle.strip() if isinstance(quelle, str) else ""
    if quelle_wert not in QUELLEN_ERLAUBT:
        raise GeschichteValidierungsfehler(
            f"Quelle '{quelle}' ist ungültig (erlaubt: "
            f"{', '.join(QUELLEN_ERLAUBT)})."
        )

    ek = ereignis_kennung.strip() if isinstance(ereignis_kennung, str) else ""
    if not ek:
        raise GeschichteValidierungsfehler("Ereignis-Kennung fehlt.")
    ereignis = _ereignis_finden(ek)
    if ereignis is None:
        raise GeschichteValidierungsfehler(f"Ereignis '{ek}' existiert nicht.")

    dk = _als_zahl(datei_kennung) if datei_kennung is not None else None
    if dk is not None:
        gueltige_dateien = _ereignis_datei_kennungen(ereignis)
        if dk not in gueltige_dateien:
            raise GeschichteValidierungsfehler(
                f"Bild {dk} gehört nicht zum Ereignis '{ek}'."
            )

    ersetzt_wert = ersetzt.strip() if isinstance(ersetzt, str) and ersetzt.strip() else None
    if ersetzt_wert is not None:
        vorhandene_ids = {e.get("id") for e in _geschichten_laden()}
        if ersetzt_wert not in vorhandene_ids:
            raise GeschichteValidierungsfehler(
                f"Ersetzte Geschichte '{ersetzt_wert}' existiert nicht."
            )

    zeile = {
        "id": str(uuid.uuid4()),
        "zeit": _jetzt_iso(),
        "schicht": SCHICHT_MENSCH,
        "version": SCHICHT_VERSION,
        "ereignis_kennung": ek,
        "ereignis_datum": ereignis.get("datum") if isinstance(ereignis.get("datum"), str) else None,
        "ereignis_titel": _titel_fuer(ereignis, eigene_titel())[0],
        "datei_kennung": dk,
        "text": text_wert,
        "quelle": quelle_wert,
        "ersetzt": ersetzt_wert,
    }

    pfad = geschichten_pfad()
    ordner = os.path.dirname(pfad)
    if ordner:
        os.makedirs(ordner, exist_ok=True)

    with open(pfad, "a", encoding="utf-8") as datei:
        datei.write(json.dumps(zeile, ensure_ascii=False) + "\n")
        datei.flush()
        os.fsync(datei.fileno())

    return zeile



def titel_setzen(kennung: str, name: Any) -> Dict[str, Any]:
    """Eigenen Titel für einen Anlass setzen (leer = zurück zum automatischen).

    Validiert (Anlass existiert, höchstens ``TITEL_MAX_LAENGE`` Zeichen,
    Leerraum zusammengezogen) und wirft :class:`GeschichteValidierungsfehler`
    mit deutschem Text. Schreibt **nur anhängend** (``"a"`` + ``flush`` +
    ``fsync``); die vorige Fassung bleibt in der Datei (Rückweg).
    """
    ek = kennung.strip() if isinstance(kennung, str) else ""
    if not ek:
        raise GeschichteValidierungsfehler("Ereignis-Kennung fehlt.")
    ereignis = _ereignis_finden(ek)
    if ereignis is None:
        raise GeschichteValidierungsfehler(f"Ereignis '{ek}' existiert nicht.")
    wert = " ".join(name.split()) if isinstance(name, str) else ""
    if len(wert) > TITEL_MAX_LAENGE:
        raise GeschichteValidierungsfehler(
            f"Titel ist zu lang ({len(wert)} Zeichen, erlaubt sind höchstens {TITEL_MAX_LAENGE})."
        )
    vorher, _ = _titel_fuer(ereignis, eigene_titel())
    zeile = {"kennung": ek, "name": wert, "zeit": _jetzt_iso(), "vorher": vorher}
    pfad = titel_pfad()
    ordner = os.path.dirname(pfad)
    if ordner:
        os.makedirs(ordner, exist_ok=True)
    with open(pfad, "a", encoding="utf-8") as datei:
        datei.write(json.dumps(zeile, ensure_ascii=False) + "\n")
        datei.flush()
        os.fsync(datei.fileno())
    titel, eigen = _titel_fuer(ereignis, eigene_titel())
    return {"kennung": ek, "titel": titel, "titel_eigen": eigen, "titel_automatisch": _titel_aus(ereignis)}
