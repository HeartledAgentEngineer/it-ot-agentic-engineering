"""Chat API routes."""

import json
import logging
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

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


def _finish_exchange(conversation_id: str, user_message: str, reply: str) -> int:
    """Austausch in den Verlauf schreiben und daraus Erinnerungen ableiten.

    Wird von beiden Chat-Wegen genutzt. Beim Streaming läuft das auch dann,
    wenn der Client mitten im Stream abbricht – sonst wäre das Gespräch weg.

    Returns:
        Anzahl neu gespeicherter Erinnerungen.
    """
    if not reply:
        return 0

    history = conversations[conversation_id]
    history.append({"role": "user", "content": user_message})
    history.append({"role": "assistant", "content": reply})

    try:
        return len(
            memory_service.extract_and_store_memories(
                user_message=user_message,
                llm_reply=reply,
                conversation_id=conversation_id,
            )
        )
    except Exception as e:
        logger.warning("Gedächtnis-Extraktion fehlgeschlagen: %s", e)
        return 0


def _sse(payload: Dict[str, Any]) -> str:
    """Ein Ereignis im Server-Sent-Events-Format."""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


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
        reply, quellen = llm_service.chat(
            user_message=request.message,
            conversation_history=history,
            memories=memories,
            web_search=request.web_search,
            model=request.model,
        )

        # 3./4. Verlauf fortschreiben und Erinnerungen ableiten
        memories_created = _finish_exchange(conversation_id, request.message, reply)

        return ChatResponse(
            reply=reply,
            conversation_id=conversation_id,
            memories_used=len(memories),
            memories_created=memories_created,
            sources=quellen,
        )

    except Exception as e:
        logger.error("Chat error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """Wie /chat, liefert die Antwort aber Stück für Stück (Server-Sent Events)."""
    conversation_id = _get_or_create_conversation(request.conversation_id)
    history = conversations[conversation_id]
    memories = memory_service.retrieve_relevant_memories(request.message, top_k=5)

    def ereignisse():
        teile: List[str] = []
        quellen: List[Dict[str, str]] = []
        try:
            try:
                for ereignis in llm_service.chat_stream(
                    user_message=request.message,
                    conversation_history=history,
                    memories=memories,
                    web_search=request.web_search,
                    model=request.model,
                ):
                    if ereignis.get("sources"):
                        quellen.extend(ereignis["sources"])
                        yield _sse({"sources": ereignis["sources"]})
                        continue
                    stueck = ereignis.get("delta")
                    if stueck:
                        teile.append(stueck)
                        yield _sse({"delta": stueck})
            except Exception as e:
                logger.error("Streaming fehlgeschlagen: %s", e)
                # Übersetzt Ablehnungen wegen der Datenschutz-Einstellungen in
                # einen Satz, der sagt, was zu tun ist.
                yield _sse({"error": llm_service.fehlertext(e)})
        finally:
            # Läuft auch bei Abbruch durch den Client (Bildschirmsperre,
            # Verbindungsverlust). Hier wird bewusst nichts gesendet – ein
            # yield waehrend GeneratorExit wuerde einen Fehler ausloesen.
            anzahl_neu = _finish_exchange(
                conversation_id, request.message, "".join(teile)
            )

        # Wird uebersprungen, wenn der Client abgebrochen hat.
        yield _sse({
            "done": True,
            "conversation_id": conversation_id,
            "memories_used": len(memories),
            "memories_created": anzahl_neu,
            "memory_count": memory_service.get_memory_count(),
            # Nochmals gesammelt – falls ein Zwischenereignis verloren ging.
            "sources": quellen,
        })

    return StreamingResponse(
        ereignisse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # verhindert Pufferung durch Zwischenschichten
        },
    )


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