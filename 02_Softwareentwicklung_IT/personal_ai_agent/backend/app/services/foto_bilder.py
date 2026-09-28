"""Datei-Kennungen zu den Fotos-Events für das Handy (N13a, Teil B, 28.09.2026).

Warum dieses Modul
------------------
Die Fotos-Übersicht aus N11 (``~/foto_sortierung/fotos_uebersicht.json``) trägt
**bewusst keine Datei-Kennungen** — für „wie viele Events gab's?" braucht sie
niemand. Für ein Vorschaubild am Handy ist eine Kennung aber unverzichtbar:
ohne sie kann kein Bild geladen werden. Das Werkzeug aus Teil A
(``tools/foto_sortierung/foto_dateien.py``) leitet deshalb aus dem lokalen
``sortierplan.json`` eine zweite kleine Datei ab
(``~/foto_sortierung/fotos_dateien.json``) — je Event eine Liste aus
``datei_id`` und Dateiname, sonst nichts. Die N11-Übersicht bleibt unangetastet.

Dieses Modul LIEST diese Datei und macht daraus

  * eine gefilterte, gekürzte Trefferliste (:func:`bilder_finden`) für „zeig
    mir die Bilder vom Urlaub 2021" — je Event höchstens ``pro_event``
    Dateien, die Gesamtzahl bleibt als ``anzahl`` sichtbar,
  * einen Zustandsblock (:func:`status_block`) mit immer denselben Schlüsseln.

Eiserne Regeln
--------------
  * **Kein Netz.** Kein ``httpx``/``requests``, kein pCloud-Aufruf, kein
    LLM-Aufruf. Gelesen wird ausschließlich die lokale Kennungsdatei.
  * **Keine Bilder.** Es wird keine Bilddatei geöffnet, kopiert, geladen oder
    gespeichert; die Datei trägt nur Kennungen und Namen.
  * **Nie ein Wurf.** :func:`dateien_laden` fängt jeden Fehler ab und liefert
    ``{"existiert": False, "error": "<deutscher Text>"}``. Eine unbekannte
    ``art`` oder ``version`` wird als Fehler gemeldet, nicht stillschweigend
    gelesen.
  * **Nur lesend.** Die Datei wird ausschließlich gelesen.
  * **Keine Geheimnisse.** In den Antworten stehen Zahlen, Stand, der
    Dateiname der Quelle und die Kennungen/Dateinamen aus der Datei — kein
    Schlüssel, kein Token, kein Ablageort.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Name der Datei, die Teil A erzeugt und die dieses Modul liest.
DATEIEN_DATEINAME = "fotos_dateien.json"

# Vorgabe-Ort der Kennungsdatei: außerhalb des Repos, im selben Ordner wie der
# Sortierplan. Für Tests über die Umgebungsvariable ``FOTO_DATEIEN_PFAD``
# übersteuerbar.
DATEIEN_ORDNER = "foto_sortierung"

# Schema-Version, die dieses Modul versteht (eingefrorene Schnittstelle).
ERWARTETE_VERSION = 1

# Erwarteter ``art``-Wert der Kennungsdatei.
ERWARTETE_ART = "foto_dateien"

# Grenzen für ``limit`` (Events je Antwort) und ``pro_event`` (Dateien je
# Event). Unten 1 — eine leere Antwort ist keine Antwort —, oben 50 bzw. 200:
# die Datei bleibt klein, und eine Chat-Antwort am Handy soll es auch.
LIMIT_STANDARD = 5
LIMIT_MIN = 1
LIMIT_MAX = 50

PRO_EVENT_STANDARD = 40
PRO_EVENT_MIN = 1
PRO_EVENT_MAX = 200

# Die Schlüssel einer Trefferzeile und eines Dateieintrags (immer dieselben).
EVENT_SCHLUESSEL = ("jahr", "kategorie", "event", "anzahl", "dateien")
DATEI_SCHLUESSEL = ("datei_id", "name")

# Umlaut-Toleranz für die Textsuche: Beide Seiten werden vor dem Vergleich
# vereinheitlicht, damit „Urlaube" auch „Urlaub" findet und „pruefung" auch
# „Prüfung" (und umgekehrt). Kleinschreibung passiert im selben Schritt.
_UMLAUTE = (
    ("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"),
    ("Ä", "ae"), ("Ö", "oe"), ("Ü", "ue"),
)


# ── Pfad ─────────────────────────────────────────────────────────────────────

def dateien_pfad() -> str:
    """Ort der Kennungsdatei.

    Standard ist ``~/foto_sortierung/fotos_dateien.json``. Für Tests lässt er
    sich über die Umgebungsvariable ``FOTO_DATEIEN_PFAD`` übersteuern; ein
    leerer oder nur aus Leerzeichen bestehender Wert zählt nicht.
    """
    ueber = os.environ.get("FOTO_DATEIEN_PFAD")
    if ueber and ueber.strip():
        return ueber.strip()
    return os.path.join(os.path.expanduser("~"), DATEIEN_ORDNER, DATEIEN_DATEINAME)


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


def _text(wert: Any) -> str:
    """Wert als Text lesen — Nicht-Text und ``None`` werden zu ``""``."""
    return wert.strip() if isinstance(wert, str) else ""


def _normalisieren(text: Any) -> str:
    """Text für den Vergleich vereinheitlichen (klein, Umlaute aufgelöst)."""
    if text is None:
        return ""
    zeichenkette = str(text).strip().lower()
    for umlaut, ersatz in _UMLAUTE:
        zeichenkette = zeichenkette.replace(umlaut, ersatz)
    return zeichenkette


def _begrenzen(wert: Any, standard: int, unten: int, oben: int) -> int:
    """Einen Zahlenwert in die Grenzen klemmen — Unbrauchbares fällt auf Standard.

    ``None``, Text und Ähnliches ergeben ``standard`` statt eines Fehlers;
    gültige Zahlen werden auf ``unten`` … ``oben`` geklemmt.
    """
    zahl = _als_zahl(wert)
    if zahl is None:
        return standard
    return max(unten, min(oben, zahl))


def _limit_begrenzen(limit: Any) -> int:
    """``limit`` auf :data:`LIMIT_MIN` … :data:`LIMIT_MAX` begrenzen."""
    return _begrenzen(limit, LIMIT_STANDARD, LIMIT_MIN, LIMIT_MAX)


def _pro_event_begrenzen(pro_event: Any) -> int:
    """``pro_event`` auf :data:`PRO_EVENT_MIN` … :data:`PRO_EVENT_MAX` begrenzen."""
    return _begrenzen(pro_event, PRO_EVENT_STANDARD, PRO_EVENT_MIN, PRO_EVENT_MAX)


def _datei_eintrag(eintrag: Any) -> Optional[Dict[str, Any]]:
    """Einen Dateieintrag auf die vereinbarten Schlüssel bringen — sonst ``None``.

    Ein Eintrag ohne verwertbare Kennung ist kein Bild: er wird verworfen,
    statt mit erfundener Kennung weiterzureichen.
    """
    if not isinstance(eintrag, dict):
        return None
    kennung = _als_zahl(eintrag.get("datei_id"))
    if kennung is None:
        return None
    return {"datei_id": kennung, "name": _text(eintrag.get("name"))}


# ── Laden ────────────────────────────────────────────────────────────────────

def dateien_laden(pfad: Optional[str] = None) -> Dict[str, Any]:
    """Die Kennungsdatei lesen. **Wirft nie.**

    Rückgabe hat immer dieselben Schlüssel: ``existiert``, ``pfad``, ``stand``,
    ``zahlen``, ``events``, ``error``. Bei jedem Problem kommt
    ``existiert: False`` mit einem deutschen ``error``-Text zurück — fehlende
    Datei, kein JSON, unerwartetes Format, fremde ``art`` oder ``version``.

    ``pfad`` übersteuert den Vorgabeort; ohne Angabe gilt
    :func:`dateien_pfad`.
    """
    ergebnis: Dict[str, Any] = {
        "existiert": False,
        "pfad": None,
        "stand": None,
        "zahlen": {},
        "events": [],
        "error": None,
    }

    try:
        ziel = pfad if pfad and str(pfad).strip() else dateien_pfad()
    except Exception as e:  # noqa: BLE001 – nie ein Wurf nach außen
        logger.warning("Datei-Kennungen: Pfad nicht bestimmbar (%s).", type(e).__name__)
        ergebnis["error"] = f"Datei-Kennungen: Pfad nicht bestimmbar ({type(e).__name__})"
        return ergebnis

    ergebnis["pfad"] = ziel

    try:
        if not os.path.isfile(ziel):
            ergebnis["error"] = (
                "Datei-Kennungen nicht gefunden (die Kennungen entstehen auf "
                "dem PC, Werkzeug foto_dateien.py)"
            )
            return ergebnis
        with open(ziel, "r", encoding="utf-8") as datei:
            daten = json.load(datei)
    except OSError as e:
        logger.warning("Datei-Kennungen nicht lesbar (%s): %s", ziel, e)
        ergebnis["error"] = f"Datei-Kennungen nicht lesbar ({type(e).__name__})"
        return ergebnis
    except UnicodeDecodeError as e:
        logger.warning("Datei-Kennungen nicht als UTF-8 lesbar (%s): %s", ziel, e)
        ergebnis["error"] = "Datei-Kennungen sind nicht als UTF-8 lesbar"
        return ergebnis
    except ValueError as e:
        logger.warning("Datei-Kennungen sind kein gültiges JSON (%s): %s", ziel, e)
        ergebnis["error"] = f"Datei-Kennungen sind kein gültiges JSON ({type(e).__name__})"
        return ergebnis
    except Exception as e:  # noqa: BLE001 – nie ein Wurf nach außen
        logger.warning("Datei-Kennungen nicht auswertbar (%s): %s", ziel, e)
        ergebnis["error"] = f"Datei-Kennungen nicht auswertbar ({type(e).__name__})"
        return ergebnis

    if not isinstance(daten, dict):
        ergebnis["error"] = "Datei-Kennungen haben ein unerwartetes Format (kein Objekt)"
        return ergebnis

    art = daten.get("art")
    if art is None or art != ERWARTETE_ART:
        ergebnis["error"] = f"Datei-Kennungen haben eine unerwartete Art ({art})"
        return ergebnis

    version = daten.get("version")
    if _als_zahl(version) != ERWARTETE_VERSION:
        ergebnis["error"] = (
            f"Datei-Kennungen haben eine unerwartete Schema-Version "
            f"({version}, erwartet {ERWARTETE_VERSION})"
        )
        return ergebnis

    ergebnis["existiert"] = True
    ergebnis["stand"] = _text(daten.get("stand")) or None

    zahlen = daten.get("zahlen")
    ergebnis["zahlen"] = dict(zahlen) if isinstance(zahlen, dict) else {}

    events = daten.get("events")
    ergebnis["events"] = [dict(eintrag) for eintrag in events
                          if isinstance(eintrag, dict)] if isinstance(events, list) else []
    return ergebnis


# ── Zustandsblock ────────────────────────────────────────────────────────────

def status_block() -> Dict[str, Any]:
    """Zustand der Datei-Kennungen — **immer dieselben Schlüssel**.

    ``ok``, ``quelle``, ``stand``, ``events``, ``dateien``, ``error``. ``quelle``
    ist der Dateiname ohne Verzeichnis und steht auch dann darin, wenn die
    Datei fehlt; ``events``/``dateien`` kommen aus ``zahlen`` (fehlt eine Zahl,
    wird die Event-Liste gezählt). Alle Fehler landen als deutscher Text in
    ``error`` — diese Funktion wirft nie.
    """
    block: Dict[str, Any] = {
        "ok": False,
        "quelle": None,
        "stand": None,
        "events": None,
        "dateien": None,
        "error": None,
    }

    try:
        pfad = dateien_pfad()
    except Exception as e:  # noqa: BLE001 – nie ein Wurf
        logger.warning("Datei-Kennungen: Pfad nicht bestimmbar (%s).", type(e).__name__)
        block["error"] = f"Datei-Kennungen: Pfad nicht bestimmbar ({type(e).__name__})"
        return block

    block["quelle"] = os.path.basename(pfad) or DATEIEN_DATEINAME

    daten = dateien_laden(pfad)
    block["error"] = daten.get("error")
    if not daten.get("existiert"):
        return block

    block["ok"] = True
    block["stand"] = daten.get("stand")

    zahlen = daten.get("zahlen")
    zahlen = zahlen if isinstance(zahlen, dict) else {}
    events = daten.get("events")
    events = events if isinstance(events, list) else []

    anzahl_events = _als_zahl(zahlen.get("events"))
    block["events"] = anzahl_events if anzahl_events is not None else len(events)

    anzahl_dateien = _als_zahl(zahlen.get("dateien"))
    if anzahl_dateien is None:
        anzahl_dateien = sum(
            _als_zahl(eintrag.get("anzahl")) or 0 for eintrag in events
        )
    block["dateien"] = anzahl_dateien
    return block


# ── Filtern ──────────────────────────────────────────────────────────────────

def _event_treffer(eintrag: Dict[str, Any], pro_event: int) -> Optional[Dict[str, Any]]:
    """Eine Trefferzeile bauen: Dateiliste gekürzt, ``anzahl`` bleibt die Gesamtzahl."""
    kennungen: List[Dict[str, Any]] = []
    rohe = eintrag.get("dateien")
    if isinstance(rohe, list):
        for datei in rohe:
            eintrag_datei = _datei_eintrag(datei)
            if eintrag_datei is not None:
                kennungen.append(eintrag_datei)

    gesamt = _als_zahl(eintrag.get("anzahl"))
    if gesamt is None:
        gesamt = len(kennungen)

    return {
        "jahr": _als_zahl(eintrag.get("jahr")),
        "kategorie": _text(eintrag.get("kategorie")),
        "event": _text(eintrag.get("event")),
        "anzahl": gesamt,
        "dateien": kennungen[:pro_event],
    }


def bilder_finden(jahr: Any = None, kategorie: Any = None, event: Any = None,
                  suche: Any = None, limit: int = LIMIT_STANDARD,
                  pro_event: int = PRO_EVENT_STANDARD) -> List[Dict[str, Any]]:
    """Events mit ihren Datei-Kennungen filtern (höchstens ``limit`` Treffer).

    Filter:
      * ``jahr`` — exakt (auch als Zahl-Text lesbar),
      * ``kategorie`` — exakt, ohne Unterschied Groß/Klein,
      * ``event`` — Teilzeichenkette im Event-Namen, ohne Unterschied
        Groß/Klein und mit Umlaut-Toleranz; **``event`` hat Vorrang vor
        ``suche``** (beide filtern dasselbe Feld),
      * ``limit`` — auf :data:`LIMIT_MIN` … :data:`LIMIT_MAX` begrenzt,
      * ``pro_event`` — Dateien je Event, auf :data:`PRO_EVENT_MIN` …
        :data:`PRO_EVENT_MAX` begrenzt; ``anzahl`` bleibt die echte
        Gesamtzahl, damit die App „42 Bilder, 40 gezeigt" sagen kann.

    Fehlt die Datei oder fehlt die Event-Liste, ist das Ergebnis leer — kein
    Wurf, kein Fehlertext.
    """
    daten = dateien_laden()
    if not daten.get("existiert"):
        return []

    liste = daten.get("events")
    if not isinstance(liste, list):
        return []

    jahr_wert = _als_zahl(jahr)
    kategorie_wert = _normalisieren(kategorie) or None
    such_wert = _normalisieren(event) or _normalisieren(suche) or None
    grenze = _limit_begrenzen(limit)
    dateien_grenze = _pro_event_begrenzen(pro_event)

    treffer: List[Dict[str, Any]] = []
    for eintrag in liste:
        if not isinstance(eintrag, dict):
            continue
        if jahr_wert is not None and _als_zahl(eintrag.get("jahr")) != jahr_wert:
            continue
        if kategorie_wert is not None and _normalisieren(eintrag.get("kategorie")) != kategorie_wert:
            continue
        if such_wert is not None and such_wert not in _normalisieren(eintrag.get("event")):
            continue
        zeile = _event_treffer(eintrag, dateien_grenze)
        if zeile is None:
            continue
        treffer.append(zeile)
        if len(treffer) >= grenze:
            break
    return treffer
