"""Masterwechsel: Themensperren holen, Übergabepaket bauen, Zustand setzen – in dieser Reihenfolge.

Scheitert eine Themensperre (der Rückwechsel wartet höchstens 5 s), die globale Sperre
(Zeitüberschreitung) oder das Paket, wird nichts am Zustand geändert.
Gemeinsamer Weg für `masterwechsel wechsel` und das Klickmenü der Taskleiste.

Der manuelle Rückwechsel auf Claude nimmt dieselben **Themensperren** wie die Automatik –
vorher blockierend, damit er nicht mit einem laufenden Automatiklauf um dieselbe Besitzdatei
streitet. Offene Vorgänge werden dabei entwertet (verspäteter Auftrag/ACK ändert dann nichts mehr).
"""
from __future__ import annotations

import time
from contextlib import ExitStack
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from . import besitz, paare, uebergabe, vorgaenge, zustand

CLAUDE = "claude"
FRIST_THEMEN_SEKUNDEN = 5.0
MELDUNG_SPERRE = "Übergabe läuft gerade – gleich erneut versuchen"


@dataclass(frozen=True)
class Ergebnis:
    art: str                # "gewechselt" | "gleich" | "fehler"
    master: str             # Ziel-Master ("claude" | "codex" | "hermes")
    paket: Path | None      # nur bei "gewechselt"
    meldung: str            # Fehlertext bei "fehler", sonst leer


def _themen_sperren(stapel: ExitStack, frist: float) -> bool:
    """Alle Themensperren alphabetisch und blockierend holen; eine gemeinsame Zeitgrenze."""
    ende = time.monotonic() + frist
    for thema in sorted({p.thema for p in paare.lesen()}):
        rest = max(0.01, ende - time.monotonic())
        if not stapel.enter_context(zustand.thema_sperre(thema, blockierend=True, frist=rest)):
            return False
    return True


def _entwerten(jetzt: datetime) -> None:
    """Rückwechsel: Besitz je Thema zurück auf `claude`, offene Vorgänge entwertet.

    * Offene Vorgänge (`sende`/`gesendet`/`unklar`) werden auf `entwertet` gesetzt; ihre
      Besitzdatei wird `claude <Zeit> entwertet <ID>` (ein verspätetes ACK ändert nichts mehr).
    * Ein bereits **bestätigter** Vorgang bleibt bestätigt (die Zustellung war echt), seine
      Besitzdatei geht aber auf `claude <Zeit>` zurück – sonst bliebe das Thema für die
      Automatik dauerhaft gesperrt (sie liest dort „Codex hat übernommen").
    """
    vorgangsliste = vorgaenge.lesen()
    if not vorgangsliste:
        return
    try:
        repo = uebergabe.repo_wurzel()
    except uebergabe.UebergabeFehler:
        repo = None
    laufend = {p.thema: p.laufend for p in paare.lesen()}
    zeit = jetzt.isoformat()
    if repo is not None:
        for thema in sorted({v.thema for v in vorgangsliste}):
            if thema not in laufend:
                continue
            offen = [v for v in vorgangsliste if v.thema == thema and v.phase in vorgaenge.OFFEN]
            text = (besitz.zeile(besitz.CLAUDE, zeit, "entwertet",
                                 max(offen, key=lambda v: v.zeit).id)
                    if offen else besitz.zeile(besitz.CLAUDE, zeit))
            besitz.schreiben(besitz.pfad(repo, laufend[thema]), text)
    offene_ids = {v.id for v in vorgangsliste if v.phase in vorgaenge.OFFEN}
    if offene_ids:
        vorgaenge.aendern(lambda alt: [replace(v, phase="entwertet", zeit=zeit) if v.id in offene_ids else v
                                       for v in alt])


def wechseln(nach: str, hinweis: str | None = None, jetzt: datetime | None = None,
             frist: float = zustand.FRIST_SEKUNDEN,
             themen_frist: float = FRIST_THEMEN_SEKUNDEN) -> Ergebnis:
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

    with ExitStack() as stapel:
        if not _themen_sperren(stapel, themen_frist):
            return Ergebnis("fehler", nach, None, MELDUNG_SPERRE)
        if nach == CLAUDE and zustand.lesen().master != CLAUDE:
            _entwerten(jetzt)
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
