"""Verwaltung und Persistierung der Workflow- und Kaskaden-Matrix ('Nach Kontingent')."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import signale

DEFAULT_MATRIX: dict[str, Any] = {
    "lage_1": {
        "name": "Lage 1 (Beide Abos frei)",
        "master": "Claude Opus 5.5",
        "pruefer": "GPT-6 Sol",
        "worker": "GPT-6 Luna",
        "arbeitsweise": "protokoll",
    },
    "lage_2a": {
        "name": "Lage 2A (Claude im Limit)",
        "master": "GPT-6 Sol",
        "pruefer": "DeepSeek V4.1 Flash",
        "worker": "GPT-6 Luna",
        "arbeitsweise": "protokoll",
    },
    "lage_2b": {
        "name": "Lage 2B (ChatGPT im Limit)",
        "master": "Claude Opus 5.5",
        "pruefer": "DeepSeek V4.1 Flash",
        "worker": "Claude Sonnet 5.5",
        "arbeitsweise": "protokoll",
    },
    "lage_3": {
        "name": "Lage 3 (Beide im Limit)",
        "master": "DeepSeek V4.1 Flash",
        "pruefer": "DeepSeek V4.1 Flash",
        "worker": "DeepSeek V4.1 Flash",
        "arbeitsweise": "protokoll",
    },
    "antigravity": {
        "aktiv": True,
        "rolle": "Master / Thinker",
        "bevorzugtes_modell": "Gemini 2.5 Pro",
    },
    "schwellen": {
        "warnung_prozent": 80,
        "wechsel_prozent": 95,
    },
}


def matrix_datei() -> Path:
    return signale.daten_ordner() / "matrix-konfiguration.json"


def matrix_lesen(datei: Path | None = None) -> dict[str, Any]:
    datei = datei or matrix_datei()
    try:
        roh = json.loads(datei.read_text(encoding="utf-8"))
        if isinstance(roh, dict):
            daten = json.loads(json.dumps(DEFAULT_MATRIX))
            daten.update(roh)
            return daten
    except (OSError, ValueError):
        pass
    return json.loads(json.dumps(DEFAULT_MATRIX))


def matrix_schreiben(daten: dict[str, Any], datei: Path | None = None) -> bool:
    datei = datei or matrix_datei()
    try:
        inhalt = json.dumps(daten, ensure_ascii=False, indent=2)
        signale._atomar_schreiben(datei, inhalt)
        return True
    except OSError:
        return False
