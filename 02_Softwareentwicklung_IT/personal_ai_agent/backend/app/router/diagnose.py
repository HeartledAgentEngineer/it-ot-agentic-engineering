"""Diagnose aus der Oberflaeche — Ueberlauf-Messwerte ablegen (01.10.2026).

Befund (Sebastian, mehrfach): Eine frisch gestreamte Antwort ragt am Handy rechts
ueber den Rand; nach einem App-Neustart ist dieselbe Nachricht richtig. Im
Browser-Pruefstand nicht nachstellbar (Recherche + Quellen + Tabelle + lange
Links: Blase 359/375 px). Der Ueberlauf-Waechter in ``frontend/app.js`` misst
deshalb AM HANDY und schickt nur Messwerte hierher:

  POST /api/diagnose/ueberlauf   {phase, fenster, skala, seite_scroll, blase_rechts,
                                  inhalt_scroll, inhalt_breite, taeter: [...]}

Abgelegt wird eine JSONL-Zeile im kabel-lesbaren Diagnose-Ordner
(``~/storage/downloads/hermes_diag/ueberlauf.jsonl``, sonst ``~/agent_diag``;
uebersteuerbar mit ``DIAG_ORDNER``) — dort liest der PC per ``adb``. Nur Zahlen
und Element-Kennzeichen (Tag, Klasse, white-space, display), NIE Textinhalt;
Zeichenketten werden auf harmlose Zeichen gekuerzt. Datei > 512 KB -> nur die
letzten 200 Zeilen bleiben (Diagnose, keine Nutzdaten).
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/diagnose", tags=["diagnose"])

DATEINAME = "ueberlauf.jsonl"
MAX_BYTES = 512 * 1024
BEHALTEN = 200


class Taeter(BaseModel):
    tag: str = Field(default="", max_length=20)
    klasse: str = Field(default="", max_length=120)
    rechts: float = 0
    breite: float = 0
    ws: str = Field(default="", max_length=20)
    display: str = Field(default="", max_length=20)


class Ueberlauf(BaseModel):
    phase: str = Field(default="", max_length=20)
    fenster: float = 0
    skala: float = 1
    seite_scroll: float = 0
    blase_rechts: float = 0
    inhalt_scroll: float = 0
    inhalt_breite: float = 0
    taeter: List[Taeter] = Field(default_factory=list, max_length=8)


def diag_ordner() -> str:
    ueber = os.environ.get("DIAG_ORDNER")
    if ueber and ueber.strip():
        return ueber.strip()
    geteilt = os.path.join(os.path.expanduser("~"), "storage", "downloads", "hermes_diag")
    if os.path.isdir(geteilt):
        return geteilt
    return os.path.join(os.path.expanduser("~"), "agent_diag")


def _harmlos(text: str, laenge: int) -> str:
    return re.sub(r"[^\w .:#\-]", "", text or "")[:laenge]


def zeile_bauen(m: Ueberlauf) -> Dict[str, Any]:
    return {
        "zeit": datetime.now().isoformat(timespec="seconds"),
        "phase": _harmlos(m.phase, 20),
        "fenster": round(m.fenster, 1), "skala": round(m.skala, 3),
        "seite_scroll": round(m.seite_scroll, 1), "blase_rechts": round(m.blase_rechts, 1),
        "inhalt_scroll": round(m.inhalt_scroll, 1), "inhalt_breite": round(m.inhalt_breite, 1),
        "taeter": [{"tag": _harmlos(t.tag, 20), "klasse": _harmlos(t.klasse, 120),
                    "rechts": round(t.rechts, 1), "breite": round(t.breite, 1),
                    "ws": _harmlos(t.ws, 20), "display": _harmlos(t.display, 20)}
                   for t in m.taeter[:8]],
    }


@router.post("/ueberlauf")
def ueberlauf(messung: Ueberlauf) -> Dict[str, Any]:
    try:
        ordner = diag_ordner()
        os.makedirs(ordner, exist_ok=True)
        pfad = os.path.join(ordner, DATEINAME)
        if os.path.isfile(pfad) and os.path.getsize(pfad) > MAX_BYTES:
            with open(pfad, encoding="utf-8", errors="replace") as datei:
                rest = datei.readlines()[-BEHALTEN:]
            with open(pfad, "w", encoding="utf-8") as datei:
                datei.writelines(rest)
        with open(pfad, "a", encoding="utf-8") as datei:
            datei.write(json.dumps(zeile_bauen(messung), ensure_ascii=False) + "\n")
        logger.warning("Ueberlauf gemeldet: phase=%s fenster=%s blase_rechts=%s",
                       messung.phase, messung.fenster, messung.blase_rechts)
        return {"ok": True}
    except OSError as fehler:
        logger.error("Ueberlauf-Meldung nicht gespeichert: %s", fehler)
        return {"ok": False, "fehler": fehler.__class__.__name__}
