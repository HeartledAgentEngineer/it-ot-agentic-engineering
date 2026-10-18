"""Sicheres Update und Backend-Neustart aus der Oberfläche.

Dazu das **Server-Protokoll** (To-do Punkt 16, 18.10.2026): der abgekoppelt
laufende Server schreibt seine Ausgaben in eine Datei, die die Oberfläche
liest. Beide Wege schützen sich gleich — vom Gerät selbst (Loopback) immer,
von fremden Geräten nur über HTTPS.
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request

from app.router import auth
from app.sicherheit import client_ist_loopback
from app.services import protokoll as server_protokoll

logger = logging.getLogger(__name__)

PROJEKT_ORDNER = Path(__file__).resolve().parents[3]
UPDATE_SKRIPT = PROJEKT_ORDNER / "termux" / "update-und-neustart.sh"
UPDATE_MELDUNG = "Stand wird geholt, Server startet neu — die Seite ist gleich wieder da."

router = APIRouter(prefix="/api/system", tags=["system"])


def _update_abgekoppelt_starten() -> None:
    """Termux-Skript in einer eigenen Sitzung starten; nie auf es warten."""
    try:
        prozess = subprocess.Popen(
            ["bash", str(UPDATE_SKRIPT)],
            cwd=str(PROJEKT_ORDNER),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
    except OSError:
        logger.exception("Update/Neustart konnte nicht gestartet werden.")
        return
    logger.info("Update/Neustart abgekoppelt gestartet (PID %s).", prozess.pid)


@router.post("/update", status_code=202)
async def update_starten(request: Request, background_tasks: BackgroundTasks):
    """Update-Skript nach der Antwort starten.

    **Das Gerät selbst (Loopback: 127.0.0.0/8, ::1) darf immer** — über HTTP
    oder HTTPS und unabhängig davon, ob ein ``API_KEY`` eingerichtet ist
    (Sebastian, 16.10.2026: der Knopf war am Handy sonst dauerhaft tot, weil
    seine App den lokalen Server über HTTP anspricht und er keine Anmeldung
    will). Für **fremde** Geräte (LAN, Tailscale) bleibt die Sperre: nur über
    HTTPS. Der Schutz nach außen ist das Netz plus die Verschlüsselung — nicht
    ein Schlüssel im lokalen Weg.
    """
    vom_geraet_selbst = client_ist_loopback(request.scope)
    if not vom_geraet_selbst and not auth._ist_https(request):
        raise HTTPException(status_code=403, detail="Update/Neustart ist von fremden Geräten nur über HTTPS möglich.")
    if not UPDATE_SKRIPT.is_file():
        logger.error("Update/Neustart-Skript fehlt: %s", UPDATE_SKRIPT)
        raise HTTPException(status_code=503, detail="Update-Skript fehlt; Server bleibt unverändert.")

    # Starlette führt BackgroundTasks erst aus, nachdem die HTTP-Antwort gesendet ist.
    # Der Prozess selbst wird zusätzlich mit start_new_session abgekoppelt.
    background_tasks.add_task(_update_abgekoppelt_starten)
    return {"ok": True, "message": UPDATE_MELDUNG}


@router.get("/protokoll")
async def protokoll_holen(
    request: Request,
    zeilen: int = Query(server_protokoll.STANDARD_ZEILEN, ge=1,
                        le=server_protokoll.MAX_ZEILEN,
                        description="Wie viele der letzten Protokollzeilen geliefert werden."),
):
    """Die letzten Zeilen des Server-Protokolls für die Oberfläche (nur lesend).

    Schutz wie beim Update: **das Gerät selbst (Loopback) darf immer** — die
    Bedienung findet am Handy statt, dort läuft der Server. Für **fremde**
    Geräte (LAN, Tailscale) bleibt die Sperre: nur über HTTPS.

    Geliefert werden ausschließlich Zahlen und die Protokollzeilen des Servers
    (Status, Zugriffe, Fehler). Die Datei ist dieselbe, die der Server selbst
    schreibt (``AGENT_SERVER_PROTOKOLL``, gesetzt vom Startweg). Ist sie nicht
    vorhanden oder nicht eingeschaltet, sagt die Antwort das ehrlich — es wird
    nichts erfunden und nichts angelegt.
    """
    vom_geraet_selbst = client_ist_loopback(request.scope)
    if not vom_geraet_selbst and not auth._ist_https(request):
        raise HTTPException(status_code=403,
                            detail="Das Server-Protokoll ist von fremden Geräten nur über HTTPS abrufbar.")

    stand = server_protokoll.protokoll_lesen(zeilen)
    return {"ok": True, **stand}
