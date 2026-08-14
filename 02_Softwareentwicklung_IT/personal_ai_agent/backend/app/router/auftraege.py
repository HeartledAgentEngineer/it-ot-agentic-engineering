"""Router: Auftragsbuch fuer den Coding-Agenten.

  POST /api/auftraege                   Auftrag eintragen (Oberflaeche)
  GET  /api/auftraege                   Liste mit Stand (Oberflaeche)
  GET  /api/auftraege/naechster         naechsten offenen abholen (Hermes)
  GET  /api/auftraege/{id}              einzelner Stand (Oberflaeche)
  POST /api/auftraege/{id}/ergebnis     Rueckmeldung (Hermes)

Warum es diesen Umweg gibt: Der Coding-Agent laeuft als eigene App auf
demselben Geraet und hat keinen eingehenden HTTP-Zugang. Anrufen laesst er
sich nicht - er muss selbst fragen. Das Auftragsbuch ist der Ort, an dem
beide Seiten sich treffen, ohne dass eine die andere erreichen muss.

Sicherheit: Diese Routen laufen ohne Authentifizierung, wie der Rest des
Servers auch - er hoert nur im Heimnetz. Sobald er von aussen erreichbar
waere, gehoert hier ein Schluessel davor: Wer Auftraege eintragen kann,
laesst fremden Code schreiben.
"""

import logging

from fastapi import APIRouter, HTTPException, Query

from app.models import (
    AuftragCreate,
    AuftragItem,
    AuftragListResponse,
    ErgebnisCreate,
)
from app.services.auftrag_service import auftrag_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auftraege", tags=["auftraege"])


# Bewusst `def` statt `async def`: Der Dienst liest und schreibt eine Datei
# und haelt dabei eine Sperre. In einer async-Funktion wuerde das den
# Event-Loop anhalten und einen laufenden Chat-Stream ausbremsen; als
# synchrone Funktion schiebt FastAPI sie in einen Threadpool.
@router.post("", response_model=AuftragItem, status_code=201)
def auftrag_anlegen(auftrag: AuftragCreate):
    """Traegt einen Auftrag ein. Abgeholt wird er beim naechsten Lauf."""
    try:
        return auftrag_service.anlegen(auftrag.auftrag, auftrag.hinweis)
    except Exception as fehler:
        logger.error("Auftrag anlegen fehlgeschlagen: %s", fehler)
        raise HTTPException(status_code=500, detail=str(fehler))


@router.get("", response_model=AuftragListResponse)
def auftraege_auflisten(limit: int = Query(default=50, ge=1, le=200)):
    """Alle Auftraege, neueste zuerst."""
    try:
        auftraege = [
            AuftragItem.model_validate(eintrag)
            for eintrag in auftrag_service.alle(limit=limit)
        ]
        return AuftragListResponse(auftraege=auftraege, total=len(auftraege))
    except Exception as fehler:
        logger.error("Auftraege auflisten fehlgeschlagen: %s", fehler)
        raise HTTPException(status_code=500, detail=str(fehler))


# Muss vor /{auftrag_id} stehen: Ein Pfadplatzhalter faengt sonst auch
# "naechster" ab und suchte nach einem Auftrag mit dieser ID.
@router.get("/naechster")
def naechsten_auftrag_abholen():
    """Gibt den aeltesten offenen Auftrag aus - fuer den Coding-Agenten.

    Der Auftrag gilt danach als in Arbeit und wird nicht noch einmal
    ausgegeben. Ist nichts zu tun, kommt `auftrag: null` zurueck statt
    eines Fehlers: Der haeufigste Fall ist "nichts zu tun", und der ist
    kein Problem, das gemeldet werden muesste.
    """
    try:
        auftrag = auftrag_service.naechster_offener()
        if auftrag is None:
            return {"auftrag": None, "hinweis": "Nichts zu tun."}
        return {"auftrag": auftrag}
    except Exception as fehler:
        logger.error("Auftrag abholen fehlgeschlagen: %s", fehler)
        raise HTTPException(status_code=500, detail=str(fehler))


@router.get("/{auftrag_id}", response_model=AuftragItem)
def auftrag_ansehen(auftrag_id: str):
    """Stand eines einzelnen Auftrags."""
    auftrag = auftrag_service.einzeln(auftrag_id)
    if auftrag is None:
        raise HTTPException(status_code=404, detail="Auftrag nicht gefunden")
    return auftrag


@router.post("/{auftrag_id}/ergebnis", response_model=AuftragItem)
def ergebnis_melden(auftrag_id: str, ergebnis: ErgebnisCreate):
    """Nimmt die Rueckmeldung des Coding-Agenten entgegen."""
    try:
        auftrag = auftrag_service.ergebnis_eintragen(
            auftrag_id, ergebnis.ergebnis, ergebnis.erfolg
        )
        if auftrag is None:
            raise HTTPException(status_code=404, detail="Auftrag nicht gefunden")
        return auftrag
    except HTTPException:
        raise
    except Exception as fehler:
        logger.error("Ergebnis eintragen fehlgeschlagen: %s", fehler)
        raise HTTPException(status_code=500, detail=str(fehler))
