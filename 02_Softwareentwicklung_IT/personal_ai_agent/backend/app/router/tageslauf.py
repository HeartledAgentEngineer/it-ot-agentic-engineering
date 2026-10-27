"""Tagesimport im Checks-Fenster (C3, 26.10.2026): Stand lesen und Einstellungen setzen.

* ``GET  /api/tageslauf``               Schalter, Kamera-Ordner, letzter Bericht, Gemini-Erinnerung.
* ``POST /api/tageslauf/einstellungen`` ``{an?: bool, kamera_ordner?: str, gemini_export_heute?: true}``.

Beide Routen hängen in ``main.py`` am API-Key. Die Fachlogik steht in
``app/services/tageslauf_status.py``. Nichts wird gelöscht; geschrieben wird nur die
Schalterdatei ``tageslauf.json`` (Lesen-Ändern-Schreiben, atomar).
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request

from app.services import tageslauf_status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tageslauf", tags=["tageslauf"])


@router.get("")
def tageslauf_stand() -> Dict[str, Any]:
    """Der Stand des Tagesimports (nur lesend, nie ein 500)."""
    try:
        return tageslauf_status.status()
    except Exception as e:  # noqa: BLE001 – nie 500
        logger.warning("Tagesimport: Stand nicht lesbar: %s", type(e).__name__)
        return {"ok": False, "error": f"Tagesimport nicht lesbar ({type(e).__name__})"}


@router.post("/einstellungen")
async def tageslauf_einstellungen(request: Request) -> Dict[str, Any]:
    """Setzt Schalter, Kamera-Ordner oder den heutigen Gemini-Export; liefert den neuen Stand."""
    try:
        koerper = await request.json()
    except Exception:  # noqa: BLE001 – kein JSON
        raise HTTPException(status_code=400, detail="Nicht gespeichert: Die Anfrage ist kein JSON.")
    try:
        return tageslauf_status.einstellungen_aendern(koerper)
    except tageslauf_status.Ablehnung as a:
        raise HTTPException(status_code=a.status, detail=a.text)
