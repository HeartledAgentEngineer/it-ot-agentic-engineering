"""Dateisuche auf dem Handy (öffentliche Termux-Ordner)."""
import logging

from fastapi import APIRouter, Query

from app.services.datei_suche import (
    basis_ordner_verfuegbar,
    lese_datei_info,
    suche_dateien,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/dateien", tags=["dateien"])


@router.get("/daten")
def datei_daten(pfad: str = Query("", max_length=1000)):
    """Liefert die fluechtige Bild-Miniatur zu einem Pfad (fuer den Chat).

    Holt die Datei NUR lesend + in-memory (kein Speichern) und liefert die
    data_url — das Frontend zeigt sie kurz an und verwirft sie. Sicher:
    nur erlaubte Erweiterungen + nur Pfade unter der Speicherwurzel.
    """
    try:
        # Nur Pfade unter ~/storage/shared (oder /sdcard) zulassen.
        erlaubt_unter = ("storage/shared", "/sdcard")
        if not any(ank in pfad for ank in erlaubt_unter):
            return {"fehler": "Pfad nicht erlaubt"}
        info = lese_datei_info(pfad)
        if not info.get("ist_bild") or not info.get("data_url"):
            return {"fehler": "Kein Bild / nicht lesbar"}
        return {"name": info["name"], "data_url": info["data_url"]}
    except Exception as e:
        logger.error("Datei-Daten fehlgeschlagen: %s", e)
        return {"fehler": str(e)}


@router.get("")
def dateien_suchen(suche: str = Query("", max_length=200),
                   neueste: bool = Query(True),
                   ordner: str = Query("")):
    """Sucht in den freigegebenen Ordnern nach einem Stichwort.

    Sicher: nur lesend, nur freigegebene Ordner, nur Dateinamen/Erweiterungen
    (kein Inhalt). Leeres `suche` + `neueste=true` liefert die neuesten
    Bilder/Dateien (für Tests: was würde der Agent finden?). `ordner` steuert
    die Priorisierung: "kamera"/"screenshot"/"" (beliebig).
    """
    try:
        # Bei leerem Suchbegriff (Test: "was würde der Agent finden?") die
        # Kamera bevorzugen: DCIM enthält die echten Fotos + kommt zuerst,
        # bevor alte root-/Pictures-Dateien das Limit füllen. `ordner` kann
        # diese Voreinstellung überschreiben (z. B. "screenshot").
        ordner_hinweis = ordner if ordner else ("kamera" if not suche.strip() else "")
        treffer = suche_dateien(suche, neueste_zuerst=neueste, ordner_hinweis=ordner_hinweis)
        return {
            "treffer": treffer,
            "anzahl": len(treffer),
            "ordner": basis_ordner_verfuegbar(),
        }
    except Exception as e:
        logger.error("Dateisuche fehlgeschlagen: %s", e)
        return {"treffer": [], "anzahl": 0, "fehler": str(e), "ordner": []}
