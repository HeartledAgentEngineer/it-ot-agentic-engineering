"""Besitzmarkierung `<thema>.master` – sie sagt, wer in einem Thema gerade schreibt.

Format: der erste Abschnitt ist der Besitzer.

* `claude <Zeit>` – Claude arbeitet oder wartet (auch `claude <Zeit> fehlgeschlagen <ID>`,
  `claude <Zeit> entwertet <ID>`, `claude <Zeit> wiederaufnahme <alte-lauf-id>`)
* `reserviert <lauf-id> <Zeit>` – die Automatik hat reserviert und prüft gleich nach
* `codex <Vorgang-ID> <Zeit>` – Codex hat übernommen
* `hermes <Zeit> modus <Kennung>` – Hermes ist thematischer Master
* `agy <Zeit> modus <Kennung>` – Antigravity (Gemini) ist thematischer Master
* `<Rolle> <Zeit> assistent <Thema> <Vorgang-ID>` – der Wechselassistent hat übergeben; die
  Vorgangs-ID macht jeden älteren Postfachauftrag ungültig, sobald ein späterer Wechsel die Marke überschreibt

Eine **fehlende** Datei gilt als `claude`. Jeder Schreiber hält die Themensperre
(`zustand.thema_sperre`); geschrieben wird atomar (temp + replace).
"""
from __future__ import annotations

import os
from pathlib import Path

from .signale import _atomar_schreiben, _iso

CLAUDE, CODEX, RESERVIERT, HERMES, AGY = "claude", "codex", "reserviert", "hermes", "agy"
ASSISTENT = "assistent"


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


def assistent_zeile(wer: str, zeit: str, thema: str, vorgang_id: str) -> str:
    """Marke des Wechselassistenten: `<Rolle> <Zeit> assistent <Thema> <Vorgang-ID>`."""
    return zeile(wer, zeit, ASSISTENT, thema, vorgang_id)


def assistent_marke(text: str) -> tuple[str, str, str] | None:
    """`(Rolle, Thema, Vorgang-ID)` einer Assistentenmarke in strengem Format, sonst `None`."""
    teile = text.split()
    if len(teile) != 5 or teile[2] != ASSISTENT or _iso(teile[1]) is None:
        return None
    return teile[0], teile[3], teile[4]


def schreiben(datei: Path, text: str) -> None:
    datei.parent.mkdir(parents=True, exist_ok=True)
    _atomar_schreiben(datei, text)


def exklusiv_schreiben(datei: Path, text: str) -> bool:
    """Datei nur anlegen, wenn es sie noch nicht gibt (`O_EXCL`): `True` = angelegt, `False` = existierte schon.

    Eine vorhandene Datei – auch eine leere – wird nie überschrieben. Scheitert das Schreiben nach dem Anlegen, wird die
    eben selbst angelegte Datei wieder entfernt.
    """
    datei.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(datei, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
    except FileExistsError:
        return False
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
    except BaseException:
        datei.unlink(missing_ok=True)     # nur die eben selbst angelegte Datei
        raise
    return True


def vergleiche_und_schreibe(datei: Path, erwartet: str, neu: str) -> bool:
    """Nur schreiben, wenn die Datei weiterhin **genau** `erwartet` enthält (gegen Fremdschreiber).

    Gibt zurück, ob geschrieben wurde. Bei jeder Abweichung bleibt die Datei unberührt.
    """
    if lesen(datei) != erwartet.strip():
        return False
    schreiben(datei, neu)
    return True
