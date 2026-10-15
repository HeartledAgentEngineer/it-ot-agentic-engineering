"""Masterwechsel: Sperre holen, Übergabepaket bauen, Zustand setzen – in dieser Reihenfolge.

Scheitert die Sperre (Zeitüberschreitung) oder das Paket, wird nichts am Zustand geändert.
Gemeinsamer Weg für `masterwechsel wechsel` und das Klickmenü der Taskleiste.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from . import uebergabe, zustand


@dataclass(frozen=True)
class Ergebnis:
    art: str                # "gewechselt" | "gleich" | "fehler"
    master: str             # Ziel-Master ("claude" | "codex")
    paket: Path | None      # nur bei "gewechselt"
    meldung: str            # Fehlertext bei "fehler", sonst leer


def wechseln(nach: str, hinweis: str | None = None, jetzt: datetime | None = None,
             frist: float = zustand.FRIST_SEKUNDEN) -> Ergebnis:
    if nach not in zustand.MASTER:
        raise ValueError(f"unbekannter Master: {nach!r}")
    jetzt = jetzt or datetime.now().astimezone()
    erzeugt: dict[str, Path] = {}

    def aenderung(alt: zustand.Zustand) -> zustand.Zustand:
        if alt.master == nach:
            return alt
        paket = uebergabe.paket_bauen(alt.master or "unbekannt", nach, hinweis, jetzt=jetzt)
        erzeugt["paket"] = paket
        return replace(alt, master=nach, seit=jetzt.isoformat(), uebergabe=str(paket))

    try:
        zustand.aendern(aenderung, frist=frist)
    except zustand.SperrFehler as fehler:
        return Ergebnis("fehler", nach, None, str(fehler))
    except uebergabe.UebergabeFehler as fehler:
        return Ergebnis("fehler", nach, None, str(fehler))
    except OSError as fehler:
        return Ergebnis("fehler", nach, None, f"Zustand nicht geschrieben: {fehler}")
    if "paket" not in erzeugt:
        return Ergebnis("gleich", nach, None, "")
    return Ergebnis("gewechselt", nach, erzeugt["paket"], "")
