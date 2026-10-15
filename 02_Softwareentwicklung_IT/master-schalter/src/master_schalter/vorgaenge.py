"""Vorgänge der Automatik (`vorgaenge.json` im Datenordner).

Ein Vorgang ist genau ein Übergabeversuch an ein Thema. Seine Kennung ist
`<thema>@<Rücksetzzeit des auslösenden Fensters>` – damit entsteht **je Paar und Limitfenster**
höchstens ein Vorgang, und ein bereits vorhandener Vorgang (egal in welcher Phase) wird nie
erneut gesendet. Gespeichert werden Thema und Lauf-Kennung mit, damit ein abgebrochener Lauf
seine eigene Reservierung wiederfindet und nie eine fremde überschreibt.

Phasen:
* `sende`     – dauerhaft vermerkt, **bevor** etwas gesendet wird (Absturz hier = unklar, kein zweiter Versand)
* `gesendet`  – Transport gestartet und erfolgreich beendet
* `fehler`    – Transport nachweislich **nicht gestartet** (kein Kindprozess) oder Paketfehler
* `unklar`    – Transport gestartet, Ergebnis (Rückgabewert/Zeitüberschreitung/Abbruch) unklar
* `bestaetigt`– Codex hat die Übernahme mit `ACK <id>` bestätigt
* `entwertet` – durch Rückwechsel ungültig gemacht (verspäteter Auftrag/ACK)

Alle Schreibvorgänge laufen unter der **globalen** Zustandssperre (`zustand.sperre`) – kurz,
niemals während der 30-Sekunden-Wartezeit der Automatik.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from . import zustand
from .signale import _atomar_schreiben, daten_ordner

PHASEN = ("sende", "gesendet", "fehler", "unklar", "bestaetigt", "entwertet")
OFFEN = ("sende", "gesendet", "unklar")   # Phasen, in denen noch ein Auftrag unterwegs sein kann


@dataclass(frozen=True)
class Vorgang:
    id: str
    thema: str
    lauf_id: str
    phase: str
    zeit: str                 # ISO-Zeit der letzten Änderung
    fehler: str | None = None


def datei() -> Path:
    return daten_ordner() / "vorgaenge.json"


def _vorgang(roh: object) -> Vorgang | None:
    if not isinstance(roh, dict):
        return None
    ident, thema = roh.get("id"), roh.get("thema")
    lauf_id, phase, zeit = roh.get("lauf_id"), roh.get("phase"), roh.get("zeit")
    if not isinstance(ident, str) or not ident:
        return None
    if not isinstance(thema, str) or not thema:
        return None
    if not isinstance(lauf_id, str) or not lauf_id:
        return None
    if not isinstance(phase, str) or phase not in PHASEN:
        return None
    if not isinstance(zeit, str) or not zeit:
        return None
    fehler = roh.get("fehler")
    return Vorgang(ident, thema, lauf_id, phase, zeit, fehler if isinstance(fehler, str) else None)


def lesen(datei_pfad: Path | None = None) -> list[Vorgang]:
    try:
        roh = json.loads((datei_pfad or datei()).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(roh, list):
        return []
    vorgaenge = [v for v in (_vorgang(e) for e in roh) if v is not None]
    return sorted(vorgaenge, key=lambda v: v.id)


def aendern(funktion: Callable[[list[Vorgang]], list[Vorgang]], frist: float = zustand.FRIST_SEKUNDEN,
            datei_pfad: Path | None = None) -> list[Vorgang]:
    """Vorgangsliste lesen, `funktion` darauf anwenden, atomar zurückschreiben – unter der globalen Sperre."""
    with zustand.sperre(frist):
        alt = lesen(datei_pfad)
        neu = funktion(alt)
        pfad = datei_pfad or datei()
        if neu != alt or not pfad.exists():
            _atomar_schreiben(pfad, json.dumps([asdict(v) for v in neu], ensure_ascii=False, indent=2))
        return neu


def finden(vorgangs_id: str, datei_pfad: Path | None = None) -> Vorgang | None:
    return next((v for v in lesen(datei_pfad) if v.id == vorgangs_id), None)


def offene(datei_pfad: Path | None = None) -> list[Vorgang]:
    """Vorgänge, bei denen noch ein Auftrag unterwegs sein könnte (für den Rückwechsel)."""
    return [v for v in lesen(datei_pfad) if v.phase in OFFEN]
