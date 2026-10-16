"""Sicheres Update und Backend-Neustart aus der Oberfläche."""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from app.config import settings
from app.router import auth

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
    """Nur angemeldet und über HTTPS: Update-Skript nach der Antwort starten."""
    if not auth._ist_https(request):
        raise HTTPException(status_code=403, detail="Update/Neustart ist nur über HTTPS möglich.")
    if not settings.api_key:
        raise HTTPException(
            status_code=503,
            detail="Update/Neustart ist gesperrt, solange API_KEY nicht eingerichtet ist.",
        )
    if not UPDATE_SKRIPT.is_file():
        logger.error("Update/Neustart-Skript fehlt: %s", UPDATE_SKRIPT)
        raise HTTPException(status_code=503, detail="Update-Skript fehlt; Server bleibt unverändert.")

    # Starlette führt BackgroundTasks erst aus, nachdem die HTTP-Antwort gesendet ist.
    # Der Prozess selbst wird zusätzlich mit start_new_session abgekoppelt.
    background_tasks.add_task(_update_abgekoppelt_starten)
    return {"ok": True, "message": UPDATE_MELDUNG}
