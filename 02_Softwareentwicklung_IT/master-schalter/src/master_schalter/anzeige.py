"""Texte für Tooltip, Menü und Benachrichtigung – reine Funktionen ohne Oberfläche."""
from __future__ import annotations

import json
from datetime import datetime, tzinfo
from pathlib import Path
from typing import TYPE_CHECKING

from . import rollen
from .signale import Fenster, Kontingent, _atomar_schreiben, daten_ordner
from .zustand import Zustand

if TYPE_CHECKING:
    from .wechsel import Ergebnis

STANDARD_SCHWELLE = 97
SCHWELLEN = (80, 90, 95, 97, 100)   # Auswahl im Menü „Wechsel-Schwelle"
MASTER_NAMEN = {"claude": "Claude", "codex": "Codex", "hermes": "Hermes"}
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


def tooltip_kopf(master: str | None, lage: str | None) -> str:
    """Anfang des Tooltips, z. B. „M Claude L1" (Master und Lage)."""
    return f"M {MASTER_NAMEN.get(master, '–')} L{lage or '?'}"


def tooltip(kontingente: list[Kontingent], kopf: str | None = None) -> str:
    teile = [kopf] if kopf else []
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


def schwelle_setzen(wert: int, datei: Path | None = None) -> None:
    """Schreibt die Schwelle (ganze Zahl 1–100) atomar; andere Felder der Datei bleiben erhalten."""
    if isinstance(wert, bool) or not isinstance(wert, int) or not 1 <= wert <= 100:
        raise ValueError(f"Schwelle muss eine ganze Zahl von 1 bis 100 sein, nicht {wert!r}")
    datei = datei or einstellungen_datei()
    try:
        roh = json.loads(datei.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        roh = {}
    if not isinstance(roh, dict):
        roh = {}
    roh["schwelle"] = wert
    _atomar_schreiben(datei, json.dumps(roh, ensure_ascii=False, indent=2))


def claude_takt_min(datei: Path | None = None) -> int:
    """Messintervall in Minuten (1–60) aus `einstellungen.json`, sonst jede Minute."""
    try:
        roh = json.loads((datei or einstellungen_datei()).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 1
    wert = roh.get("claude_takt_min") if isinstance(roh, dict) else None
    if isinstance(wert, bool) or not isinstance(wert, int) or not 1 <= wert <= 60:
        return 1
    return wert


def claude_takt_setzen(wert: int, datei: Path | None = None) -> None:
    """Speichert das Claude-Messintervall (ganze Minuten 1–60) und erhält andere Felder."""
    if isinstance(wert, bool) or not isinstance(wert, int) or not 1 <= wert <= 60:
        raise ValueError("Claude-Takt muss eine ganze Zahl von 1 bis 60 sein")
    datei = datei or einstellungen_datei()
    try:
        roh = json.loads(datei.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        roh = {}
    if not isinstance(roh, dict):
        roh = {}
    roh["claude_takt_min"] = wert
    _atomar_schreiben(datei, json.dumps(roh, ensure_ascii=False, indent=2))


def automatik_an(datei: Path | None = None) -> bool:
    """Automatik Claude → Codex: aus, solange `einstellungen.json` nichts anderes sagt."""
    try:
        roh = json.loads((datei or einstellungen_datei()).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return bool(roh.get("automatik")) if isinstance(roh, dict) else False


def automatik_setzen(an: bool, datei: Path | None = None) -> None:
    """Automatik ein- oder ausschalten; andere Felder der Datei bleiben erhalten."""
    datei = datei or einstellungen_datei()
    try:
        roh = json.loads(datei.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        roh = {}
    if not isinstance(roh, dict):
        roh = {}
    roh["automatik"] = bool(an)
    _atomar_schreiben(datei, json.dumps(roh, ensure_ascii=False, indent=2))


# --- Master und Lage ---------------------------------------------------------

def master_menuezeile(z: Zustand, zone: tzinfo | None = None) -> str:
    """„Master: Claude (seit 14.10. 21:50)" bzw. „Master: nicht gesetzt"."""
    if z.master is None:
        return "Master: nicht gesetzt"
    zeile = f"Master: {MASTER_NAMEN[z.master]}"
    try:
        seit = datetime.fromisoformat(z.seit) if z.seit else None
    except ValueError:
        seit = None
    return zeile + (f" (seit {_zeit(seit, zone)})" if seit else "")


def lage_zeilen(lage: str | None, grund: str) -> list[str]:
    """Menüzeilen zur Lage: Besetzung bei bekannter Lage, sonst „Lage ? – Grund"."""
    b = rollen.besetzung(lage)
    if b is None:
        return ["Lage ?" + (f" – {grund}" if grund else "")]
    return [f"Lage {lage}: {b.name}", f"  Thinker: {b.thinker}", f"  Reviewer: {b.reviewer}",
            f"  Worker: {b.worker}"]


def master_status_zeile(z: Zustand, lage: str | None, grund: str) -> str:
    """Zeile für `masterwechsel status`: „Master: Claude · Lage 1"."""
    name = MASTER_NAMEN.get(z.master, "nicht gesetzt")
    return f"Master: {name} · " + (f"Lage {lage}" if lage else "Lage ?" + (f" – {grund}" if grund else ""))


def wechsel_hinweis(ergebnis: "Ergebnis") -> str:
    """Text der Windows-Benachrichtigung nach einem Klick auf „Master wechseln"."""
    name = MASTER_NAMEN[ergebnis.master]
    if ergebnis.art == "gewechselt":
        text = f"Master jetzt {name} – Übergabe: {ergebnis.paket.name}. Im {name}-Chat lesen lassen."
    elif ergebnis.art == "gleich":
        text = f"Master ist schon {name}."
    else:
        text = f"Wechsel fehlgeschlagen: {ergebnis.meldung}"
    return text[:HINWEIS_MAX]
