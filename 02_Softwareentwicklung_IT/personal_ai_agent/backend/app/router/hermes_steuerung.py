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
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
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