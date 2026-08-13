"""
Router: Wissensspeicher aus den Chat-Archiven

  GET /api/archiv/status         Ist er eingebunden, was steckt drin
  GET /api/archiv/suche?q=...    Hybrid-Suche, zum Ausprobieren und Pruefen

Die Suche wird im Chat automatisch mitgenutzt (siehe router/chat.py). Diese
Endpunkte sind fuer die Fehlersuche und um ohne Umweg zu sehen, was der
Speicher zu einer Frage liefert.

Sicherheit: Nur lesend. Die Datenbank bleibt auf dem Geraet.
"""

import logging

from fastapi import APIRouter, Query

from app.services.archiv_service import archiv_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/archiv", tags=["archiv"])


# Bewusst `def` statt `async def`: SQLite und die Vektorsuche sind blockierend.
# Als Coroutine wuerden sie den Event-Loop und damit laufende Chat-Streams
# aufhalten; synchron schiebt FastAPI sie in einen Threadpool.
@router.get("/status")
def status():
    """Was im Archiv steckt — und welcher Suchweg gerade traegt."""
    return archiv_service.status()


@router.get("/suche")
def suche(
    q: str = Query(..., min_length=2, description="Frage oder Stichwort"),
    top_k: int = Query(default=5, ge=1, le=20),
    modus: str = Query(default="hybrid", pattern="^(hybrid|volltext|semantisch)$"),
):
    """Im Archiv suchen.

    `modus` erlaubt, die beiden Wege einzeln zu pruefen — nuetzlich, wenn
    Treffer fehlen und man wissen will, welcher Weg gerade nicht liefert.
    """
    if modus == "volltext":
        treffer = archiv_service.suche(q, top_k)
    elif modus == "semantisch":
        treffer = archiv_service.semantische_suche(q, top_k)
    else:
        treffer = archiv_service.hybrid(q, top_k)

    return {
        "frage": q,
        "modus": modus,
        "treffer": treffer,
        "anzahl": len(treffer),
    }
