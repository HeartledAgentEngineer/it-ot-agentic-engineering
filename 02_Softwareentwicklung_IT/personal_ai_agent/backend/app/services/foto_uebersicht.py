"""Fotos-Übersicht für das Handy (Nachtlauf-Schritt N11, Teil B, 27.09.2026).

Warum dieses Modul
------------------
Der Nutzer fragt in der App am Handy „wie viele Events gab's?" oder „zeig mir
die Urlaube 2021". Beantworten lässt sich das nicht aus dem Handy heraus: Der
Sortierschlüssel, ``themen.jsonl`` und ``kategorien.json`` liegen **nur auf dem
PC**. Das Werkzeug aus Teil A (``tools/foto_sortierung/foto_uebersicht.py``)
zieht deshalb aus dem lokalen ``sortierplan.json`` **eine kleine Datei**
(``~/foto_sortierung/fotos_uebersicht.json``) — nur Zahlen und Event-Namen.

Dieses Modul LIEST diese Übersicht und macht daraus

  * eine Chat-Anhängung (:func:`text_antwort`) für Fragen wie „wie viele Events
    gab's?" — der Chat bleibt still (leerer String), wenn die Datei fehlt, statt
    Zahlen zu raten,
  * eine gefilterte Event-Liste (:func:`events_finden`) für „zeig mir die
    Urlaube 2021",
  * einen Zustandsblock (:func:`status_block`) mit immer denselben Schlüsseln
    für das Selbsttest-Blatt.

Eiserne Regeln
--------------
  * **Kein Netz.** Kein ``httpx``/``requests``, kein pCloud-Aufruf, kein
    LLM-Aufruf. Gelesen wird ausschließlich die lokale Übersichtsdatei.
  * **Keine Bilder.** Es wird keine Bilddatei geöffnet, kopiert oder
    gespeichert; die Übersicht trägt nur Zahlen und Namen.
  * **Nie ein Wurf.** :func:`uebersicht_laden` fängt jeden Fehler ab und liefert
    ``{"existiert": False, "error": "<deutscher Text>"}``. Fehlt die Datei,
    bleiben Listen leer und die Chat-Anhängung leer.
  * **Nur lesend.** Die Datei wird ausschließlich gelesen.
  * **Keine Geheimnisse.** In den Texten stehen nur Zahlen, Stand und der
    Dateiname der Quelle — kein Schlüssel, kein Token, kein Pfad zu Bildern.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Name der Datei, die Teil A erzeugt und die dieses Modul liest.
UEBERSICHT_DATEINAME = "fotos_uebersicht.json"

# Vorgabe-Ort der Übersicht: außerhalb des Repos, im selben Ordner wie der
# Sortierplan. Für Tests über die Umgebungsvariable ``FOTO_UEBERSICHT_PFAD``
# übersteuerbar.
UEBERSICHT_ORDNER = "foto_sortierung"

# Schema-Version, die dieses Modul versteht (eingefrorene Schnittstelle).
ERWARTETE_VERSION = 1

# Erwarteter ``art``-Wert der Übersichtsdatei.
ERWARTETE_ART = "foto_uebersicht"

# Grenzen für ``limit``: unten 1 (eine leere Antwort ist keine Antwort), oben
# 200 (die Datei bleibt klein, ein Chat-Anhang darf es auch).
LIMIT_STANDARD = 25
LIMIT_MIN = 1
LIMIT_MAX = 200

# Umlaut-Toleranz für die Textsuche: Beide Seiten werden vor dem Vergleich
# vereinheitlicht, damit „Urlaube" auch „Urlaub" findet und „pruefung" auch
# „Prüfung" (und umgekehrt). Kleinschreibung passiert im selben Schritt.
_UMLAUTE = (
    ("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"),
    ("Ä", "ae"), ("Ö", "oe"), ("Ü", "ue"),
)


# ── Pfad ─────────────────────────────────────────────────────────────────────

def uebersicht_pfad() -> str:
    """Ort der Übersichtsdatei.

    Standard ist ``~/foto_sortierung/fotos_uebersicht.json``. Für Tests lässt
    er sich über die Umgebungsvariable ``FOTO_UEBERSICHT_PFAD`` übersteuern;
    ein leerer oder nur aus Leerzeichen bestehender Wert zählt nicht.
    """
    ueber = os.environ.get("FOTO_UEBERSICHT_PFAD")
    if ueber and ueber.strip():
        return ueber.strip()
    return os.path.join(os.path.expanduser("~"), UEBERSICHT_ORDNER, UEBERSICHT_DATEINAME)


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


def _normalisieren(text: Any) -> str:
    """Text für den Vergleich vereinheitlichen (klein, Umlaute aufgelöst)."""
    if text is None:
        return ""
    zeichenkette = str(text).strip().lower()
    for umlaut, ersatz in _UMLAUTE:
        zeichenkette = zeichenkette.replace(umlaut, ersatz)
    return zeichenkette


def _limit_begrenzen(limit: Any) -> int:
    """``limit`` auf :data:`LIMIT_MIN` … :data:`LIMIT_MAX` begrenzen.

    Unbrauchbare Eingaben (``None``, Text, 0) fallen auf
    :data:`LIMIT_STANDARD` bzw. die Untergrenze zurück — nie auf einen Fehler.
    """
    wert = _als_zahl(limit)
    if wert is None:
        return LIMIT_STANDARD
    return max(LIMIT_MIN, min(LIMIT_MAX, wert))


def _zahlen_aus(daten: Dict[str, Any]) -> Dict[str, Any]:
    """Den ``zahlen``-Block liefern — ein fehlender Block wird zu ``{}``."""
    zahlen = daten.get("zahlen")
    return zahlen if isinstance(zahlen, dict) else {}


# ── Laden ────────────────────────────────────────────────────────────────────

def uebersicht_laden(pfad: Optional[str] = None) -> Dict[str, Any]:
    """Die Übersichtsdatei lesen. **Wirft nie.**

    Bei Erfolg kommt der Inhalt der Datei zurück, ergänzt um
    ``existiert: True``, ``error: None`` und ``pfad``. Bei jedem Problem kommt
    ``existiert: False`` mit einem deutschen ``error``-Text zurück — fehlende
    Datei, kein JSON, unerwartetes Format, fremde Schema-Version.

    ``pfad`` übersteuert den Vorgabeort; ohne Angabe gilt
    :func:`uebersicht_pfad`.
    """
    ergebnis: Dict[str, Any] = {"existiert": False, "error": None}

    try:
        ziel = pfad if pfad and str(pfad).strip() else uebersicht_pfad()
    except Exception as e:  # noqa: BLE001 – nie ein Wurf nach außen
        logger.warning("Fotos-Übersicht: Pfad nicht bestimmbar (%s).", type(e).__name__)
        ergebnis["error"] = f"Fotos-Übersicht: Pfad nicht bestimmbar ({type(e).__name__})"
        return ergebnis

    ergebnis["pfad"] = ziel

    try:
        if not os.path.isfile(ziel):
            ergebnis["error"] = (
                "Fotos-Übersicht nicht gefunden (die Zahlen entstehen auf dem PC, "
                "Werkzeug foto_uebersicht.py)"
            )
            return ergebnis
        with open(ziel, "r", encoding="utf-8") as datei:
            daten = json.load(datei)
    except OSError as e:
        logger.warning("Fotos-Übersicht nicht lesbar (%s): %s", ziel, e)
        ergebnis["error"] = f"Fotos-Übersicht nicht lesbar ({type(e).__name__})"
        return ergebnis
    except UnicodeDecodeError as e:
        logger.warning("Fotos-Übersicht nicht als UTF-8 lesbar (%s): %s", ziel, e)
        ergebnis["error"] = "Fotos-Übersicht ist nicht als UTF-8 lesbar"
        return ergebnis
    except ValueError as e:
        logger.warning("Fotos-Übersicht ist kein gültiges JSON (%s): %s", ziel, e)
        ergebnis["error"] = f"Fotos-Übersicht ist kein gültiges JSON ({type(e).__name__})"
        return ergebnis
    except Exception as e:  # noqa: BLE001 – nie ein Wurf nach außen
        logger.warning("Fotos-Übersicht nicht auswertbar (%s): %s", ziel, e)
        ergebnis["error"] = f"Fotos-Übersicht nicht auswertbar ({type(e).__name__})"
        return ergebnis

    if not isinstance(daten, dict):
        ergebnis["error"] = "Fotos-Übersicht hat ein unerwartetes Format (kein Objekt)"
        return ergebnis

    art = daten.get("art")
    if art is not None and art != ERWARTETE_ART:
        ergebnis["error"] = f"Fotos-Übersicht hat eine unerwartete Art ({art})"
        return ergebnis

    version = daten.get("version")
    if version is not None and _als_zahl(version) != ERWARTETE_VERSION:
        ergebnis["error"] = (
            f"Fotos-Übersicht hat eine unerwartete Schema-Version "
            f"({version}, erwartet {ERWARTETE_VERSION})"
        )
        return ergebnis

    inhalt = dict(daten)
    inhalt["pfad"] = ziel
    inhalt["existiert"] = True
    inhalt["error"] = None
    return inhalt


# ── Zustandsblock für den Selbsttest ─────────────────────────────────────────

def status_block() -> Dict[str, Any]:
    """Zustand der Fotos-Übersicht — **immer dieselben Schlüssel**.

    ``quelle`` ist der Dateiname ohne Verzeichnis (``basename``) und steht auch
    dann darin, wenn die Datei fehlt — der Selbsttest soll die Quelle nennen
    können, aus der die Zahlen kämen. ``dateien`` ist die Gesamtzahl der
    Zeilen/Dateien aus ``zahlen.zeilen``, ``jahre`` kommt aus ``zahlen.jahre``
    (fehlt es, wird die Jahre-Liste gezählt). Alle Fehler landen als deutscher
    Text in ``error`` — diese Funktion wirft nie.
    """
    block: Dict[str, Any] = {
        "quelle": None,
        "pfad": None,
        "existiert": False,
        "stand": None,
        "anlaesse": None,
        "events": None,
        "dateien": None,
        "jahre": None,
        "error": None,
    }

    try:
        pfad = uebersicht_pfad()
    except Exception as e:  # noqa: BLE001 – nie ein Wurf
        logger.warning("Fotos-Übersicht: Pfad nicht bestimmbar (%s).", type(e).__name__)
        block["error"] = f"Fotos-Übersicht: Pfad nicht bestimmbar ({type(e).__name__})"
        return block

    block["pfad"] = pfad
    block["quelle"] = os.path.basename(pfad) or None

    daten = uebersicht_laden(pfad)
    block["existiert"] = bool(daten.get("existiert"))
    block["error"] = daten.get("error")
    if not block["existiert"]:
        return block

    stand = daten.get("stand")
    if isinstance(stand, str) and stand.strip():
        block["stand"] = stand.strip()

    zahlen = _zahlen_aus(daten)
    block["anlaesse"] = _als_zahl(zahlen.get("anlaesse"))
    block["events"] = _als_zahl(zahlen.get("events"))
    # „Dateien" ist die Gesamtzahl der Zeilen aus der Zusammenfassung; die
    # Übersicht führt keinen eigenen Schlüssel `dateien`.
    block["dateien"] = _als_zahl(zahlen.get("zeilen"))
    jahre = _als_zahl(zahlen.get("jahre"))
    if jahre is None:
        liste = daten.get("jahre")
        if isinstance(liste, list):
            jahre = len(liste)
    block["jahre"] = jahre
    return block


# ── Filtern ──────────────────────────────────────────────────────────────────

def events_finden(jahr: Any = None, kategorie: Any = None, suche: Any = None,
                  limit: int = 25) -> List[Dict[str, Any]]:
    """Events aus der Übersicht filtern (höchstens ``limit`` Treffer).

    Filter:
      * ``jahr`` — exakt (auch als Zahl-Text lesbar),
      * ``kategorie`` — exakt, ohne Unterschied Groß/Klein,
      * ``suche`` — Teilzeichenkette im Event-Namen, ohne Unterschied
        Groß/Klein und mit Umlaut-Toleranz (``ae`` findet ``ä`` und umgekehrt),
      * ``limit`` — auf :data:`LIMIT_MIN` … :data:`LIMIT_MAX` begrenzt.

    Fehlt die Datei oder fehlt die Event-Liste, ist das Ergebnis leer — kein
    Wurf, kein Fehlertext.
    """
    daten = uebersicht_laden()
    if not daten.get("existiert"):
        return []

    liste = daten.get("events")
    if not isinstance(liste, list):
        return []

    jahr_wert = _als_zahl(jahr)
    kategorie_wert = _normalisieren(kategorie) or None
    suche_wert = _normalisieren(suche) or None
    grenze = _limit_begrenzen(limit)

    treffer: List[Dict[str, Any]] = []
    for eintrag in liste:
        if not isinstance(eintrag, dict):
            continue
        if jahr_wert is not None and _als_zahl(eintrag.get("jahr")) != jahr_wert:
            continue
        if kategorie_wert is not None and _normalisieren(eintrag.get("kategorie")) != kategorie_wert:
            continue
        if suche_wert is not None and suche_wert not in _normalisieren(eintrag.get("name")):
            continue
        treffer.append(dict(eintrag))
        if len(treffer) >= grenze:
            break
    return treffer


# ── Chat-Anhängung ───────────────────────────────────────────────────────────

def _event_zeile(eintrag: Dict[str, Any]) -> str:
    """Eine Event-Zeile für den Chat-Anhang (Name, Kategorie, Dateien, Quelle)."""
    name = str(eintrag.get("name") or "?").strip()
    zusatz: List[str] = []
    kategorie = str(eintrag.get("kategorie") or "").strip()
    if kategorie:
        zusatz.append(kategorie)
    dateien = _als_zahl(eintrag.get("dateien"))
    if dateien is not None:
        zusatz.append(f"{dateien} Datei" + ("" if dateien == 1 else "en"))
    quelle = str(eintrag.get("quelle") or "").strip()
    if quelle:
        zusatz.append(f"Quelle {quelle}")
    return f" - {name}" + (f" ({', '.join(zusatz)})" if zusatz else "")


def text_antwort(jahr: Any = None, kategorie: Any = None, suche: Any = None,
                 limit: int = 25) -> str:
    """Deutsche Notiz für die Chat-Anhängung — leer, wenn die Datei fehlt.

    Die Notiz nennt immer die Gesamtzahl aus der Datei (Anlässe, Events,
    Dateien, Jahre), die Quelle und den Stand sowie die gezeigten Treffer. Sie
    ist als Anhang an die Nutzerfrage gedacht; der Chat soll daraus die Zahlen
    nennen und keine weiteren Events erfinden.
    """
    daten = uebersicht_laden()
    if not daten.get("existiert"):
        # Der Chat bleibt still, statt zu raten.
        return ""

    zahlen = _zahlen_aus(daten)
    kennzahlen: List[str] = []
    for schluessel, wort in (("anlaesse", "Anlässe"), ("events", "Events"),
                             ("zeilen", "Dateien"), ("jahre", "Jahre")):
        wert = _als_zahl(zahlen.get(schluessel))
        if wert is not None:
            kennzahlen.append(f"{wert} {wort}")

    quelle = os.path.basename(str(daten.get("pfad") or "")) or UEBERSICHT_DATEINAME
    stand = str(daten.get("stand") or "").strip()

    kopf = f"\n\n[Fotos-Übersicht (Quelle: {quelle}"
    if stand:
        kopf += f", Stand {stand}"
    kopf += "): " + (", ".join(kennzahlen) if kennzahlen else "keine Zahlen gemeldet")

    filter_teile: List[str] = []
    if _als_zahl(jahr) is not None:
        filter_teile.append(f"Jahr {_als_zahl(jahr)}")
    if str(kategorie or "").strip():
        filter_teile.append(f"Kategorie {str(kategorie).strip()}")
    if str(suche or "").strip():
        filter_teile.append(f"Suche \u201e{str(suche).strip()}\u201c")
    if filter_teile:
        kopf += ". Gefiltert (" + ", ".join(filter_teile) + "): "
    else:
        kopf += ". Zeige "

    treffer = events_finden(jahr=jahr, kategorie=kategorie, suche=suche, limit=limit)
    gesamt = _als_zahl(zahlen.get("events"))
    gesamt_text = f" von {gesamt} Events" if gesamt is not None else ""
    kopf += f"{len(treffer)}{gesamt_text}"

    if not treffer:
        kopf += (". Dazu liegt in der Übersicht nichts vor — sag das ehrlich und "
                 "erfinde keine Events.]")
        return kopf

    zeilen = [_event_zeile(eintrag) for eintrag in treffer]
    return (kopf + ":\n" + "\n".join(zeilen)
            + "\nNenne dem Nutzer diese Zahlen und Namen aus der lokalen "
              "Übersicht; erfinde keine weiteren Events.]")
