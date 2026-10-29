"""Paare aus Thema und Codex-Chat (`paare.json` im Datenordner).

Ein Paar verbindet ein Arbeitsthema mit dem Codex-Chat, der es übernehmen soll, und mit der
laufenden Übergabedatei. Das **Thema** ist die einzige freie Angabe und wird streng geprüft
(`re.fullmatch`, nur Kleinbuchstaben/Ziffern/Bindestrich, 1–80 Zeichen); aus ihm entstehen
Dateiname und Automatikpfad. Die **Chat-Kennung** ist eine geprüfte, eindeutige UUID. Der
**laufende Pfad** ist kein freier Dateiname, sondern exakt `.hermes/uebergabe/laufend/<thema>.md`
(relativ zur Repo-Wurzel). `aktiv` steuert, ob die Automatik das Paar überhaupt anfasst.
"""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from . import zustand
from .signale import _atomar_schreiben, daten_ordner

THEMA_MUSTER = re.compile(r"[a-z0-9][a-z0-9-]{0,79}")
LAUFEND_BASIS = ".hermes/uebergabe/laufend"


class PaarFehler(Exception):
    """Thema, Kennung, Pfad oder Doppelung ist nicht zulässig."""


@dataclass(frozen=True)
class Paar:
    thema: str
    codex_thread: str       # UUID des Ziel-Chats (klein geschrieben)
    laufend: str            # exakt `.hermes/uebergabe/laufend/<thema>.md`
    aktiv: bool = False

    @property
    def master_datei(self) -> str:
        """Besitzdatei des Themas, neben der laufenden Übergabe (`<thema>.master`)."""
        return self.laufend[: -len(".md")] + ".master"


def datei() -> Path:
    return daten_ordner() / "paare.json"


def thema_pruefen(thema: str) -> str:
    """Nur `^[a-z0-9][a-z0-9-]{0,79}$` – als `re.fullmatch`, ein abschließendes LF wird abgelehnt."""
    if not isinstance(thema, str) or THEMA_MUSTER.fullmatch(thema) is None:
        raise PaarFehler(f"Thema unzulässig (erlaubt: {THEMA_MUSTER.pattern}): {thema!r}")
    return thema


def thread_pruefen(thread: str) -> str:
    """Kennung als UUID; gespeichert wird die kanonische Kleinform."""
    if not isinstance(thread, str):
        raise PaarFehler(f"Chat-Kennung ist keine UUID: {thread!r}")
    try:
        geprueft = uuid.UUID(thread)
    except (ValueError, AttributeError, TypeError):
        raise PaarFehler(f"Chat-Kennung ist keine UUID: {thread!r}") from None
    return str(geprueft)


def laufend_bilden(thema: str) -> str:
    """Der laufende Pfad wird aus dem geprüften Thema gebildet – nie frei angegeben."""
    return f"{LAUFEND_BASIS}/{thema_pruefen(thema)}.md"


def _normalisiert(pfad: str) -> str:
    return pfad.replace("\\", "/").strip()


def laufend_pruefen(thema: str, laufend: str) -> str:
    """Der Pfad muss exakt dem aus dem Thema gebildeten entsprechen (auch kein `..`, kein Ordnerwechsel)."""
    erwartet = laufend_bilden(thema)
    if _normalisiert(laufend) != erwartet:
        raise PaarFehler(f"laufender Pfad muss exakt {erwartet!r} sein, nicht {laufend!r}")
    return erwartet


def _paar(roh: object) -> Paar | None:
    if not isinstance(roh, dict):
        return None
    thema, thread, laufend = roh.get("thema"), roh.get("codex_thread"), roh.get("laufend")
    if not isinstance(thema, str) or not isinstance(thread, str) or not isinstance(laufend, str):
        return None
    try:
        geprueft = thema_pruefen(thema)
        laufend_geprueft = laufend_pruefen(geprueft, laufend)
        return Paar(geprueft, thread_pruefen(thread), laufend_geprueft, bool(roh.get("aktiv", False)))
    except PaarFehler:
        return None


