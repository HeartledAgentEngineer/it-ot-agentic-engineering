"""Chat API routes."""

import json
import logging
import os
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.config import settings
from app.models import ChatRequest, ChatResponse
from app.services.archiv_service import archiv_service
from app.services.llm_service import llm_service
from app.services.memory_service import memory_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])

# Gespraeche. Frueher lagen sie ausschliesslich hier im Arbeitsspeicher -
# jeder Serverneustart, jeder Absturz und jedes Update loeschten damit den
# gesamten Verlauf. Fuer einen Agenten, der sich Dinge merken soll, ist das
# ein Widerspruch: Das Gedaechtnis ueberlebte, das Gespraech nicht.
conversations: Dict[str, List[Dict[str, str]]] = {}
next_conversation_id: int = 1

# Liegt neben dem Gedaechtnis, damit alles Dauerhafte an einem Ort steht.
VERLAUF_DATEI = os.path.join(settings.chroma_persist_dir, "conversations.json")


def _lade_verlauf() -> None:
    """Holt die Gespraeche von der Platte. Fehlt die Datei, faengt es leer an."""
    global next_conversation_id
    try:
        with open(VERLAUF_DATEI, "r", encoding="utf-8") as f:
            daten = json.load(f)
        conversations.update(daten.get("conversations", {}))
        next_conversation_id = int(daten.get("next_id", 1))
        logger.info(
            "Gespraechsverlauf geladen: %d Gespraeche", len(conversations)
        )
    except FileNotFoundError:
        logger.info("Kein gespeicherter Verlauf – erster Start")
    except Exception as e:
        # Eine kaputte Datei darf den Server nicht am Starten hindern.
        logger.warning("Verlauf nicht lesbar, beginne leer: %s", e)


def _speichere_verlauf() -> None:
    """Schreibt den Verlauf weg. Fehler hier duerfen den Chat nicht abbrechen."""
    try:
        os.makedirs(settings.chroma_persist_dir, exist_ok=True)
        with open(VERLAUF_DATEI, "w", encoding="utf-8") as f:
            json.dump(
                {"next_id": next_conversation_id, "conversations": conversations},
                f,
                ensure_ascii=False,
            )
    except Exception as e:
        logger.warning("Verlauf konnte nicht gespeichert werden: %s", e)


_lade_verlauf()


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
    # Sofort wegschreiben, nicht erst beim Beenden: Ein Serverabsturz oder
    # ein hartes Beenden der App darf hoechstens den laufenden Austausch
    # kosten, nicht das ganze Gespraech.
    _speichere_verlauf()

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


def _archiv_treffer(frage: str, aktiv: bool) -> List[Dict[str, Any]]:
    """Passende Stellen aus den Chat-Archiven holen.

    Scheitert die Suche, geht die Anfrage trotzdem durch – nur ohne
    Vergangenheitswissen. Ein kaputtes Archiv darf den Chat nicht lahmlegen.
    """
    if not aktiv or not archiv_service.is_available:
        return []
    try:
        return archiv_service.hybrid(frage)
    except Exception as e:
        logger.warning("Archivsuche uebersprungen: %s", e)
        return []


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

        # 1b. Passende Stellen aus den Chat-Archiven – das, was den Agenten
        # über die eigene Vergangenheit sprechen lässt.
        archiv = _archiv_treffer(request.message, request.archiv)

        # 2. Get LLM response with memory context
        reply, quellen = llm_service.chat(
            user_message=request.message,
            conversation_history=history,
            memories=memories,
            web_search=request.web_search,
            model=request.model,
            no_retention=request.no_retention,
            archiv=archiv,
        )

        # 3./4. Verlauf fortschreiben und Erinnerungen ableiten
        memories_created = _finish_exchange(conversation_id, request.message, reply)

        return ChatResponse(
            reply=reply,
            conversation_id=conversation_id,
            memories_used=len(memories),
            memories_created=memories_created,
            sources=quellen,
            archiv_used=len(archiv),
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
    archiv = _archiv_treffer(request.message, request.archiv)

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
                    no_retention=request.no_retention,
                    archiv=archiv,
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
            "archiv_used": len(archiv),
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


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Liefert die Nachrichten eines Gespraechs.

    Damit kann die Oberflaeche nach einem Neustart dort weitermachen, wo
    sie war. Ohne das waere der Verlauf zwar gespeichert, aber unsichtbar.
    """
    if conversation_id not in conversations:
        raise HTTPException(status_code=404, detail="Gespräch nicht gefunden")
    return {
        "id": conversation_id,
        "messages": conversations[conversation_id],
    }