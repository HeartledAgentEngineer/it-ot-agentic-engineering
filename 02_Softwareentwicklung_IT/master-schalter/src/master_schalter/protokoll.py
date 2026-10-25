"""Entscheidungsprotokoll des Wechselassistenten (G10): `protokoll.jsonl` im Datenordner.

Je Entscheidung eine JSON-Zeile `{zeit, vorgang, thema, entscheidung, grund}`. Es stehen **nur** feste
Begriffe darin – keine Chat-Kennungen, keine Titel, keine Nachrichteninhalte. Schreibfehler werden
geschluckt: das Protokoll darf den Ablauf eines Wechsels nie aufhalten. `lesen` liefert die letzten
Einträge für das spätere Fenster.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .signale import daten_ordner

MAX_GRUND = 200
STANDARD_LIMIT = 50


def datei() -> Path:
    return daten_ordner() / "protokoll.jsonl"


def schreiben(vorgang_id: str, thema: str, entscheidung: str, grund: str = "") -> None:
    """Eine Zeile anhängen; jeder Fehler (Pfad, Platte, Sperre) wird verschluckt."""
    try:
        zeile = json.dumps({"zeit": datetime.now(timezone.utc).isoformat(), "vorgang": vorgang_id,
                            "thema": thema, "entscheidung": entscheidung,
                            "grund": str(grund)[:MAX_GRUND]}, ensure_ascii=False)
        pfad = datei()
        pfad.parent.mkdir(parents=True, exist_ok=True)
        with open(pfad, "a", encoding="utf-8") as f:
            f.write(zeile + "\n")
    except Exception:  # noqa: BLE001 - das Protokoll darf den Wechsel nie stören
        pass


def lesen(limit: int = STANDARD_LIMIT) -> list[dict]:
    """Die letzten `limit` Einträge (älteste zuerst); fehlende Datei oder kaputte Zeilen werden übersprungen."""
    try:
        zeilen = datei().read_text(encoding="utf-8").splitlines()
    except (OSError, ValueError):
        return []
    eintraege: list[dict] = []
    for zeile in zeilen:
        try:
            roh = json.loads(zeile)
        except ValueError:
            continue
        if isinstance(roh, dict):
            eintraege.append(roh)
    return eintraege[-limit:] if limit > 0 else []
