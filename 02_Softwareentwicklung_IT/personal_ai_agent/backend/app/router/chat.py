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
from app.services.hermes_gateway import hermes_gateway
from app.services.hermes_local import (
    ist_verfuegbar as hermes_local_ist_verfuegbar,
    stream_auftrag as hermes_local_stream_auftrag,
)
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


# Schuetzt den Verlauf gegen gleichzeitige Aenderungen: Waehrend ein
# Coding-Auftrag im Hintergrund-Thread laeuft (Track C), schreibt das
# Auftragsbuch Live-Nachrichten von Hermes hierher, waehrend im selben
# Moment der Chat-Thread (Verlauf speichern) oder ein Streaming-Thread
# schreibt. Ohne Sperre kann das die JSON-Datei zerhacken.
_verlauf_sperre = threading.Lock()


def verlauf_nachricht_anhaengen(conversation_id, role, content) -> None:
    """Haengt eine Agenten-Nachricht an ein Gespraech und schreibt den Verlauf weg.

    Wird vom Auftragsbuch aufgerufen, wenn der Coding-Agent (Hermes) waehrend
    eines Coding-Auftrags eine Zwischenmeldung oder ein Ergebnis liefert. So
    landen diese Nachrichten auch im persistenten Verlauf und ueberleben ein
    Neuladen der Oberflaeche — statt nur als kurzlebige Chat-Blasen im
    Client-Speicher zu stehen.

    Ein unbekanntes oder fehlendes Gespraech stoert den Auftrag nicht; auch
    ein Schreibfehler darf das Auftragsbuch nicht abbrechen.
    """
    try:
        with _verlauf_sperre:
            if not conversation_id or conversation_id not in conversations:
                return
            if not content:
                return
            conversations[conversation_id].append(
                {
                    "role": role,
                    "content": content,
                    "zeit": datetime.now().astimezone().isoformat(timespec="seconds"),
                }
            )
            _speichere_verlauf()
    except Exception as e:
        logger.warning(
            "Live-Nachricht konnte nicht in den Verlauf uebernommen werden: %s", e
        )


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
    with _verlauf_sperre:
        jetzt = datetime.now().astimezone().isoformat(timespec="seconds")
        history.append({"role": "user", "content": user_message, "zeit": jetzt})
        history.append({"role": "assistant", "content": reply, "zeit": jetzt})
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


