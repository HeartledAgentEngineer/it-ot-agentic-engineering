"""Verwaltung und Persistierung der Workflow- und Kaskaden-Matrix ('Nach Kontingent')."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import signale

VERFUEGBARE_MASTER = (
    "Claude Opus 5.5",
    "Argon (Antigravity)",
    "Gemini 3.8 Flash",
    "GPT-6 Sol",
    "DeepSeek V4.1 Flash",
)

VERFUEGBARE_PRUEFER = (
    "GPT-6 Sol",
    "Claude Opus 5.5",
    "DeepSeek V4.1 Flash",
    "Argon (Antigravity)",
    "Gemini 3.8 Flash",
    "App-Standard (Codex)",
)

VERFUEGBARE_WORKER = (
    "GPT-6 Luna",
    "Claude Sonnet 5.5",
    "Gemini 3.8 Flash",
    "DeepSeek V4.1 Flash",
    "Argon (Antigravity)",
)

PRESETS: dict[str, dict[str, Any]] = {
    "Standard (AGENTS.md)": {
        "lage_1": {"master": "Claude Opus 5.5", "pruefer": "GPT-6 Sol", "worker": "GPT-6 Luna"},
        "lage_2a": {"master": "GPT-6 Sol", "pruefer": "DeepSeek V4.1 Flash", "worker": "GPT-6 Luna"},
        "lage_2b": {"master": "Claude Opus 5.5", "pruefer": "DeepSeek V4.1 Flash", "worker": "Claude Sonnet 5.5"},
        "lage_3": {"master": "DeepSeek V4.1 Flash", "pruefer": "DeepSeek V4.1 Flash", "worker": "DeepSeek V4.1 Flash"},
        "antigravity": {"rolle": "Master / Thinker", "modell": "Claude Opus 5.5"},
    },
    "Integrative Maschine (Claude Opus 5.5)": {
        "lage_1": {"master": "Claude Opus 5.5", "pruefer": "GPT-6 Sol", "worker": "Gemini 3.8 Flash"},
        "lage_2a": {"master": "Claude Opus 5.5", "pruefer": "DeepSeek V4.1 Flash", "worker": "Gemini 3.8 Flash"},
        "lage_2b": {"master": "Claude Opus 5.5", "pruefer": "DeepSeek V4.1 Flash", "worker": "Gemini 3.8 Flash"},
        "lage_3": {"master": "Claude Opus 5.5", "pruefer": "DeepSeek V4.1 Flash", "worker": "DeepSeek V4.1 Flash"},
        "antigravity": {"rolle": "Master / Thinker", "modell": "Claude Opus 5.5"},
    },
    "Antigravity & Argon (Google AI)": {
        "lage_1": {"master": "Argon (Antigravity)", "pruefer": "Claude Opus 5.5", "worker": "Gemini 3.8 Flash"},
        "lage_2a": {"master": "Argon (Antigravity)", "pruefer": "DeepSeek V4.1 Flash", "worker": "Gemini 3.8 Flash"},
        "lage_2b": {"master": "Gemini 3.8 Flash", "pruefer": "DeepSeek V4.1 Flash", "worker": "DeepSeek V4.1 Flash"},
        "lage_3": {"master": "Gemini 3.8 Flash", "pruefer": "DeepSeek V4.1 Flash", "worker": "DeepSeek V4.1 Flash"},
        "antigravity": {"rolle": "Master / Thinker", "modell": "Argon (Antigravity)"},
    },
    "Gemini 3.8 Flash Fokus": {
        "lage_1": {"master": "Gemini 3.8 Flash", "pruefer": "GPT-6 Sol", "worker": "Gemini 3.8 Flash"},
        "lage_2a": {"master": "Gemini 3.8 Flash", "pruefer": "DeepSeek V4.1 Flash", "worker": "Gemini 3.8 Flash"},
        "lage_2b": {"master": "Gemini 3.8 Flash", "pruefer": "DeepSeek V4.1 Flash", "worker": "Gemini 3.8 Flash"},
        "lage_3": {"master": "Gemini 3.8 Flash", "pruefer": "DeepSeek V4.1 Flash", "worker": "DeepSeek V4.1 Flash"},
        "antigravity": {"rolle": "Master / Thinker", "modell": "Gemini 3.8 Flash"},
    },
    "DeepSeek Notlauf (Budget)": {
        "lage_1": {"master": "DeepSeek V4.1 Flash", "pruefer": "DeepSeek V4.1 Flash", "worker": "DeepSeek V4.1 Flash"},
        "lage_2a": {"master": "DeepSeek V4.1 Flash", "pruefer": "DeepSeek V4.1 Flash", "worker": "DeepSeek V4.1 Flash"},
        "lage_2b": {"master": "DeepSeek V4.1 Flash", "pruefer": "DeepSeek V4.1 Flash", "worker": "DeepSeek V4.1 Flash"},
        "lage_3": {"master": "DeepSeek V4.1 Flash", "pruefer": "DeepSeek V4.1 Flash", "worker": "DeepSeek V4.1 Flash"},
        "antigravity": {"rolle": "Worker / Ausführer", "modell": "DeepSeek V4.1 Flash"},
    },
}

DEFAULT_PRESET_NAME = "Standard (AGENTS.md)"

DEFAULT_MATRIX: dict[str, Any] = {
    "preset": DEFAULT_PRESET_NAME,
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
        "bevorzugtes_modell": "Claude Opus 5.5",
    },
    "schwellen": {
        "warnung_prozent": 80,
        "wechsel_prozent": 95,
    },
}


def matrix_datei() -> Path:
    return signale.daten_ordner() / "matrix-konfiguration.json"


def matrix_initialisieren_wenn_noetig() -> None:
    datei = matrix_datei()
    if not datei.exists():
        matrix_schreiben(DEFAULT_MATRIX, datei=datei)


def matrix_lesen(datei: Path | None = None) -> dict[str, Any]:
    datei = datei or matrix_datei()
    try:
        if not datei.exists():
            matrix_initialisieren_wenn_noetig()
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


def preset_anwenden(preset_name: str, datei: Path | None = None) -> dict[str, Any]:
    """Wendet ein vordefiniertes Matrix-Preset an und speichert es."""
    preset = PRESETS.get(preset_name)
    if not preset:
        preset = PRESETS[DEFAULT_PRESET_NAME]
        preset_name = DEFAULT_PRESET_NAME

    daten = json.loads(json.dumps(DEFAULT_MATRIX))
    daten["preset"] = preset_name
    for lage_key in ("lage_1", "lage_2a", "lage_2b", "lage_3"):
        if lage_key in preset:
            daten[lage_key].update(preset[lage_key])
    if "antigravity" in preset:
        daten["antigravity"].update(preset["antigravity"])
    matrix_schreiben(daten, datei=datei)
    return daten
