"""Chat API routes."""

import json
import logging
import os
import threading
import time
from datetime import datetime
from typing import Optional, List, Dict, Any, Iterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.config import settings
from app.models import ChatRequest, ChatResponse
from app.services.archiv_service import archiv_service
from app.services.auftrag_service import auftrag_service
from app.services.auftrags_erkennung import ist_auftrag
from app.services.faehigkeiten import stoesst_an_grenze
from app.services.hermes_gateway import hermes_gateway
from app.services.hermes_local import (
    ist_verfuegbar as hermes_local_ist_verfuegbar,
    stream_auftrag as hermes_local_stream_auftrag,
    hermes_registry,
)
from app.services.llm_service import llm_service
from app.services.memory_service import memory_service
from app.services import chat_verlauf
from app.services import sse as sse_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])

# Verlauf liegt jetzt im Service (app.services.chat_verlauf) — Refactoring.
# Re-Export, damit der Rest dieser Datei (und alte Nutzer) identisch weiter
# funktionieren. Memory-Extraktion wird hier injected, damit der Service keine
# harten Imports braucht.
conversations = chat_verlauf.conversations
VERLAUF_DATEI = os.path.join(settings.chroma_persist_dir, "conversations.json")

# Service initialisieren (lädt Verlauf von der Platte).
chat_verlauf.init(VERLAUF_DATEI, settings.chroma_persist_dir)

# Memory-Extraktion an den Service anbinden (gleiche wie bisher).
chat_verlauf.setze_memory_extractor(
    memory_service.extract_and_store_memories
)

# Alias für Abwärtskompat im restlichen Code:
_lade_verlauf = chat_verlauf._lade_verlauf
_speichere_verlauf = chat_verlauf._speichere_verlauf
verlauf_nachricht_anhaengen = chat_verlauf.verlauf_nachricht_anhaengen
_get_or_create_conversation = chat_verlauf._get_or_create_conversation
_finish_exchange = chat_verlauf.finish_exchange
_verlauf_sperre = chat_verlauf._verlauf_sperre




_sse = sse_service._sse
_strom_auftrag_live = sse_service.strom_auftrag_live


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


def _starte_lokale_hermes(
    auftrag: str,
    hinweis: str,
    kategorie: Optional[str],
    komplexitaet: Optional[str],
    chat_verknuepfung: Optional[str] = None,
):
    """Track C im Hintergrund: Lokaler Termux-Hermes bearbeitet den Auftrag und
    strahlt seine Gedanken live ins Auftragsbuch.

    Legt den Auftrag als direkt ``laeuft`` an (damit der Watcher ihn nicht
    doppelt claimt), startet den Hermes-Stream in einem Daemon-Thread und
    schreibt jeden Zwischengedanken als Status-Meldung sowie das Endergebnis
    via ``ergebnis_eintragen``. Das Frontend zeigt die Meldungen live als
    Chat-Blasen — inhaltlich 1:1, wie der Agent sie tippt.

    Returns:
        Dict mit der angelegten Auftrags-Äquivalenz (id, status).
    """
    eintrag = auftrag_service.anlegen_als_arbeitender(
        auftrag,
        hinweis=hinweis,
        kategorie=kategorie,
        komplexitaet=komplexitaet,
    )
    auftrag_id = eintrag["id"]

    # Verknuepfung Auftrag <-> Gespraech VOR dem Thread-Start setzen.
    # Wuerde sie erst nach dem Start geschehen, koennte der Worker die
    # allerersten Hermes-Zwischenmeldungen liefern, bevor seine
    # conversation_id in der Datei steht -> verlauf_nachricht_anhaengen
    # wuerde sie verwerfen. So sind alle Hermes-Meldungen ab der ersten
    # an das Gespraech gebunden und landen im persistenten Verlauf.
    if chat_verknuepfung:
        auftrag_service.setze_chat_verknuepfung(auftrag_id, chat_verknuepfung)

    def _worker():
        try:
            try:
                for ereignis in hermes_local_stream_auftrag(auftrag_id, auftrag):
                    art = ereignis.get("art")
                    text = ereignis.get("text", "")
                    if art == "gedanke" and text:
                        auftrag_service.statusmeldung_hinzufuegen(auftrag_id, text)
                        # Auch in den persistenten Chat-Verlauf, falls verknuepft.
                        _reite_an_verlauf(auftrag_id, "assistant", text)
                    elif art == "ergebnis":
                        auftrag_service.ergebnis_eintragen(
                            auftrag_id, text, erfolg=bool(text)
                        )
                        if text:
                            _reite_an_verlauf(auftrag_id, "assistant", text)
                    elif art == "fehler":
                        auftrag_service.ergebnis_eintragen(
                            auftrag_id, text, erfolg=False
                        )
                        return
            except Exception as e:
                logger.error("Lokaler Hermes-Job abgebrochen (%s): %s", auftrag_id[:8], e)
                auftrag_service.ergebnis_eintragen(
                    auftrag_id, f"Fehler im lokalen Hermes-Job: {e}", erfolg=False
                )
            finally:
                # Auftrag ist final (ergebnis/fehler eingetragen oder Abbruch):
                # den laufenden Hermes-CLI aus der Registry nehmen. Dadurch
                # loest entferne() -> job.beende() -> tmux kill-session aus und
                # der interaktive Agent wird wirklich beendet. Stattdessen
                # verwaisten vorher jede abgeschlossene Programmierung eine
                # offene tmux-Session (Ressourcenschwund ueber die Tage).
                hermes_registry.entferne(auftrag_id)
        except Exception as e:
            logger.error("Lokaler Hermes-Job-Traeger selbst fehlgeschlagen (%s): %s",
                         auftrag_id[:8], e)

    threading.Thread(target=_worker, daemon=True).start()
    return eintrag