def _strom_auftrag_live(auftrag_id, conversation_id, reply_text) -> Iterator[str]:
    """Offene Live-Strecke fuer Track C im Chat-Stream.

    Der lokale Hermes laeuft im Daemon-Thread und schreibt seine Gedanken
    waehrend der ganzen Bearbeitung als ``status_meldungen`` ins Auftragsbuch.
    Dieser Generator bleibt deshalb NICHT bei der Bestaetigung stehen, sondern
    offen: Er liest das Buch periodisch und reicht jede neue Zwischenmeldung
    als weiteres Antwort-Haeppchen durch. Erst wenn der Auftrag ``fertig``
    (oder ``fehlgeschlagen``) ist, kommt das ``done``-Ereignis — zusammen mit
    dem Endergebnis. So bleibt die Kette Frontend -> Server -> Hermes eine
    einzige durchgehende Verbindung statt "Request schliessen, dann 3s-Polling".

    Der 3-Sekunden-Tracker im Frontend bleibt als Fallback/Rueckversicherung
    bestehen (z.B. wenn die Verbindung unterwegs abreisst); er wird nur nicht
    mehr als primaeres Transportmittel gebraucht.
    """
    # Haeppchen 1: sofort die "Auftrag erkannt"-Bestaetigung.
    yield _sse({"delta": reply_text})
    gesehen = 0  # wie viele status_meldungen bereits durchgereicht wurden
    letzte_aktivitaet = time.time()
    while True:
        try:
            aktuell = auftrag_service.einzeln(auftrag_id)
        except Exception:
            aktuell = None
        status = (aktuell or {}).get("status")
        meldungen = (aktuell or {}).get("status_meldungen", []) or []

        for meldung in meldungen[gesehen:]:
            gesehen += 1
            if meldung:
                # Eigene gedaanke-Ereignis (nicht delta): Das Frontend zeigt
                # jede Hermes-Zwischenmeldung als EIGENE Bubble statt sie in
                # die laufende Antwort-Blase zu haengen (Bug: 5:50 landete in
                # der 5:49-Blase). Live-Gedanken Gehören als getrennte Blase.
                yield _sse({"art": "gedanke", "text": meldung})
                letzte_aktivitaet = time.time()

        if status in ("fertig", "fehler"):
            ergebnis = ((aktuell or {}).get("ergebnis") or "").strip()
            kopf = "✅ **Ergebnis:**" if status == "fertig" else "❌ **Fehler:**"
            if ergebnis:
                yield _sse({"delta": f"\n\n{kopf}\n" + ergebnis})
            # Dieses done-Ereignis kam aus der durchgehenden Strecke; das
            # Frontend traegt darunter keine zusaetzlichen Auftrags-Details
            # mehr als 3s-Poller nach (sondern nur, wenn der Stream versagt).
            yield _sse({
                "done": True,
                "auftrag_strecke": True,
                "conversation_id": conversation_id,
                "memories_used": 0, "memories_created": 0,
                "memory_count": memory_service.get_memory_count(),
                "archiv_used": 0, "sources": [],
            })
            return

        # Keepalive gegen Browser-/Proxy-Timeouts, wenn länger kein Meldung
        # kommt (Hermes denkt gerade, ohne Statusbox). Wird vom Client ignoriert.
        if time.time() - letzte_aktivitaet >= 15:
            yield ": keepalive\n\n"
            letzte_aktivitaet = time.time()

        time.sleep(1)


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Process a chat message and return the LLM response."""
    try:
        # Weiche: Coding-/Werkzeug-Auftraege ans Auftragsbuch statt an den
        # lokalen LLM. Damit landet "erstelle das und das" bei Hermes, der
        # sich den Auftrag im eigenen Takt abholt.
        #
        # Track A: Ist der PC-Hermes (im selben WLAN) erreichbar, wird die
        # Anfrage direkt dorthin geschickt und die Antwort zurueckgegeben.
        # Track C: Ist kein PC-Hermes erreichbar, probiert der LOKALE Hermes
        # (Termux-CLI auf diesem Geraet) den Auftrag direkt zu bearbeiten.
        # Fallback: Erst wenn weder PC noch lokaler Hermes liefern, geht der
        # Auftrag ins Auftragsbuch (Track B).
        ist_auftrag_val, begruendung, kategorie, komplexitaet = ist_auftrag(request.message)
        if ist_auftrag_val:
            # 1) PC-Hermes (Track A) — wenn erreichbar, bleibt er zuerst.
            hermes_antwort = hermes_gateway.sende_auftrag(request.message)
            if hermes_antwort is not None:
                conversation_id = _get_or_create_conversation(request.conversation_id)
                _finish_exchange(conversation_id, request.message, hermes_antwort)
                return ChatResponse(
                    reply=hermes_antwort,
                    conversation_id=conversation_id,
                    memories_used=0,
                    memories_created=0,
                    sources=[],
                    archiv_used=0,
                )

            # 2) Lokaler Hermes auf diesem Geraet (Track C) — va. unterwegs.
            # Ist der CLI installiert, startet er die Aufgabe im Hintergrund
            # und gibt seine Gedanken + das Ergebnis live ins Auftragsbuch.
            if hermes_local_ist_verfuegbar():
                # Gespraech ERST anlegen/ermitteln, damit die Verknuepfung
                # vor dem Thread-Start an den Worker geht und das Gespraech
                # im conversations-Dict bereits existiert, wenn die ersten
                # Hermes-Zwischenmeldungen eintreffen.
                conversation_id = _get_or_create_conversation(request.conversation_id)
                eintrag = _starte_lokale_hermes(
                    request.message,
                    hinweis=f"Automatische Erkennung: {begruendung}",
                    kategorie=kategorie,
                    komplexitaet=komplexitaet,
                    chat_verknuepfung=conversation_id,
                )
                reply_text = (
                    "🧩 **Coding-Auftrag erkannt – lokaler Hermes übernimmt.**\n\n"
                    f"📋 **Aufgabe:** {request.message[:150]}…\n\n"
                    "Gedanken & Zwischenschritte erscheinen hier live, das "
                    "Endergebnis danach.\n"
                )
                _finish_exchange(conversation_id, request.message, reply_text)
                return ChatResponse(
                    reply=reply_text,
                    conversation_id=conversation_id,
                    memories_used=0,
                    memories_created=0,
                    sources=[],
                    archiv_used=0,
                )

            # 3) Auftragsbuch (Track B) — nur wenn kein Hermes (PC noch lokal)
            # erreichbar ist, liegt der Auftrag dort zur Abholung bereit.
            eintrag = auftrag_service.anlegen(
                request.message,
                hinweis=f"Automatische Erkennung: {begruendung}",
                kategorie=kategorie,
                komplexitaet=komplexitaet,
            )
            # Sofort eine "Warte auf Hermes"-Meldung einfügen,
            # damit das Frontend-Tracking sofort eine Meldung sieht
            auftrag_service.statusmeldung_hinzufuegen(
                eintrag["id"],
                "⏳ **Hermes wurde benachrichtigt** – wartet auf Bearbeitung..."
            )
            reply_text = (
                "🧩 **Coding-Auftrag erkannt – wird bearbeitet.**\n\n"
                f"📋 **Aufgabe:** {request.message[:150]}…\n\n"
                "Hermes nimmt sich der Aufgabe an. Sobald ein Ergebnis vorliegt, "
                "erscheint es live hier.\n"
            )
            conversation_id = _get_or_create_conversation(request.conversation_id)
            _finish_exchange(conversation_id, request.message, reply_text)
            # Auftrag an das Gespraech binden, damit Hermes-Live-Meldungen
            # (Zwischenschritte, Ergebnis) den persistenten Verlauf füllen.
            auftrag_service.setze_chat_verknuepfung(eintrag["id"], conversation_id)
            return ChatResponse(
                reply=reply_text,
                conversation_id=conversation_id,
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

        # 2. Get LLM response with memory context
        reply, quellen = llm_service.chat(
            user_message=request.message,
            conversation_history=history,
            memories=memories,
            web_search=request.web_search,
            model=request.model,
            no_retention=request.no_retention,
            archiv=archiv,
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


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """Wie /chat, liefert die Antwort aber Stück für Stück (Server-Sent Events)."""
    # Gleiche Weiche wie in /chat: Coding-Auftraege ans Auftragsbuch statt
    # an den lokalen LLM. Als ein einzelnes SSE-Event ausgeliefert.
    ist_auftrag_val, begruendung, kategorie, komplexitaet = ist_auftrag(request.message)
    if ist_auftrag_val:
        # Wie /chat: erst PC-Hermes (Track A), dann lokalen Hermes
        # (Track C). Nur wenn beides nicht verfuegbar ist, geht der
        # Auftrag ins Buch (Track B).
        hermes_antwort = hermes_gateway.sende_auftrag(request.message)
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
                request.message,
                hinweis=f"Automatische Erkennung: {begruendung}",
                kategorie=kategorie,
                komplexitaet=komplexitaet,
                chat_verknuepfung=conversation_id,
            )
            reply_text = (
                "🧩 **Coding-Auftrag erkannt – lokaler Hermes übernimmt.**\n\n"
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
            request.message,
            hinweis=f"Automatische Erkennung: {begruendung}",
            kategorie=kategorie,
            komplexitaet=komplexitaet,
        )
        reply_text = (
            "🧩 **Coding-Auftrag erkannt – wird bearbeitet.**\n\n"
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