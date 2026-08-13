"""Memory API routes for viewing and managing stored memories."""

import logging
from typing import List

from fastapi import APIRouter, HTTPException, Query

from app.models import MemoryItem, MemoryCreate, MemoryListResponse
from app.services.memory_service import memory_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/memory", tags=["memory"])


@router.get("", response_model=MemoryListResponse)
async def list_memories(limit: int = Query(default=50, ge=1, le=200)):
    """Get all stored memories."""
    try:
        memories_data = memory_service.get_all_memories(limit=limit)
        memories = [
            MemoryItem(
                id=m.get("id"),
                content=m.get("content", ""),
                category=m.get("category", "fact"),
                importance=m.get("importance", 3),
                timestamp=m.get("timestamp"),
                conversation_id=m.get("conversation_id"),
            )
            for m in memories_data
        ]
        return MemoryListResponse(memories=memories, total=len(memories))
    except Exception as e:
        logger.error("Failed to list memories: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=dict)
async def create_memory(memory: MemoryCreate):
    """Manually create a new memory."""
    try:
        memory_id = memory_service.store_memory(
            content=memory.content,
            category=memory.category,
            importance=memory.importance,
            conversation_id=memory.conversation_id,
        )
        return {"id": memory_id, "status": "created"}
    except Exception as e:
        logger.error("Failed to create memory: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/count")
async def memory_count():
    """Get the number of stored memories."""
    try:
        return {"count": memory_service.get_memory_count()}
    except Exception as e:
        logger.error("Failed to get memory count: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/vektoren")
async def vektoren_nachruesten():
    """Bettet Erinnerungen nach, die noch keinen Vektor haben.

    Bewusst von Hand ausgeloest: Es kostet einen API-Aufruf je Eintrag.
    Ohne Vektor findet die Bedeutungssuche einen Eintrag nie.
    """
    try:
        return memory_service.ruste_vektoren_nach()
    except Exception as e:
        logger.error("Nachruesten fehlgeschlagen: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/wiederholungen")
async def wiederholungen_aufraeumen(
    ausfuehren: bool = Query(
        default=False,
        description="false zeigt nur, was wegfiele; erst true loescht wirklich",
    )
):
    """Raeumt mehrfach gespeicherte Fakten aus dem Gedaechtnis.

    Standardmaessig ein Trockenlauf. Das ist Absicht: Geloeschtes ist hier
    nicht wiederherstellbar, und wer aufraeumt, sollte vorher sehen, was
    verschwindet. Der jeweils aelteste Eintrag bleibt stehen.
    """
    try:
        return memory_service.entferne_wiederholungen(nur_zeigen=not ausfuehren)
    except Exception as e:
        logger.error("Aufraeumen fehlgeschlagen: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/clear")
async def clear_memories():
    """Clear all memories (dangerous – for testing only)."""
    try:
        count_before = memory_service.get_memory_count()
        memory_service.clear_memories()
        return {
            "status": "cleared",
            "deleted_count": count_before,
        }
    except Exception as e:
        logger.error("Failed to clear memories: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# Muss hinter /clear und /count stehen: Ein Pfadplatzhalter faengt sonst
# auch diese Namen ab, und "clear" waere ploetzlich eine Erinnerungs-ID.
@router.delete("/{memory_id}")
async def einzelne_erinnerung_loeschen(memory_id: str):
    """Loescht einen einzelnen Eintrag.

    Noetig, weil das Gedaechtnis auch Falsches aufnimmt - erfundene
    Vorlieben etwa. Bisher blieb nur, alles zu leeren; ein einzelner
    falscher Eintrag kostete dann auch alle richtigen.
    """
    try:
        if not memory_service.loesche_erinnerung(memory_id):
            raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")
        return {"status": "geloescht", "id": memory_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Loeschen fehlgeschlagen: %s", e)
        raise HTTPException(status_code=500, detail=str(e))