def _reite_an_verlauf(auftrag_id: str, role: str, content: str) -> None:
    """Reicht eine Hermes-Nachricht in den persistenten Chat-Verlauf weiter.

    Der Coding-Auftrag fuehrt eine verknuepfte conversation_id; landet die
    Nachricht nur im Auftragsbuch, ist der Chat-Verlauf nach einem Neuladen
    leer. Hier wird die Verknuepfung gelesen und angehaengt, wenn vorhanden.
    """
    try:
        eingang = auftrag_service.einzeln(auftrag_id)
        conv_id = eingang.get("conversation_id") if eingang else None
        if conv_id:
            auftrag_service._in_verlauf_anhaengen(conv_id, role, content)
    except Exception as e:
        logger.warning("Verlauf-Übergabe fehlgeschlagen (%s): %s", auftrag_id[:8], e)


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Process a chat message and return the LLM response."""
    try:
        # Weiche: Coding-/Werkzeug-Auftraege weiterleiten. Bei hochgeladenen
        # Dateien (request.files) NICHT als Coding-Auftrag einordnen — ein
        # Dokument-/Bild-Upload ist immer eine Verständnis-/Analyse-Frage an
        # den LLM, kein Programmier-Kommando an Hermes.
        # Zusätzlich zur ist_auftrag()-Heuristik wird die Fähigkeits-Grenze
        # geprüft (Terminal/Datei/System/Tool-Install) — selbst wenn die
        # Heuristik es nicht als Coding einstuft, delegiert der Agent an
        # Hermes (Toolcall).
        ist_auftrag_val = False
        if not request.files:
            ist_auftrag_val, begruendung, kategorie, komplexitaet = ist_auftrag(request.message)
            if not ist_auftrag_val and stoesst_an_grenze(request.message):
                ist_auftrag_val = True
                begruendung = "Fähigkeits-Grenze (Terminal/Datei/System) – Hermes als Toolcall"
                kategorie = "feature"
                komplexitaet = "mittel"
        else:
            begruendung, kategorie, komplexitaet = "", None, None
        if ist_auftrag_val:
            # Die Track-A/C/B-Weiche (PC → lokal → Buch) liegt jetzt im
            # Routing-Service. Er liefert art/reply/conversation_id; hier wird
            # nur noch die ChatResponse daraus gebaut.
            from app.services.chat_routing import route_auftrag
            res = route_auftrag(
                request.message,
                begruendung,
                kategorie,
                komplexitaet,
                finish_exchange=_finish_exchange,
                get_or_create_conversation=lambda _: _get_or_create_conversation(request.conversation_id),
                starte_lokale_hermes=_starte_lokale_hermes,
                kontext=_baue_kontext(request.message),
            )
            return ChatResponse(
                reply=res["reply"],
                conversation_id=res["conversation_id"],
                memories_used=0,
                memories_created=0,
                sources=[],
                archiv_used=0,
            )

        conversation_id = _get_or_create_conversation(request.conversation_id)
        history = conversations[conversation_id]

        # 1. Retrieve relevant memories from vector DB
        memories = memory_service.retrieve_relevant_memories(
            request.message, top_k=5
        )

        # 1b. Passende Stellen aus den Chat-Archiven – das, was den Agenten
        # über die eigene Vergangenheit sprechen lässt.
        archiv = _archiv_treffer(request.message, request.archiv)

        # 1c. Rolling-Summary der älteren Unterhaltung (Ein-Chat). Begrenzt die
        # History auf die letzten 15 + gibt den kompakten Summary als Zusatz-
        # Kontext weiter, damit die Vergangenheit nicht verloren geht / der
        # Prompt nicht explodiert.
        kontext_summary, _ = _hole_kontext_summary(conversation_id, history, request.message)
        begrenzte_history = history[-15:]

        # 2. Get LLM response with memory context
        reply, quellen = llm_service.chat(
            user_message=request.message,
            conversation_history=begrenzte_history,
            memories=memories,
            web_search=request.web_search,
            model=request.model,
            no_retention=request.no_retention,
            archiv=archiv,
            summary=kontext_summary,
            files=[f.model_dump() for f in request.files] if request.files else None,
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


def _baue_kontext(frage: str) -> str:
    """Baut das kompakte Kontext-Paket für die Hermes-Delegation (Variante C).

    Nimmt die letzten max. 6 Chat-Nachrichten der aktuellen Conversation +
    die 3 relevantesten Erinnerungen (semantisch zur Frage) und kürzt sie auf
    eine handliche Textmenge. So weiß Hermes, worum es im Gespräch geht,
    ohne dass der Prompt explodiert (günstig + reichhaltig).
    """
    konv_id = _get_or_create_conversation(None)
    hist = conversations.get(konv_id, [])
    teile: List[str] = []
    # Letzte bis zu 6 Nachrichten (ohne die aktuelle Frage-Duplikate).
    for m in hist[-6:]:
        rolle = m.get("role", "?")
        inhalt = (m.get("content") or "").strip()
        if not inhalt:
            continue
        # Langen Inhalt kürzen (Kontext kompakt halten).
        if len(inhalt) > 500:
            inhalt = inhalt[:500] + "…"
        teile.append(f"{rolle}: {inhalt}")
    # Relevante Erinnerungen (semantisch zur Frage).
    try:
        mems = memory_service.retrieve_relevant_memories(frage, top_k=3)
        for m in mems:
            inhalt = (m.get("content") or m.get("text") or "").strip()
            if inhalt and len(inhalt) < 400:
                teile.append(f"Erinnerung: {inhalt}")
    except Exception:
        pass  # Kontext ist Bonus — nie die Delegation deswegen brechen.
    if not teile:
        return ""
    return "\n".join(teile)


def _hole_kontext_summary(conversation_id: str, historie: list, frage: str) -> tuple:
    """Holt das Rolling-Summary der Conversation (+ rollt bei Bedarf neu).

    Liefert (summary_text, gerollt). Rollt nur, wenn die Historie über der
    Schwelle liegt UND genug neue Nachrichten seit dem letzten Roll kamen
    (Rate-Limit → günstig). Erhöht den Zähler bei jedem Aufruf.
    """
    from app.services import chat_verlauf, kontext_service
    summary_eintrag = chat_verlauf.summary_holen(conversation_id)
    summary = str(summary_eintrag.get("text") or "")
    anzahl_seit = int(summary_eintrag.get("anzahl_seit_roll") or 0)

    # Kontext-Paket bauen (Rolling-Summary-Logik).
    ergebnis = kontext_service.baue_kontext(
        historie, frage,
        memory_extractor=None,           # Erinnerungen kommen separat in llm_service
        gespeichertes_summary=summary,
        anzahl_seit_roll=anzahl_seit,
    )
    if ergebnis["gerollt"]:
        chat_verlauf.summary_setzen(conversation_id, ergebnis["summary"])
    # Zähler fürs künftige Roll-Limit erhöhen.
    chat_verlauf.summary_erhoehe_zaehler(conversation_id)
    return ergebnis["summary"], ergebnis["gerollt"]


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """Wie /chat, liefert die Antwort aber Stück für Stück (Server-Sent Events)."""
    # Gleiche Weiche wie in /chat: Coding-Auftraege weiterleiten. Bei
    # hochgeladenen Dateien (request.files) NICHT als Coding-Auftrag einordnen
    # — ein Dokument-/Bild-Upload ist eine Verständnis-/Analyse-Frage an den
    # LLM. Zusätzlich stößt ein Fähigkeits-Grenzthema (Terminal/Datei/System)
    # an Hermes als Toolcall, auch wenn ist_auftrag es nicht als Coding sieht.
    ist_auftrag_val = False
    if not request.files:
        ist_auftrag_val, begruendung, kategorie, komplexitaet = ist_auftrag(request.message)
        if not ist_auftrag_val and stoesst_an_grenze(request.message):
            ist_auftrag_val = True
            begruendung = "Fähigkeits-Grenze (Terminal/Datei/System) – Hermes als Toolcall"
            kategorie = "feature"
            komplexitaet = "mittel"
    else:
        begruendung, kategorie, komplexitaet = "", None, None
    if ist_auftrag_val:
        # Kontext-Erweiterung: Frage + Gesprächskontext, damit Hermes nicht
        # blind (nur mit der Frage) arbeitet. (Gleiche Logik wie im Router.)
        kontext_paket = _baue_kontext(request.message)
        herm_aufgabe = request.message
        if kontext_paket and kontext_paket.strip():
            herm_aufgabe = (
                f"{request.message}\n\n"
                "[Kontext aus dem Gespräch (vorherige Nachrichten/Erinnerungen):]\n"
                f"{kontext_paket.strip()}"
            )
        # Wie /chat: erst PC-Hermes (Track A), dann lokalen Hermes
        # (Track C). Nur wenn beides nicht verfuegbar ist, geht der
        # Auftrag ins Buch (Track B).
        hermes_antwort = hermes_gateway.sende_auftrag(herm_aufgabe)
        if hermes_antwort is not None:
            conversation_id = _get_or_create_conversation(request.conversation_id)
            _finish_exchange(conversation_id, request.message, hermes_antwort)
            def pc_baer_ereignisse():
                yield _sse({"delta": hermes_antwort})
                yield _sse({"done": True, "conversation_id": conversation_id,
                            "memories_used": 0, "memories_created": 0,
                            "memory_count": memory_service.get_memory_count(),
                            "archiv_used": 0, "sources": []})
            return StreamingResponse(
                pc_baer_ereignisse(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

        # Track C: Lokaler Hermes startet die Aufgabe im Hintergrund und
        # strahlt Gedanken + Ergebnis live ins Auftragsbuch.
        if hermes_local_ist_verfuegbar():
            # Gespraech ERST anlegen/ermitteln, damit die Verknuepfung
            # vor dem Thread-Start an den Worker geht und das Gespraech
            # im conversations-Dict bereits existiert, wenn die ersten
            # Hermes-Zwischenmeldungen eintreffen.
            conversation_id = _get_or_create_conversation(request.conversation_id)
            eintrag = _starte_lokale_hermes(
                herm_aufgabe,
                hinweis=f"Automatische Erkennung: {begruendung}",
                kategorie=kategorie,
                komplexitaet=komplexitaet,
                chat_verknuepfung=conversation_id,
            )
            reply_text = (
                "🧩 **Hermes-Aufgabe erkannt – erweitertes Werkzeug übernimmt.**\n\n"
                f"📋 **Aufgabe:** {request.message[:150]}…\n\n"
                "Gedanken & Zwischenschritte erscheinen hier live, das "
                "Endergebnis danach.\n"
            )
            _finish_exchange(conversation_id, request.message, reply_text)
            # Verknuepfung Auftrag <-> Gespraech setzt _starte_lokale_hermes
            # bereits VOR dem Thread-Start; kein zweites setzen noetig.

            return StreamingResponse(
                _strom_auftrag_live(eintrag["id"], conversation_id, reply_text),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

        eintrag = auftrag_service.anlegen(
            herm_aufgabe,
            hinweis=f"Automatische Erkennung: {begruendung}",
            kategorie=kategorie,
            komplexitaet=komplexitaet,
        )
        reply_text = (
            "🧩 **Hermes-Aufgabe erkannt – wird bearbeitet.**\n\n"
            f"📋 **Aufgabe:** {request.message[:150]}…\n\n"
            "Hermes nimmt sich der Aufgabe an. Sobald ein Ergebnis vorliegt, "
            "erscheint es live hier.\n"
        )
        conversation_id = _get_or_create_conversation(request.conversation_id)
        _finish_exchange(conversation_id, request.message, reply_text)
        # Auftrag an das Gespraech binden, damit Hermes-Live-Meldungen
        # (Zwischenschritte, Ergebnis) den persistenten Verlauf füllen.
        auftrag_service.setze_chat_verknuepfung(eintrag["id"], conversation_id)

        def auftrag_ereignisse():
            # In zwei Teile zerlegt: erst Text, dann fertig - die UI haengt
            # ihr "fertig"-Handle an das done-Event.
            yield _sse({"delta": reply_text})
            yield _sse({
                "done": True,
                "conversation_id": conversation_id,
                "memories_used": 0,
                "memories_created": 0,
                "memory_count": memory_service.get_memory_count(),
                "archiv_used": 0,
                "sources": [],
            })

        return StreamingResponse(
            auftrag_ereignisse(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

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
                    files=[f.model_dump() for f in request.files] if request.files else None,
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