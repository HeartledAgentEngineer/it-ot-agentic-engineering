"""
Router: Wissensspeicher aus den Chat-Archiven

  GET /api/archiv/status         Ist er eingebunden, was steckt drin
  GET /api/archiv/suche?q=...    Hybrid-Suche, zum Ausprobieren und Pruefen

Die Suche wird im Chat automatisch mitgenutzt (siehe router/chat.py). Diese
Endpunkte sind fuer die Fehlersuche und um ohne Umweg zu sehen, was der
Speicher zu einer Frage liefert.

Gesucht wird ueber den **Standardweg** (``archiv_standard.StandardArchiv``):
erst der volle Index mit dem WhatsApp-Vollbestand, dann der alte Dienst — genau
wie im Chat. Bis zum 11.10.2026 fragten diese Endpunkte den **alten** Dienst
allein; sie zeigten damit einen anderen Stand als der Chat (kein WhatsApp) und
verdeckten so den Fehler, den sie finden sollten (Sebastians Befund Nr. 3).

Sicherheit: Nur lesend. Die Datenbank bleibt auf dem Geraet.
"""

import logging

from fastapi import APIRouter, Query

from app.services.archiv_standard import StandardArchiv

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/archiv", tags=["archiv"])


# Bewusst `def` statt `async def`: SQLite und die Vektorsuche sind blockierend.
# Als Coroutine wuerden sie den Event-Loop und damit laufende Chat-Streams
# aufhalten; synchron schiebt FastAPI sie in einen Threadpool.
@router.get("/status")
def status():
    """Was im Archiv steckt — und welcher Suchweg gerade traegt (``quelle``)."""
    return StandardArchiv().status()


@router.get("/suche")
def suche(
    q: str = Query(..., min_length=2, description="Frage oder Stichwort"),
    top_k: int = Query(default=5, ge=1, le=20),
    modus: str = Query(default="hybrid", pattern="^(hybrid|volltext|semantisch)$"),
):
    """Im Archiv suchen — ueber denselben Weg wie der Chat.

    `modus` erlaubt, die beiden Wege einzeln zu pruefen — nuetzlich, wenn
    Treffer fehlen und man wissen will, welcher Weg gerade nicht liefert.
    """
    dienst = StandardArchiv()
    if modus == "volltext":
        treffer = dienst.suche(q, top_k)
    elif modus == "semantisch":
        treffer = dienst.semantische_suche(q, top_k)
    else:
        treffer = dienst.hybrid(q, top_k)

    return {
        "frage": q,
        "modus": modus,
        "treffer": treffer,
        "anzahl": len(treffer),
        "quelle": dienst.quelle,
    }