def lesen(datei_pfad: Path | None = None) -> list[Paar]:
    """Fehlende oder kaputte Datei ergibt eine leere Liste; unbrauchbare Einträge werden übersprungen."""
    try:
        roh = json.loads((datei_pfad or datei()).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(roh, list):
        return []
    paare: list[Paar] = []
    for eintrag in roh:
        paar = _paar(eintrag)
        if paar is not None and paar not in paare:
            paare.append(paar)
    return paare


def schreiben(paare: list[Paar], datei_pfad: Path | None = None) -> None:
    """Paare atomar und unter der gemeinsamen Zustands-OS-Sperre speichern."""
    try:
        with zustand.sperre():
            _schreiben_gesperrt(paare, datei_pfad)
    except zustand.SperrFehler as fehler:
        raise PaarFehler(f"Paarliste konnte nicht gesperrt werden: {fehler}") from fehler


def _schreiben_gesperrt(paare: list[Paar], datei_pfad: Path | None = None) -> None:
    """Atomar schreiben, wenn der Aufrufer bereits `zustand.sperre()` hält."""
    _atomar_schreiben(datei_pfad or datei(), json.dumps([asdict(p) for p in paare], ensure_ascii=False, indent=2))


def setzen(thema: str, codex_thread: str, laufend: str, aktiv: bool | None = None,
           datei_pfad: Path | None = None) -> Paar:
    """Ein Paar anlegen oder überschreiben.

    Dasselbe Thema darf erneut gesetzt werden (die Auswahl bleibt erhalten, `aktiv` nur, wenn
    angegeben). Eine Chat-Kennung, die schon zu einem **anderen** Thema gehört, wird abgelehnt –
    je Chat genau ein Paar.
    """
    thema_pruefen(thema)
    thread_pruefen(codex_thread)
    laufend_pruefen(thema, laufend)
    try:
        with zustand.sperre():
            return _setzen_gesperrt(thema, codex_thread, laufend, aktiv, datei_pfad)
    except zustand.SperrFehler as fehler:
        raise PaarFehler(f"Paarliste konnte nicht gesperrt werden: {fehler}") from fehler


def _setzen_gesperrt(thema: str, codex_thread: str, laufend: str, aktiv: bool | None = None,
                    datei_pfad: Path | None = None) -> Paar:
    """Ein Paar setzen, wenn der Aufrufer bereits `zustand.sperre()` hält."""
    thema, thread = thema_pruefen(thema), thread_pruefen(codex_thread)
    pfad = laufend_pruefen(thema, laufend)
    alt = lesen(datei_pfad)
    fremd = next((p for p in alt if p.codex_thread == thread and p.thema != thema), None)
    if fremd is not None:
        raise PaarFehler(f"Kennung {thread} gehört schon zum Thema {fremd.thema!r}")
    bisher = next((p for p in alt if p.thema == thema), None)
    neu = Paar(thema, thread, pfad, bisher.aktiv if aktiv is None and bisher else bool(aktiv))
    _schreiben_gesperrt(sorted([p for p in alt if p.thema != thema] + [neu], key=lambda p: p.thema), datei_pfad)
    return neu


def aktiv_setzen(thema: str, an: bool, datei_pfad: Path | None = None) -> Paar:
    """Ein vorhandenes Paar an- oder abschalten; unbekanntes Thema wird abgelehnt."""
    thema = thema_pruefen(thema)
    try:
        with zustand.sperre():
            alt = lesen(datei_pfad)
            bisher = next((p for p in alt if p.thema == thema), None)
            if bisher is None:
                raise PaarFehler(f"Thema unbekannt: {thema!r}")
            neu = Paar(bisher.thema, bisher.codex_thread, bisher.laufend, bool(an))
            _schreiben_gesperrt([neu if p.thema == thema else p for p in alt], datei_pfad)
            return neu
    except zustand.SperrFehler as fehler:
        raise PaarFehler(f"Paarliste konnte nicht gesperrt werden: {fehler}") from fehler


def aktive(datei_pfad: Path | None = None) -> list[Paar]:
    """Nur eingeschaltete Paare – inaktive werden von der Automatik nie gesendet."""
    return [p for p in lesen(datei_pfad) if p.aktiv]
