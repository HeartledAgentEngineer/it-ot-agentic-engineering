"""Router: pCloud (nur lesend) — Status, Ordnerliste, Suche, Vorschau, Datei.

  GET /api/cloud/status                  Kontozusammenfassung (Quota, E-Mail maskiert)
  GET /api/cloud/liste?folderid=0        Eintraege EINES Ordners, Ordner zuerst
  GET /api/cloud/suche?q=...&folderid=0  Namenssuche in EINEM Ordner (nicht rekursiv)
  GET /api/cloud/thumb?fileid=...        Vorschaubild (live: JPEG)
  GET /api/cloud/datei?fileid=...        Datei-Download (max. 25 MB)

Sicherheit:
  * Nur lesend — es gibt hier bewusst keine Schreib-, Umbenenn- oder
    Loeschroute (Regeln siehe ``services/pcloud_service.py``).
  * Ist kein Token konfiguriert, antworten ALLE Endpunkte mit HTTP 503 und
    einer klaren deutschen Meldung statt mit einem Absturz.
  * Ist der Key-Schutz aktiv (``settings.api_key``), greift er wie bei allen
    anderen /api-Routen (Registrierung in ``app/main.py``).
  * Antworten tragen nie den Token; pCloud-Fehler werden zu HTTP 502
    (bzw. 413 bei zu grossen Dateien) samt Fehlertext der API.
"""

import logging
from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.services.pcloud_service import (
    PCloudFehler,
    PCloudNichtKonfiguriert,
    PCloudService,
    PCloudZuGross,
    media_typ_fuer_bild,
    pcloud_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cloud", tags=["cloud"])

NICHT_KONFIGURIERT = (
    "pCloud ist nicht konfiguriert: In der .env des Backends fehlt "
    "PCLOUD_TOKEN (Host-Setting PCLOUD_HOST, Standard eapi.pcloud.com)."
)


def _dienst() -> PCloudService:
    """Dienst-Instanz oder 503 mit klarer Meldung (statt Absturz)."""
    if not pcloud_service.ist_konfiguriert():
        raise HTTPException(status_code=503, detail=NICHT_KONFIGURIERT)
    return pcloud_service


def _ergebnis(arbeit: Callable[[], Any]) -> Any:
    """Dienst-Aufruf ausfuehren und pCloud-Fehler in HTTP-Codes uebersetzen.

    Die Fehlertexte kommen bereits ohne Token aus dem Dienst; hier wird
    nur noch der passende Statuscode gewaehlt.
    """
    try:
        return arbeit()
    except PCloudNichtKonfiguriert as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except PCloudZuGross as e:
        raise HTTPException(status_code=413, detail=str(e)) from e
    except PCloudFehler as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


# Bewusst `def` statt `async def`: httpx ist synchron und blockierend. Als
# Coroutine wuerde der Aufruf den Event-Loop (laufende Chat-Streams) anhalten;
# synchron schiebt FastAPI ihn in einen Threadpool — wie in router/archiv.py.
@router.get("/status")
def status():
    """Kontozusammenfassung: Quota/belegt in GB, premium, E-Mail maskiert."""
    dienst = _dienst()
    return _ergebnis(lambda: dienst.status())


@router.get("/liste")
def liste(
    folderid: int = Query(default=0, ge=0, description="folderid aus /liste; 0 = Wurzel"),
):
    """Eintraege EINES Ordners — Ordner zuerst, dann Name (nicht rekursiv)."""
    dienst = _dienst()
    eintraege = _ergebnis(lambda: dienst.liste(folderid))
    return {"folderid": folderid, "anzahl": len(eintraege), "eintraege": eintraege}


@router.get("/suche")
def suche(
    q: str = Query(..., min_length=1, description="Begriff, Gross-/Kleinschreibung egal"),
    folderid: int = Query(default=0, ge=0, description="Ordner, der durchsucht wird"),
):
    """Namenssuche in EINEM Ordner (max. 50 Treffer, kein rekursiver Lauf)."""
    dienst = _dienst()
    treffer = _ergebnis(lambda: dienst.suche(q, folderid))
    return {"frage": q, "folderid": folderid, "anzahl": len(treffer), "treffer": treffer}


@router.get("/thumb")
def thumb(
    fileid: int = Query(..., ge=0, description="fileid aus /liste"),
    groesse: str = Query(default="120x120", pattern="^(32x32|120x120|480x480|800x800)$"),
):
    """Vorschaubild eines Bildes — kommt als Bild zurueck (live: JPEG).

    Groessen: 32x32 und 120x120 (pCloud-Doku) sowie 480x480 und 800x800
    (live geprueft 27.09.2026; fuer Screenshots noetig, weil Text bei
    120x120 nicht lesbar ist). Der Medientyp wird aus den ersten Bytes
    bestimmt; pCloud liefert derzeit JPEG (siehe services/pcloud_service.py).
    """
    dienst = _dienst()
    daten = _ergebnis(lambda: dienst.thumb(fileid, groesse))
    return Response(
        content=daten,
        media_type=media_typ_fuer_bild(daten),
        headers={"Cache-Control": "no-store"},
    )


@router.get("/datei")
def datei(fileid: int = Query(..., ge=0, description="fileid aus /liste")):
    """Datei herunterladen (max. 25 MB) — Antwort als Datei-Download."""
    dienst = _dienst()
    daten = _ergebnis(lambda: dienst.datei_bytes(fileid))
    return Response(
        content=daten,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="pcloud-{fileid}"',
            "Cache-Control": "no-store",
        },
    )
