"""Dateisuche auf dem Handy (öffentliche Termux-Ordner)."""
import logging

from fastapi import APIRouter, Query

from app.services.datei_suche import basis_ordner_verfuegbar, suche_dateien

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/dateien", tags=["dateien"])


@router.get("")
def dateien_suchen(suche: str = Query("", max_length=200)):
    """Sucht in den freigegebenen Ordnern nach einem Stichwort.

    Sicher: nur lesend, nur freigegebene Ordner, nur Dateinamen/Erweiterungen
    (kein Inhalt). Das Ergebnis kann der Nutzer dann als Anhang wählen.
    """
    try:
        treffer = suche_dateien(suche)
        return {
            "treffer": treffer,
            "anzahl": len(treffer),
            "ordner": basis_ordner_verfuegbar(),
        }
    except Exception as e:
        logger.error("Dateisuche fehlgeschlagen: %s", e)
        return {"treffer": [], "anzahl": 0, "fehler": str(e), "ordner": []}
