"""Bestätigung (ACK) eines Automatikauftrags im Rollout des Zielchats.

Ausgewertet werden **ausschließlich** die Rollout-Dateien des Zielchats
(`rollout-*-<codex_thread>.jsonl`, gesucht unter dem Ordner aus `signale.codex_ordner()`), und
dort nur Einträge **nach** dem Sendezeitpunkt sowie nur **Assistentenantworten**
(`response_item` mit `role == "assistant"` bzw. `event_msg` vom Typ `agent_message`). Deren Text
muss mit `ACK <id>` **beginnen**. Die eigene Nutzernachricht (der Prompt) zählt nie, auch wenn sie
die Kennung enthält. Andere Inhalte werden nicht ausgewertet oder gespeichert.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from . import signale

BESTAETIGUNG_NACH_MINUTEN = 15


def _text(inhalt: object) -> str:
    """Text einer Antwort aus `payload.content` (Zeichenkette oder Liste von Blöcken)."""
    if isinstance(inhalt, str):
        return inhalt
    if isinstance(inhalt, list):
        teile = []
        for block in inhalt:
            if isinstance(block, str):
                teile.append(block)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                teile.append(block["text"])
        return "\n".join(teile)
    return ""


def _antwort_text(obj: dict) -> str | None:
    """Assistentenantwort einer Rollout-Zeile oder None, wenn die Zeile keine ist."""
    nutzlast = obj.get("payload")
    if not isinstance(nutzlast, dict):
        return None
    art = obj.get("type") or nutzlast.get("type")
    if art == "response_item" and nutzlast.get("type") == "message" and nutzlast.get("role") == "assistant":
        return _text(nutzlast.get("content"))
    if art == "event_msg" and nutzlast.get("type") == "agent_message":
        return _text(nutzlast.get("message")) or _text(nutzlast.get("content"))
    return None


def _zeit(wert: object) -> datetime | None:
    return signale._iso(wert)


def rollout_dateien(thread: str, ordner: Path | None = None) -> list[Path]:
    """Nur die Rollout-Dateien des Zielchats (`**/rollout-*-<uuid>.jsonl`)."""
    ordner = ordner or signale.codex_ordner()
    if not ordner.is_dir():
        return []
    try:
        return sorted(ordner.rglob(f"rollout-*-{thread}.jsonl"))
    except OSError:
        return []


def pruefen(vorgangs_id: str, thread: str, seit: datetime, ordner: Path | None = None) -> bool:
    """True, wenn eine Assistentenantwort des Zielchats nach `seit` mit `ACK <id>` beginnt."""
    erwartet = f"ACK {vorgangs_id}"
    for datei in rollout_dateien(thread, ordner):
        try:
            with datei.open(encoding="utf-8", errors="replace") as f:
                for zeile in f:
                    if "ACK" not in zeile:
                        continue
                    try:
                        obj = json.loads(zeile)
                    except ValueError:
                        continue
                    if not isinstance(obj, dict):
                        continue
                    zeit = _zeit(obj.get("timestamp")) if "timestamp" in obj else None
                    if zeit is None or zeit < seit.astimezone(timezone.utc):
                        continue
                    text = _antwort_text(obj)
                    if text is not None and text.strip().startswith(erwartet):
                        return True
        except OSError:
            continue
    return False
