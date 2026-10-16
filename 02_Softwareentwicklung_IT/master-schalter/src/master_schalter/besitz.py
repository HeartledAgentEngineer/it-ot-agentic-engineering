"""Besitzmarkierung `<thema>.master` – sie sagt, wer in einem Thema gerade schreibt.

Format: der erste Abschnitt ist der Besitzer.

* `claude <Zeit>` – Claude arbeitet oder wartet (auch `claude <Zeit> fehlgeschlagen <ID>`,
  `claude <Zeit> entwertet <ID>`, `claude <Zeit> wiederaufnahme <alte-lauf-id>`)
* `reserviert <lauf-id> <Zeit>` – die Automatik hat reserviert und prüft gleich nach
* `codex <Vorgang-ID> <Zeit>` – Codex hat übernommen
* `hermes <Zeit> modus <Kennung>` – Hermes ist thematischer Master

Eine **fehlende** Datei gilt als `claude`. Jeder Schreiber hält die Themensperre
(`zustand.thema_sperre`); geschrieben wird atomar (temp + replace).
"""
from __future__ import annotations

from pathlib import Path

from .signale import _atomar_schreiben

CLAUDE, CODEX, RESERVIERT, HERMES = "claude", "codex", "reserviert", "hermes"


def pfad(repo: Path, laufend: str) -> Path:
    """Die Besitzdatei liegt neben der laufenden Übergabe: `…/<thema>.md` wird zu `…/<thema>.master`.

    Nimmt auch einen bereits fertigen `.master`-Pfad an – dann unverändert (idempotent).
    """
    if laufend.endswith(".master"):
        return repo / laufend
    basis = laufend[: -len(".md")] if laufend.endswith(".md") else laufend
    return repo / (basis + ".master")


def lesen(datei: Path) -> str:
    """Inhalt ohne Zeilenenden; fehlende oder unlesbare Datei ergibt leer (= `claude`)."""
    try:
        return datei.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def besitzer(text: str) -> str:
    teile = text.split()
    return teile[0] if teile else CLAUDE


def ist(text: str, wer: str) -> bool:
    return besitzer(text) == wer


def zeile(wer: str, zeit: str, *rest: str) -> str:
    return " ".join([wer, zeit, *rest])


def schreiben(datei: Path, text: str) -> None:
    datei.parent.mkdir(parents=True, exist_ok=True)
    _atomar_schreiben(datei, text)


def vergleiche_und_schreibe(datei: Path, erwartet: str, neu: str) -> bool:
    """Nur schreiben, wenn die Datei weiterhin **genau** `erwartet` enthält (gegen Fremdschreiber).

    Gibt zurück, ob geschrieben wurde. Bei jeder Abweichung bleibt die Datei unberührt.
    """
    if lesen(datei) != erwartet.strip():
        return False
    schreiben(datei, neu)
    return True
