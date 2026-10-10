"""Router: Was laeuft gerade? — die Statusleiste am oberen Rand (10.10.2026).

Sebastian: "muss jederzeit ersichtlich sein, welche Hintergrundprozesse
laufen" — gestern lief eine Bildanalyse 20 bis 30 Minuten, im Chat war nichts
davon zu sehen. ``GET /api/laeuft`` fasst die drei bekannten Quellen zusammen
(angemeldete Backend-Arbeiten, laufende Auftraege im Buch, Protokolldateien
in den kabel-lesbaren Ordnern) — Details in
``app/services/laufende_arbeiten.py``.

Rein lesend, fehlertolerant: fehlende Dateien/Ordner ergeben eine leere
Liste, nie einen Serverfehler. Die Oberflaeche pollt diesen Endpunkt fuer
die dauerhafte Leiste oben (Name, seit wann, antippbar fuer Einzelheiten).
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter

from app.services import laufende_arbeiten

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/laeuft")
def laeuft() -> Dict[str, Any]:
    """Laufende Hintergrundarbeiten mit Name, Startzeit, Zustand, letzter Zeile, Fortschritt."""
    daten = laufende_arbeiten.alles()
    daten["ok"] = True
    try:
        daten["zeit"] = datetime.now().astimezone().isoformat(timespec="seconds")
    except Exception:  # pragma: no cover - darf nie scheitern
        daten["zeit"] = ""
    return daten
