"""Der Master-Zustand: wer ist Master, seit wann, welches Übergabepaket zuletzt.

Die Datei `master.json` liegt im Datenordner (`%USERPROFILE%/.master-schalter/`), nicht im Repo.
Jede Änderung läuft über `aendern(funktion)`: Die Funktion hält für den gesamten
Lese-Änderungs-Schreib-Vorgang eine exklusive Betriebssystem-Sperre auf der dauerhaft liegenden
Datei `master.json.lock`. Stirbt der Halter, gibt das Betriebssystem die Sperre frei – es gibt
keine verwaiste Sperre. Die Sperrdatei wird nie gelöscht.
"""
from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterator

from .signale import _atomar_schreiben, daten_ordner

MASTER = ("claude", "codex", "hermes")
FRIST_SEKUNDEN = 5.0
TAKT_SEKUNDEN = 0.05


class SperrFehler(Exception):
    """Die Sperre blieb bis zur Frist belegt."""


@dataclass(frozen=True)
class Zustand:
    master: str | None = None      # "claude" | "codex" | "hermes" | None (= nicht gesetzt)
    seit: str | None = None        # ISO-Zeit des letzten Wechsels
    uebergabe: str | None = None   # Pfad des letzten Übergabepakets


def datei() -> Path:
    return daten_ordner() / "master.json"


def sperrdatei() -> Path:
    return daten_ordner() / "master.json.lock"


def _text(wert: object) -> str | None:
    return wert if isinstance(wert, str) and wert else None


def lesen() -> Zustand:
    """Fehlende oder kaputte Datei ergibt „nicht gesetzt" – nie einen Absturz."""
    try:
        roh = json.loads(datei().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return Zustand()
    if not isinstance(roh, dict):
        return Zustand()
    master = roh.get("master")
    return Zustand(master if master in MASTER else None, _text(roh.get("seit")), _text(roh.get("uebergabe")))


# --- Sperre ------------------------------------------------------------------

def _versuchen(fd: int) -> bool:
    """Ein Sperrversuch auf Byte 0; False = belegt."""
    os.lseek(fd, 0, os.SEEK_SET)
    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


def _freigeben(fd: int) -> None:
    try:
        if os.name == "nt":
            import msvcrt
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_UN)
    except OSError:
        pass  # Schließen des Handles gibt die Sperre ohnehin frei


@contextmanager
def sperre(frist: float = FRIST_SEKUNDEN, takt: float = TAKT_SEKUNDEN) -> Iterator[None]:
    """Exklusive Sperre; Versuche alle 50 ms, nach `frist` Sekunden `SperrFehler`."""
    pfad = sperrdatei()
    pfad.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(pfad, os.O_RDWR | os.O_CREAT, 0o666)
    try:
        ende = time.monotonic() + frist
        while not _versuchen(fd):
            if time.monotonic() >= ende:
                raise SperrFehler(f"Sperre auf {pfad.name} blieb {frist:g} s belegt")
            time.sleep(takt)
        try:
            yield
        finally:
            _freigeben(fd)
    finally:
        os.close(fd)


def aendern(funktion: Callable[[Zustand], Zustand], frist: float = FRIST_SEKUNDEN) -> Zustand:
    """Liest den Zustand, ruft `funktion` auf und schreibt das Ergebnis atomar – alles unter der Sperre.

    Wirft die Funktion, bleibt die Datei unverändert. Bei belegter Sperre wird die Funktion
    gar nicht erst aufgerufen (`SperrFehler`).
    """
    with sperre(frist):
        alt = lesen()
        neu = funktion(alt)
        if neu.master is not None and neu.master not in MASTER:
            raise ValueError(f"unbekannter Master: {neu.master!r}")
        if neu != alt or not datei().exists():
            _atomar_schreiben(datei(), json.dumps(asdict(neu), ensure_ascii=False))
        return neu


# --- Themensperre (Automatik) -------------------------------------------------

def themen_sperrdatei(thema: str) -> Path:
    """Sperrdatei eines Themas; gleicher Ordner wie der Zustand, damit die Reihenfolge gilt."""
    return daten_ordner() / f"automatik-{thema}.lock"


@contextmanager
def thema_sperre(thema: str, blockierend: bool = False,
                 frist: float = FRIST_SEKUNDEN, takt: float = TAKT_SEKUNDEN) -> Iterator[bool]:
    """Exklusive Sperre **eines Themas**; gibt zurück, ob sie erworben wurde.

    Nicht blockierend (Standard) überspringt ein belegtes Thema sofort (`False`) – so laufen
    zwei Automatikläufe nie gleichzeitig an demselben Thema. Blockierend (Rückwechsel) wird bis
    `frist` gewartet; danach `False`, und es darf nichts geschrieben werden. Das Betriebssystem
    gibt die Sperre beim Prozessende frei – es gibt keine verwaiste Sperre; die Datei bleibt liegen.
    """
    pfad = themen_sperrdatei(thema)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(pfad, os.O_RDWR | os.O_CREAT, 0o666)
    try:
        ende = time.monotonic() + frist
        while True:
            if _versuchen(fd):
                break
            if not blockierend or time.monotonic() >= ende:
                yield False
                return
            time.sleep(takt)
        try:
            yield True
        finally:
            _freigeben(fd)
    finally:
        os.close(fd)
