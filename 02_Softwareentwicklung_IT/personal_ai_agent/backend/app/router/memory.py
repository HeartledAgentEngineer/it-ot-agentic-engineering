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