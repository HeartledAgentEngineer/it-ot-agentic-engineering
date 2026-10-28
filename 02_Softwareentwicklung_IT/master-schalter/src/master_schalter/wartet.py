"""„Wartet worauf“ je Thema: kurze technische Meldung, die `kurz` anzeigt (`masterwechsel warte`).

Layout: `<datenordner>/wartet/<thema>.json` mit `{"text": <eine Zeile, höchstens 120 Zeichen>, "zeit": <ISO UTC>}`.
Das Thema wird mit `paare.thema_pruefen` geprüft; der Dateiname entsteht nur daraus. Geschrieben wird atomar.
Der Text soll eine technische Kurzangabe sein („Freigabe Vibe-Modus“, „Codex-Prüfung R2“) – keine Inhalte,
Namen oder Pfade. Erzwingen kann der Code das nicht; er begrenzt Form und Länge.

`alle_lesen` überspringt fehlende, zu große oder kaputte Dateien, statt zu raten.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import paare
from .signale import _atomar_schreiben, daten_ordner

MAX_ZEICHEN = 120
MAX_BYTES = 1024
_LEERRAUM = re.compile(r"\s+")


class WartetFehler(Exception):
    """Thema oder Text ist nicht zulässig."""


@dataclass(frozen=True)
class Meldung:
    thema: str
    text: str
    zeit: datetime


def ordner() -> Path:
    return daten_ordner() / "wartet"


def datei(thema: str) -> Path:
    try:
        return ordner() / f"{paare.thema_pruefen(thema)}.json"
    except paare.PaarFehler as fehler:
        raise WartetFehler(str(fehler)) from fehler


def text_bereinigen(text: str) -> str:
    """Eine Zeile: Steuerzeichen und Zeilenumbrüche werden zu Leerzeichen, höchstens `MAX_ZEICHEN` Zeichen."""
    if not isinstance(text, str):
        raise WartetFehler("Text fehlt")
    zeile = "".join(" " if not z.isprintable() else z for z in text)
    zeile = _LEERRAUM.sub(" ", zeile).strip()
    if not zeile:
        raise WartetFehler("Text ist leer")
    return zeile if len(zeile) <= MAX_ZEICHEN else zeile[: MAX_ZEICHEN - 1].rstrip() + "…"


def setzen(thema: str, text: str, jetzt: datetime | None = None) -> Meldung:
    pfad = datei(thema)
    meldung = Meldung(thema, text_bereinigen(text), jetzt or datetime.now(timezone.utc))
    _atomar_schreiben(pfad, json.dumps({"text": meldung.text, "zeit": meldung.zeit.isoformat()},
                                       ensure_ascii=False))
    return meldung


def loeschen(thema: str) -> bool:
    """Meldung des Themas entfernen; `False`, wenn keine da war (idempotent)."""
    try:
        datei(thema).unlink()
    except FileNotFoundError:
        return False
    return True


def _lesen(pfad: Path) -> Meldung | None:
    try:
        if pfad.stat().st_size > MAX_BYTES:
            return None
        roh = json.loads(pfad.read_text(encoding="utf-8"))
        paare.thema_pruefen(pfad.stem)
    except (OSError, ValueError, paare.PaarFehler):
        return None
    if not isinstance(roh, dict) or not isinstance(roh.get("text"), str) or not isinstance(roh.get("zeit"), str):
        return None
    try:
        zeit = datetime.fromisoformat(roh["zeit"])
        text = text_bereinigen(roh["text"])
    except (ValueError, WartetFehler):
        return None
    return Meldung(pfad.stem, text, zeit if zeit.tzinfo else zeit.replace(tzinfo=timezone.utc))


def alle_lesen() -> list[Meldung]:
    """Alle gültigen Meldungen, älteste zuerst; ungültige Dateien bleiben unberührt und ungezeigt."""
    try:
        pfade = sorted(ordner().glob("*.json"))
    except OSError:
        return []
    meldungen = [m for m in (_lesen(p) for p in pfade) if m is not None]
    return sorted(meldungen, key=lambda m: m.zeit)
