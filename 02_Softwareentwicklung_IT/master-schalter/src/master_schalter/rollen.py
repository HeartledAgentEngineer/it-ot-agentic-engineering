"""Lage der Kaskaden-Matrix und Rollenbesetzung.

Maßgeblich ist allein die Tabelle in `AGENTS.md` („Rollen und Datenschutz im Agenten-Workflow").
`BESETZUNG` übernimmt deren Zellen wörtlich; ein Test vergleicht sie mit der Datei.
"""
from __future__ import annotations

from dataclasses import dataclass

from .signale import Kontingent

FREI, LIMIT, UNBEKANNT = "frei", "limit", "unbekannt"


@dataclass(frozen=True)
class Besetzung:
    name: str       # erste Spalte ohne Nummer, z. B. „Beide Abos frei (0 € extra)"
    thinker: str
    reviewer: str
    worker: str


BESETZUNG: dict[str, Besetzung] = {
    "1": Besetzung("Beide Abos frei (0 € extra)",
                   "Claude Opus 5.5 (Claude Pro)",
                   "GPT-6 Sol (ChatGPT Plus / Codex)",
                   "GPT-6 Luna / Claude Sonnet 5.5 (Abos)"),
    "2A": Besetzung("Claude im Limit",
                    "GPT-6 Sol (ChatGPT Plus / Codex)",
                    "DeepSeek V4.1 Flash (OpenRouter)",
                    "GPT-6 Luna (ChatGPT Plus)"),
    "2B": Besetzung("ChatGPT im Limit",
                    "Claude Opus 5.5 (Claude Pro)",
                    "DeepSeek V4.1 Flash (OpenRouter)",
                    "Claude Sonnet 5.5 (Claude Pro) / DeepSeek V4.1 Flash (OpenRouter)"),
    "3": Besetzung("Beide im Limit",
                   "DeepSeek V4.1 Flash (OpenRouter/Hermes)",
                   "DeepSeek V4.1 Flash (OpenRouter)",
                   "DeepSeek V4.1 Flash (OpenRouter)"),
}


def besetzung(lage: str | None) -> Besetzung | None:
    return BESETZUNG.get(lage) if lage else None


def _bewerten(k: Kontingent, schwelle: int) -> tuple[str, list[str]]:
    """Zustand eines Abos: (frei | limit | unbekannt, Gründe für „unbekannt").

    Im Limit: ein gemessenes Fenster (Wert vorhanden, Reset nicht vorbei) liegt bei oder über der
    Schwelle. Frei: beide Fenster gemessen und darunter. Alles andere ist unbekannt –
    ein abgelaufenes (`zurueckgesetzt`) oder fehlendes Fenster zählt nie als 0 %; ein gemessenes
    0 % ohne geplante Rücksetzzeit (Fenster nicht aktiv) zählt als frei.
    """
    if k.fehler:
        return UNBEKANNT, [f"{k.master} {k.fehler}"]
    gruende: list[str] = []
    im_limit = False
    for name in ("5h", "Woche"):
        f = k.fenster_nach_name(name)
        if f is None or f.prozent is None:
            gruende.append(f"{k.master} {name} nicht gemessen")
        elif f.zurueckgesetzt:
            gruende.append(f"{k.master} {name} nach Reset noch nicht neu gemessen")
        elif f.reset is None:
            if f.prozent == 0:
                # Gemessene 0 % ohne geplante Rücksetzzeit (Fenster nicht aktiv, API-Form 16.10.2026):
                # zählt als frei; nur fehlende Rücksetzzeit MIT Verbrauch bleibt unbekannt.
                continue
            gruende.append(f"{k.master} {name} ohne gültige Rücksetzzeit")
        elif f.prozent >= schwelle:
            im_limit = True
    if im_limit:
        return LIMIT, []
    return (UNBEKANNT, gruende) if gruende else (FREI, [])


def lage(claude: Kontingent, codex: Kontingent, schwelle: int) -> str | None:
    """„1" | „2A" | „2B" | „3" oder None, wenn ein Abo unbekannt ist (keine Rate)."""
    c, x = _bewerten(claude, schwelle)[0], _bewerten(codex, schwelle)[0]
    return {(FREI, FREI): "1", (LIMIT, FREI): "2A", (FREI, LIMIT): "2B", (LIMIT, LIMIT): "3"}.get((c, x))


def lage_grund(claude: Kontingent, codex: Kontingent, schwelle: int) -> str:
    """Warum die Lage unbekannt ist; leer, wenn sie bekannt ist."""
    gruende = _bewerten(claude, schwelle)[1] + _bewerten(codex, schwelle)[1]
    return "; ".join(gruende)
