"""Chat API routes."""

import logging
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException

from app.models import ChatRequest, ChatResponse
from app.services.llm_service import llm_service
from app.services.memory_service import memory_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])

# In-memory conversation store (MVP – later replace with DB)
conversations: Dict[str, List[Dict[str, str]]] = {}
next_conversation_id: int = 1


def _get_or_create_conversation(conversation_id: Optional[str]) -> str:
    """Get existing conversation or create a new one."""
    global next_conversation_id

    if conversation_id and conversation_id in conversations:
        return conversation_id

    new_id = f"conv_{next_conversation_id}"
    next_conversation_id += 1
    conversations[new_id] = []
    return new_id


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Process a chat message and return the LLM response."""
    try:
        conversation_id = _get_or_create_conversation(request.conversation_id)
        history = conversations[conversation_id]

        # 1. Retrieve relevant memories from vector DB
        memories = memory_service.retrieve_relevant_memories(
            request.message, top_k=5
        )

        # 2. Get LLM response with memory context
        reply = llm_service.chat(
            user_message=request.message,
            conversation_history=history,
            memories=memories,
        )

        # 3. Store user message and assistant reply in conversation history
        history.append({"role": "user", "content": request.message})
        history.append({"role": "assistant", "content": reply})

        # 4. Extract and store new memories from this exchange
        stored_memory_ids = memory_service.extract_and_store_memories(
            user_message=request.message,
            llm_reply=reply,
            conversation_id=conversation_id,
        )

        return ChatResponse(
            reply=reply,
            conversation_id=conversation_id,
            memories_used=len(memories),
            memories_created=len(stored_memory_ids),
        )

    except Exception as e:
        logger.error("Chat error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations")
async def list_conversations():
    """List all active conversations."""
    return {
        "conversations": [
            {
                "id": cid,
                "message_count": len(msgs),
                "last_message": msgs[-1]["content"][:100] if msgs else "",
            }
            for cid, msgs in conversations.items()
        ],
        "total": len(conversations),
    }