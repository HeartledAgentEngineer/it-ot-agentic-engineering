"""Statusregister der Chats (K2): `arbeitet` oder `ruht`, geschrieben von den Hooks der Chats.

Layout: `<datenordner>/status/<werkzeug>-<kennung>.json` mit
`{"zustand": "arbeitet"|"ruht", "zeit": <ISO-Zeit UTC>, "ereignis": <Hook-Ereignis>}`.
Werkzeug und Kennung folgen dem Muster der Sitzungskennungen (`modi.VORGANG_ID_MUSTER`, G6); der Dateiname
entsteht nur aus diesen geprüften Teilen. Die Datei wird atomar ersetzt (tmp + `os.replace`).

Drosselung: `arbeitet` wird bei jedem `PostToolUse` gemeldet. Geschrieben wird es nur, wenn der Zustand
vorher ein anderer war, die Datei fehlt oder nicht lesbar ist oder die gespeicherte Zeit mindestens
`DROSSEL_SEKUNDEN` (60 s) zurückliegt – so entsteht keine Schreiblast bei vielen Werkzeugaufrufen.
`ruht` wird immer geschrieben.

`lesen` liefert `(zustand, zeit)` oder `None`; `None` heißt **unbekannt** (Datei fehlt, ist zu groß, kaputt
oder ungültig). Der spätere Ruhenachweis (G8b) darf `None` nie als „ruht“ deuten.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from . import modi
from .signale import _atomar_schreiben, daten_ordner

ARBEITET, RUHT = "arbeitet", "ruht"
ZUSTAENDE = (ARBEITET, RUHT)
WERKZEUGE = ("claude", "hermes", "codex")
DROSSEL_SEKUNDEN = 60.0
MAX_BYTES = 1024


class StatusFehler(Exception):
    """Werkzeug, Kennung oder Zustand ist nicht zulässig."""


def ordner() -> Path:
    return daten_ordner() / "status"


def datei(werkzeug: str, kennung: str) -> Path:
    """Statusdatei einer Sitzung; Werkzeug und Kennung werden geprüft (Name = nur geprüfte Teile)."""
    if not isinstance(werkzeug, str) or werkzeug not in WERKZEUGE:
        raise StatusFehler("Werkzeug unzulässig")
    if not isinstance(kennung, str) or modi.VORGANG_ID_MUSTER.fullmatch(kennung) is None:
        raise StatusFehler(f"Sitzungskennung unzulässig (erlaubt: {modi.VORGANG_ID_MUSTER.pattern})")
    return ordner() / f"{werkzeug}-{kennung}.json"


def _zeit_lesen(wert: object) -> datetime | None:
    if not isinstance(wert, str):
        return None
    try:
        zeit = datetime.fromisoformat(wert)
    except ValueError:
        return None
    return zeit if zeit.tzinfo else zeit.replace(tzinfo=timezone.utc)


def _roh_lesen(pfad: Path) -> tuple[str, datetime] | None:
    try:
        if pfad.stat().st_size > MAX_BYTES:
            return None
        roh = json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(roh, dict) or roh.get("zustand") not in ZUSTAENDE:
        return None
    zeit = _zeit_lesen(roh.get("zeit"))
    return (roh["zustand"], zeit) if zeit is not None else None


def lesen(werkzeug: str, kennung: str) -> tuple[str, datetime] | None:
    """`(zustand, zeit)` der Sitzung; `None` = unbekannt (fehlt, kaputt, ungültig oder unzulässige Kennung)."""
    try:
        return _roh_lesen(datei(werkzeug, kennung))
    except StatusFehler:
        return None


def schreiben(werkzeug: str, kennung: str, stand: str, ereignis: str,
              jetzt: datetime | None = None) -> bool:
    """Zustand melden; `True`, wenn geschrieben wurde, `False`, wenn die Drosselung es übersprang.

    `ereignis` ist der Name des Hook-Ereignisses (nur Buchstaben, höchstens 40 Zeichen). Unzulässige Eingaben
    ergeben `StatusFehler`; Schreibfehler (`OSError`) gibt die Funktion weiter – der Aufrufer (Hook) schluckt sie.
    """
    if stand not in ZUSTAENDE:
        raise StatusFehler(f"Zustand unzulässig (erlaubt: {', '.join(ZUSTAENDE)})")
    if not isinstance(ereignis, str) or not ereignis.isascii() or not ereignis.isalpha() or len(ereignis) > 40:
        raise StatusFehler("Ereignisname unzulässig")
    pfad = datei(werkzeug, kennung)
    jetzt = jetzt or datetime.now(timezone.utc)
    if stand == ARBEITET:
        alt = _roh_lesen(pfad)
        if alt is not None and alt[0] == ARBEITET and 0 <= (jetzt - alt[1]).total_seconds() < DROSSEL_SEKUNDEN:
            return False
    _atomar_schreiben(pfad, json.dumps({"zustand": stand, "zeit": jetzt.isoformat(), "ereignis": ereignis},
                                       ensure_ascii=False))
    return True
