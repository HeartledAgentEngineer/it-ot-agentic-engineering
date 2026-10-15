"""Senden des Automatikauftrags an den Codex-Chat (`codex.exe queue`).

Ablauf in **festgelegter, sicherer Reihenfolge**:

1. Erster `vorgaenge.aendern`-Vorgang: unter der globalen Sperre prüfen, dass die
   Vorgangskennung noch nicht existiert, `phase="sende"` eintragen und zurückkehren – der Eintrag
   liegt damit **dauerhaft auf der Platte**, bevor irgendetwas gesendet wird. Ein zweiter Prozess
   sieht ihn und sendet nie.
2. Außerhalb der globalen Sperre das Paket bauen – im Automatikweg **ohne** repo-weite Planliste
   und **ohne** Repo-Freitext (`paket_bauen(..., plaene=False, minimal=True)`); der Hinweis ist
   ausschließlich der gebildete Pfad der laufenden Übergabe.
3. Besitzmarke auf `codex <id> <Zeit>` setzen (nur wenn sie noch genau die eigene Reservierung
   trägt) – der Transport sieht sie also beim Start bereits.
4. Transport synchron starten: `codex.exe queue --thread <UUID> --message <Prompt>` (Argumentliste,
   keine Shell, Zeitgrenze 60 s).
5. Zweiter `vorgaenge.aendern`-Vorgang: `phase="gesendet"`, `"fehler"` oder `"unklar"`.

Nur ein belegtes **Nicht-Starten** des Transportprozesses (kein Kindprozess) erlaubt das
Rücksetzen auf `claude <Zeit> fehlgeschlagen <ID>`. Nichtnull-Rückgabe eines gestarteten
Prozesses, Zeitüberschreitung, Abbruch oder fehlende Antwort gelten konservativ als **unklar**:
der Auftrag kann bereits zugestellt sein, Codex-Besitz und Kennung bleiben erhalten.
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Callable

from . import besitz, uebergabe, vorgaenge
from .auftrag import Auftrag

TIMEOUT_SEKUNDEN = 60
QUEUE = "queue"
START_FEHLER = (FileNotFoundError, PermissionError, NotADirectoryError)

Transport = Callable[[list[str], int], int]   # (Argumentliste, Zeitgrenze) -> Rückgabewert


@dataclass(frozen=True)
class Ergebnis:
    phase: str            # "gesendet" | "fehler" | "unklar" | "doppelt"
    paket: Path | None
    meldung: str = ""


def programm() -> str | None:
    """Neuestes `codex.exe` der Codex-App; `MASTER_SCHALTER_CODEX` hat Vorrang (wie `pruefkreis.py`)."""
    eigen = os.environ.get("MASTER_SCHALTER_CODEX")
    if eigen:
        return eigen
    basis = Path(os.environ.get("LOCALAPPDATA", "")) / "OpenAI" / "Codex" / "bin"
    try:
        treffer = sorted(basis.glob("*/codex.exe"), key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        return None
    return str(treffer[0]) if treffer else None


def _transport(liste: list[str], timeout: int) -> int:
    return subprocess.run(liste, capture_output=True, text=True, timeout=timeout).returncode


def prompt(auftrag: Auftrag, repo: Path, paket: Path) -> str:
    """Fester Prompt – nur Pfade, Kennung und Zahlen; **kein** Dateiinhalt."""
    laufend = (repo / auftrag.laufend).as_posix()
    master_datei = (repo / auftrag.master_datei).as_posix()
    frei_ab = auftrag.frei_ab.astimezone().strftime("%d.%m.%Y %H:%M")
    return (
        f"Automatische Masterübergabe {auftrag.id}. Claude Code ist im Nutzungslimit "
        f"(5 h {auftrag.fuenf:.0f} %, Woche {auftrag.woche:.0f} %, frei ab {frei_ab}). "
        f"Übernimm als Master (Thinker) nach AGENTS.md, Lage {auftrag.lage}. "
        f"**Erster Schritt (Planprüfung v0.3 R6/1):** Lies {master_datei}. Steht dort nicht genau "
        f"`codex {auftrag.id}` am Zeilenanfang, antworte als einzige Zeile `ABGELEHNT {auftrag.id}` "
        f"und tu nichts weiter. Sonst antworte als allererste Zeile genau `ACK {auftrag.id}`, "
        f"schreibe die Kopfzeile `Übergabebereit: nein · <ISO-Zeit> · <HEAD-Kurzform>` in {laufend} "
        f"und halte die Datei wie der Claude-Master aktuell. Lies {laufend}; maßgeblich ist allein "
        f"der dort genannte Plan. Das Paket {paket.as_posix()} enthält nur Git-Metadaten. Arbeite "
        f"den nächsten offenen Schritt möglichst autonom weiter und prüfe {master_datei} vor jedem "
        f"weiteren Schritt erneut — steht dort nicht mehr `codex {auftrag.id}`, hör auf. "
        f"Grenzen aus AGENTS.md gelten unverändert."
    )


def _sende_eintrag(auftrag: Auftrag, zeit: str) -> bool:
    """Phase `sende` dauerhaft setzen; False, wenn die Kennung schon existiert (egal welche Phase)."""
    angelegt = []

    def aenderung(alt: list[vorgaenge.Vorgang]) -> list[vorgaenge.Vorgang]:
        if any(v.id == auftrag.id for v in alt):
            return alt
        angelegt.append(True)
        return [*alt, vorgaenge.Vorgang(auftrag.id, auftrag.thema, auftrag.lauf_id, "sende", zeit)]

    vorgaenge.aendern(aenderung)
    return bool(angelegt)


def _phase_setzen(auftrag: Auftrag, zeit: str, phase: str, fehler: str | None = None) -> None:
    def aenderung(alt: list[vorgaenge.Vorgang]) -> list[vorgaenge.Vorgang]:
        return [replace(v, phase=phase, zeit=zeit, fehler=fehler) if v.id == auftrag.id else v for v in alt]

    vorgaenge.aendern(aenderung)


def _zuruecksetzen(master_pfad: Path, auftrag: Auftrag, zeit: str) -> None:
    """Besitz **nur** zurückgeben, wenn dort weiterhin genau der eigene Codex-Besitz steht."""
    text = besitz.lesen(master_pfad)
    teile = text.split()
    if besitz.besitzer(text) == besitz.CODEX and len(teile) > 1 and teile[1] == auftrag.id:
        besitz.schreiben(master_pfad, besitz.zeile(besitz.CLAUDE, zeit, "fehlgeschlagen", auftrag.id))


def senden(auftrag: Auftrag, repo: Path, master_pfad: Path, reservierung: str,
           jetzt: datetime, *, transport: Transport | None = None, git=None,
           timeout: int = TIMEOUT_SEKUNDEN) -> Ergebnis:
    """Den Auftrag senden; gibt die erreichte Phase zurück (siehe Modulbeschreibung)."""
    zeit = jetzt.isoformat()
    if not _sende_eintrag(auftrag, zeit):
        return Ergebnis("doppelt", None, f"Vorgang {auftrag.id} existiert bereits")

    try:
        paket = uebergabe.paket_bauen("claude", "codex", auftrag.laufend, repo=repo, jetzt=jetzt,
                                      git=git, plaene=False, minimal=True)
    except uebergabe.UebergabeFehler as fehler:
        # Paketfehler liegt vor jedem Transport – sicher auflösbar.
        _phase_setzen(auftrag, zeit, "fehler", str(fehler))
        besitz.vergleiche_und_schreibe(master_pfad, reservierung,
                                       besitz.zeile(besitz.CLAUDE, zeit, "fehlgeschlagen", auftrag.id))
        return Ergebnis("fehler", None, str(fehler))

    if not besitz.vergleiche_und_schreibe(master_pfad, reservierung,
                                          besitz.zeile(besitz.CODEX, auftrag.id, zeit)):
        # Fremder Schreiber war schneller: kein Versand, Vorgang als sicher-nicht-gesendet schließen.
        _phase_setzen(auftrag, zeit, "fehler", "Besitzmarke zwischenzeitlich geändert")
        return Ergebnis("fehler", paket, "Besitzmarke zwischenzeitlich geändert")

    liste = [programm() or "codex.exe", QUEUE, "--thread", auftrag.codex_thread,
             "--message", prompt(auftrag, repo, paket)]
    try:
        rc = (transport or _transport)(liste, timeout)
    except START_FEHLER as fehler:
        # Nachweislich nicht gestartet (kein Kindprozess) – nur der eigene Besitz wird zurückgesetzt.
        _phase_setzen(auftrag, zeit, "fehler", f"Transport nicht gestartet: {fehler}")
        _zuruecksetzen(master_pfad, auftrag, zeit)
        return Ergebnis("fehler", paket, f"Transport nicht gestartet: {fehler}")
    except Exception as fehler:  # noqa: BLE001 - alles nach dem Start gilt konservativ als unklar
        _phase_setzen(auftrag, zeit, "unklar", str(fehler))
        return Ergebnis("unklar", paket, str(fehler))

    if rc == 0:
        _phase_setzen(auftrag, zeit, "gesendet")
        return Ergebnis("gesendet", paket, "")
    _phase_setzen(auftrag, zeit, "unklar", f"Rückgabewert {rc}")
    return Ergebnis("unklar", paket, f"Rückgabewert {rc}")
