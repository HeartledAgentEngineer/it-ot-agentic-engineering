"""Was gesendet werden soll: ein Auftrag je Thema und Limitfenster."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Auftrag:
    """Ein beschlossener Übergabeauftrag (Ergebnis der Entscheidung, noch nicht gesendet)."""

    thema: str
    lauf_id: str            # Lauf-Kennung der Reservierung, die diesen Auftrag erzeugt
    id: str                 # `<thema>@<resets_at>` – je Paar und Limitfenster genau einmal
    codex_thread: str       # UUID des Zielchats
    laufend: str            # laufende Übergabedatei (repo-relativ)
    master_datei: str       # Besitzdatei des Themas (repo-relativ)
    fuenf: float            # Claude 5-Stunden-Verbrauch in Prozent
    woche: float            # Claude Wochen-Verbrauch in Prozent
    frei_ab: datetime       # Rücksetzzeit des auslösenden Fensters
    lage: str               # Lage der Kaskaden-Matrix (2A)
