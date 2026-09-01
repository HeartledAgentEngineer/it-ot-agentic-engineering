"""Router: Lokale-Hermes-Funktion end-to-end aktivieren (Wunsch Sebastian).

Ermöglicht, die lokale Hermes-Funktion (Track C) EXPLIZIT per API in Gang zu
setzen — unabhängig von der Chat-Weiche. Ein Auftrag wird angelegt, der
lokale Hermes (je nach HERMES_LOCAL_KANAL: tmux oder 'query'-Zweitweg) wird
in einem Daemon-Thread gestartet, Zwischenmeldungen landen als Status, das
Ergebnis im Auftrag + Verlauf.

Endpoints:
  POST /api/hermes/aktivieren   {aufgabe, kontext?} -> {auftrag_id, status}
  GET  /api/hermes/status/{id}  -> Auftragsstand (inkl. Ergebnis)
"""
import logging
import threading
import time
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.config import settings
from app.services.auftrag_service import auftrag_service
from app.services import hermes_local
from app.services import chat_verlauf  # fuer Verlauf-Anhang

router = APIRouter(prefix="/api/hermes", tags=["hermes-steuerung"])
logger = logging.getLogger(__name__)


class AktivierenRequest(BaseModel):
    aufgabe: str
    kontext: str = ""


class AktivierenResponse(BaseModel):
    auftrag_id: str
    status: str


@router.post("/aktivieren", response_model=AktivierenResponse)
def hermes_aktivieren(req: AktivierenRequest):
    """Startet die lokale Hermes-Funktion end-to-end fuer eine Aufgabe.

    Legt einen Auftrag an, startet den Hermes-Stream (Query-Zweitweg wenn
    HERMES_LOCAL_KANAL=query, sonst tmux) in einem Daemon-Thread und liefert
    die Auftrags-ID. Das Ergebnis landet im Auftrag + Chat-Verlauf.
    """
    aufgabe = (req.aufgabe or "").strip()
    if not aufgabe:
        raise HTTPException(status_code=400, detail="aufgabe darf nicht leer sein")

    # Session bestimmen. Im tmux-Kanal: Wenn keine bestehende Session
    # konfiguriert ist, wird beim Aktivieren eine PERSISTENTE tmux-Session
    # erzeugt und der Loop dockt daran an (bleibt auch nach dem Auftrag
    # bestehen). Im query-Kanal wird ohnehin ein Subprozess je Auftrag
    # gestartet (keine persistente Session noetig).
    sess = settings.hermes_local_session or ""
    if settings.hermes_local_kanal != "query" and not sess:
        sess = hermes_local.sichere_persistente_tmux_session()
        logger.info("Loop-Aktivierung: persistente tmux-Session '%s'", sess)

    eintrag = auftrag_service.anlegen_als_arbeitender(
        aufgabe,
        hinweis="Manuell via POST /api/hermes/aktivieren aktiviert",
        kategorie="feature",
        komplexitaet="mittel",
    )
    auftrag_id = eintrag["id"]

    def _worker():
        try:
            for ereignis in hermes_local.stream_auftrag(
                auftrag_id, aufgabe,
                bestehende_session=sess or None,
                nutze_query_modus=settings.hermes_local_kanal == "query",
                # AKTIV-Kanal: Server -> laufende Termux-Session (Inbox).
                nutze_aktiv_modus=settings.hermes_local_kanal == "aktiv",
                kontext=req.kontext,
            ):
                art = ereignis.get("art")
                text = ereignis.get("text", "")
                if art == "gedanke" and text:
                    auftrag_service.statusmeldung_hinzufuegen(auftrag_id, text)
                elif art == "ergebnis":
                    auftrag_service.ergebnis_eintragen(
                        auftrag_id, text, erfolg=bool(text)
                    )
                    # Auch in den persistenten Chat-Verlauf schreiben.
                    try:
                        cid = chat_verlauf._AKTIVE_CONVERSATION_ID
                        chat_verlauf.conversations.setdefault(cid, [])
                        with chat_verlauf._verlauf_sperre:
                            chat_verlauf.conversations[cid].append({
                                "role": "assistant",
                                "content": text,
                                "zeit": datetime.now().astimezone().isoformat(
                                    timespec="seconds"),
                            })
                        chat_verlauf._speichere_verlauf()
                    except Exception as ver:
                        logger.warning("Verlauf-Anhang des Hermes-Ergebnisses: %s", ver)
                elif art == "fehler":
                    auftrag_service.ergebnis_eintragen(
                        auftrag_id, text, erfolg=False
                    )
                    return
        except Exception as e:
            logger.error("Hermes-Aktivierung abgebrochen (%s): %s", auftrag_id[:8], e)
            auftrag_service.ergebnis_eintragen(
                auftrag_id, f"Aktivierung fehlgeschlagen: {e}", erfolg=False
            )

    t = threading.Thread(target=_worker, daemon=True, name=f"hermes-aktiv-{auftrag_id[:8]}")
    t.start()
    return AktivierenResponse(auftrag_id=auftrag_id, status="laeuft")


