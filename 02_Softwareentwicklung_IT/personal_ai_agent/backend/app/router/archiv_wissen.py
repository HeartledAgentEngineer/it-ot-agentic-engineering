"""
Router: Wissensspeicher — Zeitachse, Original-Nachlesen, Bewusstsein.

  GET /api/archiv/wissen/statistik    Anzahl Gespräche/Nachrichten je Quelle,
                                      Zeitraum, Themen-Häufigkeit
  GET /api/archiv/wissen/chronik      älteste/neueste Gespräche mit Datum+Thema
  GET /api/archiv/wissen/frage        Hybridsuche, Treffer zeitlich sortiert
  GET /api/archiv/wissen/original     Originaltext einer Fundstelle + Kontext
  GET /api/archiv/wissen/ueberblick   Prompt-Baustein „was mein Agent weiß"

Diese Datei ist absichtlich **neu und separat** von ``router/archiv.py``
(dort stehen ``/status`` und ``/suche``): Der Haupt-Agent hängt sie mit einer
Zeile in ``app/main.py`` ein, ohne dass zwei Stränge dieselbe Datei anfassen.

Einhängen in ``app/main.py``::

    from app.router import ..., archiv_wissen        # Import ergänzen
    app.include_router(archiv_wissen.router)         # neben den anderen

Sicherheit: Nur lesend. Die Archivinhalte bleiben auf dem Gerät; nach außen
geht höchstens die Suchfrage zur Einbettung (siehe ``archiv_suche.py``).
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Query

from app.services.archiv_suche import ArchivSuche, archiv_suche

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/archiv/wissen", tags=["archiv-wissen"])


def _dienst(service: Any = None) -> ArchivSuche:
    """Der Archiv-Dienst — in Tests durch eine Attrappe ersetzbar.

    Bewusst ein Argument statt eines Modul-Imports im Rumpf: So kann der
    Testclient einen winzigen Index im ``tmp_path`` unterjubeln, ohne dass
    das echte Archiv angefasst wird.
    """
    return service or archiv_suche


# Bewusst `def` statt `async def`: SQLite und die Vektorrechnung blockieren.
# Als Coroutine würden sie den Event-Loop und damit laufende Chat-Streams
# aufhalten; synchron schiebt FastAPI sie in einen Threadpool.
@router.get("/statistik")
def statistik() -> Dict[str, Any]:
    """Was steckt im Wissensspeicher — Zahlen je Quelle, Zeitraum, Themen."""
    return _dienst().statistik()


@router.get("/chronik")
def chronik(
    richtung: str = Query(default="alt", pattern="^(alt|neu)$"),
    limit: int = Query(default=10, ge=1, le=200),
) -> Dict[str, Any]:
    """Die ältesten oder die neuesten Gespräche — Datum, Quelle, Thema."""
    return _dienst().chronik(richtung=richtung, limit=limit)


@router.get("/frage")
def frage(
    q: str = Query(..., min_length=2, description="Frage oder Stichwort"),
    top_k: int = Query(default=5, ge=1, le=20),
    modus: str = Query(default="hybrid", pattern="^(hybrid|volltext|vektor)$"),
) -> Dict[str, Any]:
    """Hybrid suchen und die Treffer **zeitlich sortiert** zurückgeben.

    Das Ergebnis trägt immer ``sicher``/``grund``; bei ``sicher: false``
    steht eine fertige ``rueckfrage`` an Sebastian darin statt einer
    behaupteten Antwort. Jeder Treffer trägt einen ``zeiger`` ins Original.
    """
    return _dienst().hybrid(q, top_k=top_k, modus=modus)


@router.get("/original")
def original(
    chat_kennung: str = Query(..., min_length=1, description="conversation_id aus dem Zeiger"),
    ordinal: int = Query(..., ge=0, description="Nachrichten-Ordinal aus dem Zeiger"),
    kontext: int = Query(default=1, ge=0, le=10, description="Nachrichten davor/danach"),
) -> Dict[str, Any]:
    """Den **unveränderten** Originaltext der Fundstelle nachlesen.

    Stufe 2 der Suche: Der Treffer zeigt *wo*, hier steht *was* — gekürzt
    wird nichts.
    """
    return _dienst().original(chat_kennung=chat_kennung, ordinal=ordinal, kontext=kontext)


@router.get("/ueberblick")
def ueberblick() -> Dict[str, Any]:
    """Der Baustein „was mein Agent weiß" — Quellen, Zeitraum, Regeln.

    Enthält bewusst keine Archivinhalte, nur Kennzahlen und die Nutzungsregel
    („vor der Web-Suche zuerst hier suchen"). Gedacht zum Einbau in den
    System-Prompt — Einbauort steht in ``docs/konzept-wissensspeicher.md``.
    """
    return _dienst().ueberblick()
