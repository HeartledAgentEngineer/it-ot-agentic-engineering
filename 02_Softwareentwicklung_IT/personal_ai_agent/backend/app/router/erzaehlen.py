"""Router: Erzähl-Diashow (Auftrag E8a, 28.09.2026).

  GET  /api/erzaehlen/ereignisse            Gefilterte Ereignisliste
  GET  /api/erzaehlen/ereignisse/{kennung}  Ein Ereignis + Datei-Kennungen + Geschichten
  POST /api/erzaehlen/geschichten           Eine Geschichte anhängen
  GET  /api/erzaehlen/geschichten           Geschichten (optional gefiltert)

Eiserne Regeln
--------------
  * GET-Endpunkte antworten **immer** mit HTTP 200 und denselben Feldern.
    Fehlt ``ereignisse.jsonl`` (Normalfall auf einem frischen Gerät), ist
    ``ok`` falsch und ``error`` trägt einen deutschen Text — kein 500er.
  * POST validiert (Regeln in ``services/erzaehl_service.py``) und antwortet
    bei ungültiger Eingabe mit HTTP 400 und deutschem Text.
  * Nur lesend bei Ereignissen, nur anhängend bei Geschichten — siehe Dienst.
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services import erzaehl_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/erzaehlen", tags=["erzaehlen"])

EREIGNISDATEI_FEHLT = (
    "Ereignisdatei noch nicht vorhanden — sie liegt auf dem PC "
    "(tools/foto_sortierung/ereignisse_bauen.py)."
)


@router.get("/ereignisse")
def ereignisse(
    jahr: Optional[int] = Query(None, description="Nur Ereignisse dieses Jahres"),
    suche: Optional[str] = Query(None, max_length=200, description="Teilzeichenkette im Titel"),
    min_bilder: int = Query(1, description="Mindestzahl an Dateien je Ereignis"),
    limit: int = Query(200, description="Höchstzahl der Ereignisse (1…500)"),
    offset: int = Query(0, description="Versatz für Seitenblättern"),
) -> Dict[str, Any]:
    """Gefilterte Ereignisliste. Antwortet immer mit HTTP 200."""
    antwort: Dict[str, Any] = {
        "ok": False,
        "eintraege": [],
        "gesamt": 0,
        "defekte_zeilen": 0,
        "error": None,
    }
    try:
        if not erzaehl_service.ereignisse_existiert():
            antwort["error"] = EREIGNISDATEI_FEHLT
            return antwort

        ergebnis = erzaehl_service.ereignisse_liste(
            jahr=jahr, suche=suche, min_bilder=min_bilder, limit=limit, offset=offset,
        )
        antwort["ok"] = True
        antwort["eintraege"] = ergebnis["eintraege"]
        antwort["gesamt"] = ergebnis["gesamt"]
        antwort["defekte_zeilen"] = ergebnis["defekte_zeilen"]
    except Exception as e:  # noqa: BLE001 – der Endpunkt darf nie 500en
        logger.error("Ereignisliste fehlgeschlagen: %s", e)
        antwort["ok"] = False
        antwort["error"] = f"Ereignisliste nicht lesbar ({type(e).__name__})"
    return antwort


@router.get("/ereignisse/{kennung}")
def ereignis_detail(kennung: str) -> Dict[str, Any]:
    """Ein Ereignis mit allen Datei-Kennungen und seinen Geschichten."""
    antwort: Dict[str, Any] = {"ok": False, "ereignis": None, "error": None}
    try:
        if not erzaehl_service.ereignisse_existiert():
            antwort["error"] = EREIGNISDATEI_FEHLT
            return antwort

        detail = erzaehl_service.ereignis_detail(kennung)
        if detail is None:
            antwort["error"] = f"Ereignis '{kennung}' nicht gefunden."
            return antwort

        antwort["ok"] = True
        antwort["ereignis"] = detail
    except Exception as e:  # noqa: BLE001 – der Endpunkt darf nie 500en
        logger.error("Ereignis-Detail fehlgeschlagen: %s", e)
        antwort["ok"] = False
        antwort["error"] = f"Ereignis nicht lesbar ({type(e).__name__})"
    return antwort


@router.get("/geschichten")
def geschichten(
    ereignis_kennung: Optional[str] = Query(None, max_length=200),
    datei_kennung: Optional[int] = Query(None),
) -> Dict[str, Any]:
    """Geschichten (nur neueste Fassung), optional gefiltert."""
    antwort: Dict[str, Any] = {"ok": False, "geschichten": [], "error": None}
    try:
        antwort["geschichten"] = erzaehl_service.geschichten(
            ereignis_kennung=ereignis_kennung, datei_kennung=datei_kennung,
        )
        antwort["ok"] = True
    except Exception as e:  # noqa: BLE001 – der Endpunkt darf nie 500en
        logger.error("Geschichten-Liste fehlgeschlagen: %s", e)
        antwort["ok"] = False
        antwort["geschichten"] = []
        antwort["error"] = f"Geschichten nicht lesbar ({type(e).__name__})"
    return antwort


class GeschichteEingabe(BaseModel):
    """Eingabe für ``POST /api/erzaehlen/geschichten``."""

    # Bewusst KEIN max_length auf `text`: ein zu langer Text soll als HTTP 400
    # mit deutschem Klartext aus dem Dienst kommen (Auftrag), nicht als
    # generisches Pydantic-422.
    ereignis_kennung: str = Field(..., min_length=1, max_length=200)
    text: str = Field(..., min_length=1)
    quelle: str = Field(..., min_length=1, max_length=20)
    datei_kennung: Optional[int] = None
    ersetzt: Optional[str] = Field(default=None, max_length=100)


@router.post("/geschichten")
def geschichte_speichern(eingabe: GeschichteEingabe) -> Dict[str, Any]:
    """Eine Geschichte anhängen. HTTP 400 mit deutschem Text bei Fehler."""
    try:
        zeile = erzaehl_service.geschichte_speichern(
            ereignis_kennung=eingabe.ereignis_kennung,
            text=eingabe.text,
            quelle=eingabe.quelle,
            datei_kennung=eingabe.datei_kennung,
            ersetzt=eingabe.ersetzt,
        )
    except erzaehl_service.GeschichteValidierungsfehler as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001 – kein 500er ohne Klartext
        logger.error("Geschichte speichern fehlgeschlagen: %s", e)
        raise HTTPException(
            status_code=400, detail=f"Geschichte konnte nicht gespeichert werden ({type(e).__name__})."
        ) from e
    return {"ok": True, "geschichte": zeile}