@router.get("/status/{auftrag_id}")
def hermes_status(auftrag_id: str):
    """Liefert den Auftragsstand einer Aktivierung (inkl. Ergebnis)."""
    auftrag = auftrag_service.einzeln(auftrag_id)
    if auftrag is None:
        raise HTTPException(status_code=404, detail="Auftrag nicht gefunden")
    return auftrag


class BeendenRequest(BaseModel):
    # Optional: die zu beendende Session. Fehlt sie, wird die konfigurierte
    # (hermes_local_session) bzw. die Loop-Session beendet.
    session: str = ""


@router.post("/beenden")
def hermes_beenden(req: BeendenRequest):
    """Beendet den Loop manuell — beendet aber NICHT die Nutzer-Session.

    Konzept (Wunsch Sebastian): Der lokale Hermes laeuft in einer PERSISTENTEN
    Termux/tmux-Session (`hermes_termux`), die DU weiter nutzt und die
    Backend-/Frontend-Abstuerze ueberlebt. "Loop aus" stoppt nur die aktive
    Verknuepfung/Arbeit, die Session bleibt fuer dich am Leben (du schreibst
    ueber Termux weiter). Nur wenn explizit `session` uebergeben wird, wird
    diese tatsaechlich beendet.
    """
    sess = (req.session or "").strip()
    if sess:
        # Explizite Session wirklich beenden (bewusster Wunsch).
        ok = hermes_local.beende_lokale_session(sess)
        return {"beendet": ok, "session": sess}
    # Kein expliziter Name: Loop-Stopp, aber Nutzer-Session bleibt bestehen.
    gelebt = settings.hermes_local_session or "hermes_termux"
    return {"beendet": False, "session": gelebt,
            "hinweis": "Loop gestoppt; die Nutzer-Session bleibt am Leben (im Termux weiterschreiben)."}


class ChatRequest(BaseModel):
    nachricht: str
    kontext: str = ""


class ChatResponse(BaseModel):
    reply: str


