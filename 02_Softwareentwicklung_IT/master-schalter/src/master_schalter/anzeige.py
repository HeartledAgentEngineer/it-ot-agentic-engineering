"""Texte für Tooltip, Menü und Benachrichtigung – reine Funktionen ohne Oberfläche."""
from __future__ import annotations

import json
from datetime import datetime, tzinfo
from pathlib import Path

from .signale import Fenster, Kontingent, daten_ordner

STANDARD_SCHWELLE = 97
WARN_AB = 80
TOOLTIP_MAX = 127   # Windows schneidet Tooltips von Taskleisten-Symbolen bei 127 Zeichen ab
HINWEIS_MAX = 255   # Windows-Benachrichtigungen fassen höchstens 255 Zeichen


def _kurz(prozent: float | None) -> str:
    return "–" if prozent is None else f"{round(prozent)}%"


def _lang(prozent: float | None) -> str:
    return "–" if prozent is None else f"{round(prozent)} %"


def _zeit(wert: datetime | None, zone: tzinfo | None) -> str:
    return "?" if wert is None else wert.astimezone(zone).strftime("%d.%m. %H:%M")


def _prozent(k: Kontingent, name: str) -> float | None:
    f = k.fenster_nach_name(name)
    return f.prozent if f else None


def tooltip(kontingente: list[Kontingent]) -> str:
    teile = []
    for k in kontingente:
        if k.fehler:
            teile.append(f"{k.master}: {k.fehler}")
        else:
            teile.append(f"{k.master} 5h {_kurz(_prozent(k, '5h'))} · Wo {_kurz(_prozent(k, 'Woche'))}")
    text = " | ".join(teile)
    return text if len(text) <= TOOLTIP_MAX else text[: TOOLTIP_MAX - 1] + "…"


def _fenster_zeile(f: Fenster, zone: tzinfo | None) -> str:
    if f.zurueckgesetzt:
        return f"  {f.name}: zurückgesetzt (seit {_zeit(f.reset, zone)})"
    zeile = f"  {f.name}: {_lang(f.prozent)}"
    return zeile + (f" · Reset {_zeit(f.reset, zone)}" if f.reset else "")


def details(kontingente: list[Kontingent], zone: tzinfo | None = None) -> list[str]:
    zeilen: list[str] = []
    for k in kontingente:
        zeilen.append(k.master)
        if k.fehler:
            zeilen.append(f"  {k.fehler}")
            continue
        zeilen += [_fenster_zeile(f, zone) for f in k.fenster]
        zeilen.append(f"  Stand: {_zeit(k.stand, zone)}")
    return zeilen


def hinweis(kontingente: list[Kontingent], zone: tzinfo | None = None) -> str:
    zeilen = []
    for k in kontingente:
        if k.fehler:
            zeilen.append(f"{k.master}: {k.fehler}")
        else:
            zeilen.append(f"{k.master}: 5h {_lang(_prozent(k, '5h'))} · Woche {_lang(_prozent(k, 'Woche'))}"
                          f" (Stand {_zeit(k.stand, zone)})")
    return "\n".join(zeilen)[:HINWEIS_MAX]


def stufe(prozent: float | None, schwelle: int) -> str:
    if prozent is None:
        return "unbekannt"
    if prozent >= schwelle:
        return "voll"
    return "warn" if prozent >= WARN_AB else "ok"


def einstellungen_datei() -> Path:
    return daten_ordner() / "einstellungen.json"


def schwelle(datei: Path | None = None) -> int:
    """Schwelle in Prozent (1–100) aus `einstellungen.json`, sonst 97."""
    try:
        roh = json.loads((datei or einstellungen_datei()).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return STANDARD_SCHWELLE
    wert = roh.get("schwelle") if isinstance(roh, dict) else None
    if isinstance(wert, bool) or not isinstance(wert, int) or not 1 <= wert <= 100:
        return STANDARD_SCHWELLE
    return wert
