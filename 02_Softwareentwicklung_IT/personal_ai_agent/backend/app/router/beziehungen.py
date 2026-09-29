"""Router: Beziehungen – GET /api/beziehungen/uebersicht und /api/beziehungen/tag.

Warum es diese Endpunkte gibt
-----------------------------
Der Nachtlauf-Schritt N27e hat je Anlass **belegbare** Aussagen „wer war mit
wem wo" in ``~/foto_sortierung/beziehungen.jsonl`` abgeleitet (15.051 Aussagen).
Diese Datei liegt **nur auf dem PC**; am Handy gibt es sie nicht. Dieser Router
macht sie abfragbar:

  * ``GET /api/beziehungen/uebersicht`` — die Kennzahlen aus der kleinen
    Übersicht ``beziehungen.json`` (Zahlen je Unterart, Datumsspanne,
    Personen-Kennungen, Kontakte),
  * ``GET /api/beziehungen/tag?datum=JJJJ-MM-TT`` — alle an einem Tag
    belegbaren Aussagen (sortiert nach Unterart-Reihenfolge).

Die Chat-Anhängung (``_beziehungen_tool`` in ``router/chat.py``) nutzt denselben
Dienst wie ``/api/beziehungen/tag``.

Eiserne Regeln
--------------
  * **IMMER HTTP 200** und **immer dieselben Felder**. Fehlt eine Datei (der
    Normalfall auf einem frisch eingerichteten Handy), steht das als deutscher
    ``error``-Text im JSON und ``ok`` ist ``false`` — nie ein 500er, nie ein
    Absturz.
  * **Nur lesend, kein Netz, keine Bilder.** Der Dienst liest ausschließlich
    die lokalen Dateien; es werden keine Bilddateien angefasst und keine
    Fremdsysteme aufgerufen.
  * **Keine Geheimnisse.** Ausgegeben werden Zahlen, Datum, Stand, der
    Dateiname der Quelle und das, was in der Datei steht — kein Schlüssel.
"""

import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query

from app.services import beziehungen_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/beziehungen", tags=["beziehungen"])

# Die Felder der Übersichts-Antwort — immer dieselben.
UEBERSICHT_FELDER = (
    "pfad", "existiert", "stand", "anzahl", "anzahl_gesamt", "datum_von",
    "datum_bis", "anzahl_personen_kennungen", "anzahl_namen_bestaetigt",
    "anzahl_kontakte",
)


@router.get("/uebersicht")
def beziehungen_uebersicht() -> Dict[str, Any]:
    """Kennzahlen der Beziehungen aus der lokalen Übersicht.

    Antwortet immer mit HTTP 200 und allen Feldern ``ok``, ``pfad``,
    ``existiert``, ``stand``, ``anzahl``, ``anzahl_gesamt``, ``datum_von``,
    ``datum_bis``, ``anzahl_personen_kennungen``, ``anzahl_namen_bestaetigt``,
    ``anzahl_kontakte``, ``error``. Fehlt die Datei, ist ``ok`` falsch und
    ``error`` trägt einen deutschen Text — der Endpunkt bleibt erreichbar, damit
    die App ehrlich melden kann, dass die Daten noch auf dem PC liegen.
    """
    antwort: Dict[str, Any] = {
        "ok": False,
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
        daten = beziehungen_service.beziehungen_laden()
        for feld in UEBERSICHT_FELDER:
            antwort[feld] = daten.get(feld)
        antwort["ok"] = bool(daten.get("existiert"))
        antwort["error"] = daten.get("error")
    except Exception as e:  # noqa: BLE001 – der Endpunkt darf nie 500en
        logger.error("Beziehungen-Übersicht fehlgeschlagen: %s", e)
        antwort["ok"] = False
        antwort["error"] = f"Beziehungen nicht lesbar ({type(e).__name__})"

    return antwort


@router.get("/tag")
def beziehungen_tag(
    datum: Optional[str] = Query(None, max_length=40,
                                 description="Tag, z. B. 2022-08-21 oder 21.08.2022"),
    limit: int = Query(50, description="Höchstzahl der Aussagen (1…200)"),
) -> Dict[str, Any]:
    """Alle belegbaren Aussagen eines Tages aus der lokalen Datei.

    Antwortet immer mit HTTP 200 und allen Feldern ``ok``, ``quelle``,
    ``stand``, ``datum``, ``gueltig``, ``anzahl``, ``anzahl_je_unterart``,
    ``aussagen``, ``gekuerzt``, ``error``. Ein unplausibles Datum ergibt
    ``gueltig: false`` (HTTP 200) und einen deutschen ``error``; ein Tag ohne
    Aussagen ist kein Fehler (``anzahl: 0``). ``limit`` wird auf 1…200 geklemmt.
    """
    antwort: Dict[str, Any] = {
        "ok": False,
        "quelle": None,
        "stand": None,
        "datum": None,
        "gueltig": False,
        "anzahl": 0,
        "anzahl_je_unterart": {},
        "aussagen": [],
        "gekuerzt": False,
        "error": None,
    }

    try:
        pfad = beziehungen_service.aussagen_pfad()
        antwort["quelle"] = os.path.basename(pfad) or None

        antwort["stand"] = beziehungen_service.beziehungen_laden().get("stand")

        daten = beziehungen_service.aussagen_fuer_datum(datum, limit=limit)
        for feld in ("datum", "gueltig", "anzahl", "anzahl_je_unterart",
                     "aussagen", "gekuerzt"):
            antwort[feld] = daten.get(feld)
        antwort["error"] = daten.get("error")
        antwort["ok"] = daten.get("error") is None
    except Exception as e:  # noqa: BLE001 – der Endpunkt darf nie 500en
        logger.error("Beziehungen-Tag fehlgeschlagen: %s", e)
        antwort["ok"] = False
        antwort["error"] = f"Beziehungen nicht lesbar ({type(e).__name__})"

    return antwort