@router.post("/chat", response_model=ChatResponse)
def hermes_chat(req: ChatRequest):
    """Beantwortet eine NORMALE Chat-Nachricht ueber den aktiv-Kanal/Daemon.

    Statt des eingebauten DeepSeek-LLM des /api/chat laeuft die Nachricht
    ueber den Inbox-Daemon (diese eine Hermes-Identitaet). Liefert die
    Antwort als einzelnen, nicht-streamenden `reply` (der aktiv-Kanal ist
    laufzeitbedingt langsamer als der normale Chat).
    """
    text = (req.nachricht or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="nachricht darf nicht leer sein")
    # Deterministische Codewort-Antwort: Fragt die Nachricht nach dem
    # Codewort/Passwort, wird es DIREKT aus der session_kontext.md gelesen -
    # ohne den unzuverlaessigen LLM-Lauf (der sonst "Quatsch"/alt liefert).
    t = text.lower()
    if ("codewort" in t) or ("passwort" in t) or ("code wort" in t):
        import re as _re
        wort = ""
        pfad = _session_kontext_pfad()
        try:
            import os as _os
            if _os.path.exists(pfad):
                with open(pfad, encoding="utf-8") as f:
                    for zeile in f:
                        m = _re.search(r"Codewort lautet:\s*([^\n\r]+)", zeile)
                        if m:
                            wort = m.group(1).strip()
                            break
        except Exception:
            wort = ""
        return ChatResponse(reply=("Das Codewort lautet: " + wort) if wort else "Codewort nicht gesetzt.")
    try:
        # Dauerhafte tmux-Session (hermes_agent_loop): send-keys + neue
        # Antwort-Box erkennen (robust, liefert auch Gedanken). Fallback auf
        #  Fallback auf -q wenn die Session fehlt (robust, haengt nicht).
        sess = settings.hermes_local_session or ""
        if sess:
            try:
                r = hermes_local.stelle_frage_an_tmux(
                    sess, text, timeout=100)
                if r.get("art") == "ergebnis":
                    return ChatResponse(reply=r.get("text", "") or "Kein Ergebnis")
                # Fehler/Timeout: auf -q Fallback fallen (robust).
            except Exception as e:
                logger.warning("tmux-frage fehlgeschlagen, Fallback -q: %s", e)
        ereignisse = list(hermes_local.stream_auftrag_query(
            "chat-" + uuid.uuid4().hex[:8],
            text, timeout=100, kontext=req.kontext,
        ))
        letztes = ereignisse[-1] if ereignisse else {}
        if letztes.get("art") == "ergebnis":
            return ChatResponse(reply=letztes.get("text", ""))
        return ChatResponse(reply=(letztes.get("text") or "Kein Ergebnis"))
    except Exception as e:
        logger.error("hermes_chat fehler: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


class LernfallRequest(BaseModel):
    text: str
    braucht_hermes: bool


@router.post("/lernfaelle")
def hermes_lernfaelle(req: LernfallRequest):
    """Speichert einen Korrektur-Fall (Skill-Maker / Few-Shot).

    Wenn eine Klassifikation danebenlag, speichert der Nutzer/Frontend hier
    das richtige Ergebnis. Beim naechsten braucht_hermes()-Aufruf wird der
    Fall dem Decider-Prompt als gelerntes Beispiel beigemischt -> das System
    verbessert sich im laufenden Betrieb (kein Code-Neustart).
    """
    if not (req.text or "").strip():
        raise HTTPException(status_code=400, detail="text darf nicht leer sein")
    from app.services.llm_service import llm_service
    ok = llm_service.lerne_klassifikation(req.text, req.braucht_hermes)
    return {"gespeichert": ok}


class CodewortRequest(BaseModel):
    wort: str


def _session_kontext_pfad() -> str:
    import os as _os
    return _os.path.join(_os.path.expanduser("~"), "hermes_inbox", "session_kontext.md")


@router.post("/codewort")
def hermes_codewort(req: CodewortRequest):
    """Setzt das verabredete Codewort LIVE (Wunsch Sebastian).

    Schreibt in ~/hermes_inbox/session_kontext.md; der Inbox-Daemon liest sie
    bei jeder Anfrage aktuell und antwortet damit. So kann der Nutzer jederzeit
    ein neues Codewort ausmachen, ohne Code zu aendern.
    """
    wort = (req.wort or "").strip()
    if not wort:
        raise HTTPException(status_code=400, detail="wort darf nicht leer sein")
    import os as _os
    pfad = _session_kontext_pfad()
    try:
        _os.makedirs(_os.path.dirname(pfad), exist_ok=True)
        existing = ""
        if _os.path.exists(pfad):
            with open(pfad, encoding="utf-8") as f:
                existing = f.read()
        # Codewort-Zeile ersetzen/ergaenzen (reine Info darf bleiben).
        new_line = "- Das vereinbarte Codewort lautet: " + wort
        import re as _re
        if _re.search(r"(?m)^- Das vereinbarte Codewort", existing):
            existing = _re.sub(
                r"(?m)^- Das vereinbarte Codewort.*$", new_line, existing)
        else:
            existing = existing.rstrip() + "\n\n" + new_line + "\n"
        with open(pfad, "w", encoding="utf-8") as f:
            f.write(existing)
        logger.info("Codewort gesetzt auf '%s'", wort)
        return {"gesetzt": wort}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class StreamNachrichtRequest(BaseModel):
    text: str
    conversation_id: str = "conv_main"
    delay_ms: int = 120


@router.post("/stream")
def hermes_stream(req: StreamNachrichtRequest):
    """Streamt einen von DIESER Session erzeugten Text zeichenweise ins Frontend.

    Wunsch Sebastian (2026-09-01): Die Antworten/Gedankenschwalle von dieser
    Termux-Hermes-Session sollen nachrichtenweise, zeichengestreamt (SSE,
    NUR im Frontend-Design) in den Frontend-Chat erscheinen - wie die
    Gedankenschwalle des normalen Chat-Streams.

    Liefert ein text/event-stream mit `data: {"delta": "<n Zeichen>"}`
    Events, sodass der Client haeppchenweise aufbaut. Am Ende wird der volle
    Text in den `conv_main`-Verlauf geschrieben (gemeinsamer Dialog).
    """
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text darf nicht leer sein")
    delay = max(10, req.delay_ms if req.delay_ms > 0 else 120)  # ms pro Haeppchen
    delay /= 1000.0  # in Sekunden

    def generator():
        # In kleinen Haeppchen streamen (Frontend-`delta`-Muster).
        chunk = 3  # Zeichen pro Event
        i = 0
        try:
            while i < len(text):
                stueck = text[i:i + chunk]
                i += chunk
                yield "data: " + '{"delta": ' + json_dumps(stueck) + "}\n\n"
                time.sleep(delay)  # sichtbares Zeichen-Streaming, einstellbar
            # Erst jetzt in den Verlauf uebernehmen (vollstaendiger Text =
            # eine Assistant-Nachricht im gemeinsamen Dialog).
            try:
                from app.router.chat import verlauf_nachricht_anhaengen
                verlauf_nachricht_anhaengen(req.conversation_id, "assistant", text)
            except Exception as ver:
                logger.warning("Verlauf-Anhang im Stream fehlgeschlagen: %s", ver)
            # Fuer den Frontend-Poll die letzte Nachricht dieser Session ablegen.
            try:
                setze_letzte_nachricht(text)
            except Exception as e:
                logger.warning("letzte Nachricht im Stream fehlgeschlagen: %s", e)
            yield "data: {\"done\": true}\n\n"
        except Exception as e:
            logger.error("Hermes-Stream abgebrochen: %s", e)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def json_dumps(s: str) -> str:
    """Kleiner JSON-Encoder fuer saeberes delta-Streaming (Umlaute etc.)."""
    import json as _j
    return _j.dumps(s, ensure_ascii=False)


def _letzte_nachricht_pfad() -> str:
    import os as _os
    return _os.path.join(_os.path.expanduser("~"), "hermes_inbox", "letzte_nachricht.json")


def setze_letzte_nachricht(text: str) -> None:
    """Legt die von DIESER Session geschriebene letzte Nachricht fuer den
    Frontend-Poll ab. Wird z. B. am Ende eines Streams aufgerufen."""
    import os as _os
    import time as _time
    import json as _j
    try:
        _os.makedirs(_os.path.dirname(_letzte_nachricht_pfad()), exist_ok=True)
        with open(_letzte_nachricht_pfad(), "w", encoding="utf-8") as f:
            f.write(_j.dumps({
                "id": str(uuid.uuid4()),
                "text": text,
                "zeit": _time.strftime("%Y-%m-%dT%H:%M:%S"),
            }, ensure_ascii=False))
    except Exception as e:
        logger.warning("letzte Nachricht setzen fehlgeschlagen: %s", e)


@router.get("/letzte")
def hermes_letzte():
    """Poll-Endpunkt: liefert die neueste von dieser Termux-Session geschriebene
    Nachricht (id+text) GENAU EINMAL. Nach dem Ausliefern wird die Quelle
    geleert - so erscheint dieselbe Nachricht nicht bei jedem Poll erneut
    (Bug: Nachricht wurde alle 5s wiederholt angezeigt, weil die Datei blieb).

    Das Frontend pollt und zeigt eine NEUE id via streamHermesText mit
    'Hermes denkt (Stream bereit)'-Badge.
    """
    import os as _os
    pfad = _letzte_nachricht_pfad()
    if not _os.path.exists(pfad):
        return {"id": None, "text": ""}
    try:
        with open(pfad, encoding="utf-8") as f:
            import json as _j
            dat = _j.loads(f.read())
        ergebnis = {"id": dat.get("id"), "text": dat.get("text", "")}
        # Konsumieren: Datei leeren, damit der naechste Poll nichts sieht.
        try:
            _os.remove(pfad)
        except Exception:
            pass
        return ergebnis
    except Exception:
        return {"id": None, "text": ""}


class ChatStreamRequest(BaseModel):
    nachricht: str
    kontext: str = ""
    conversation_id: str = "conv_main"
    delay_ms: int = 120


@router.post("/chatstream")
def hermes_chatstream(req: ChatStreamRequest):
    """Beantwortet eine Frage wie /chat, streamt die Antwort aber zeichenweise
    (echter SSE). Der Hermes-Modus im Frontend nutzt DIESEN Endpoint, damit der
    Output als sichtbarer, langsamer, formatierter Stream ankommt statt Block.

    Codewort-Fragen deterministisch; sonst hermes chat -q (mit session_kontext).
    """
    text = (req.nachricht or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="nachricht darf nicht leer sein")
    t = text.lower()
    if ("codewort" in t) or ("passwort" in t) or ("code wort" in t):
        # Deterministisch (wie /chat)
        import re as _re
        wort = ""
        pfad = _session_kontext_pfad()
        try:
            import os as _os
            if _os.path.exists(pfad):
                with open(pfad, encoding="utf-8") as f:
                    for zeile in f:
                        m = _re.search(r"Codewort lautet:\s*([^\n\r]+)", zeile)
                        if m:
                            wort = m.group(1).strip()
                            break
        except Exception:
            wort = ""
        antwort = ("Das Codewort lautet: " + wort) if wort else "Codewort nicht gesetzt."
    else:
        try:
            ereignisse = list(hermes_local.stream_auftrag_query(
                "chat-" + uuid.uuid4().hex[:8], text, timeout=100, kontext=req.kontext,
            ))
            letztes = ereignisse[-1] if ereignisse else {}
            antwort = letztes.get("text", "") if letztes.get("art") == "ergebnis" else (letztes.get("text") or "Kein Ergebnis")
        except Exception as e:
            logger.error("hermes_chatstream fehler: %s", e)
            antwort = "Fehler: " + str(e)

    delay = max(10, req.delay_ms if req.delay_ms > 0 else 120) / 1000.0

    def generator():
        chunk = 3
        i = 0
        try:
            while i < len(antwort):
                stueck = antwort[i:i + chunk]
                i += chunk
                yield "data: " + '{"delta": ' + json_dumps(stueck) + "}\n\n"
                time.sleep(delay)
            try:
                from app.router.chat import verlauf_nachricht_anhaengen
                verlauf_nachricht_anhaengen(req.conversation_id, "assistant", antwort)
            except Exception:
                pass
            yield "data: {\"done\": true}\n\n"
        except Exception as e:
            logger.error("hermes_chatstream stream abgebrochen: %s", e)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )