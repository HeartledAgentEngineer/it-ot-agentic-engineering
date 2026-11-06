"""Sprachsteuerungs- und Abfrage-Zentrale für OrbitDesk („Telefonagent“ / Voice-Rolls-Mode).

Formatiert den aktuellen Leitwarten-Status in flüssige, prägnante Sprachantworten (TTS-optimiert):
- `was_laeuft_wo()`: Aktuelle Worker, laufende Arbeit und nächste Schritte über alle Projekte.
- `offene_pruefungen_und_blocker()`: Anstehende Prüfungen, offene Abnahmen und Wartegründe.
- `fragen_an_sebastian()`: Ungeklärte Entscheidungen oder Punkte, die Sebastians Eingriff erfordern.
- `thema_ansage(thema)`: Kompakte Sprachzusammenfassung für ein einzelnes Projekt.
"""
from __future__ import annotations

from typing import Any

from . import kosten_budget, modi, paare, ziele


def was_laeuft_wo() -> str:
    """Sprachausgabe für 'Was geht gerade wo? / Was läuft wo?'."""
    themen = paare.lesen()
    if not themen:
        return "Aktuell sind keine Coding-Projekte im Master-Schalter eingerichtet."

    saetze = []
    for p in themen:
        profil = modi.profil(p.thema)
        ziel = ziele.goal_lesen(p.thema)
        master = profil.master.upper()
        if master == "AGY":
            master = "Antigravity"
        elif master == "CODEX":
            master = "Codex"
        elif master == "HERMES":
            master = "Hermes"
        elif master == "CLAUDE":
            master = "Claude Code"

        arbeit = ziel.laufende_arbeit if (ziel and ziel.laufende_arbeit) else "Keine aktive Arbeit gemeldet."
        naechster = f" Als Nächstes geplant: {ziel.naechster_schritt}." if (ziel and ziel.naechster_schritt) else ""
        warte = f" Achtung: {ziel.wartegrung}." if (ziel and ziel.wartegrung) else ""

        saetze.append(f"Im Projekt {p.thema} führt aktuell {master}. {arbeit}{naechster}{warte}")

    return " ".join(saetze)


def offene_pruefungen_und_blocker() -> str:
    """Sprachausgabe für 'Welche Prüfungen stehen an? Wo gibt es Blocker?'."""
    themen = paare.lesen()
    pruefungen = []
    blocker = []

    for p in themen:
        ziel = ziele.goal_lesen(p.thema)
        if ziel:
            if ziel.status == ziele.STATUS_BLOCKIERT or ziel.wartegrung:
                grund = ziel.wartegrung or "Allgemeine Blockade"
                blocker.append(f"In {p.thema}: {grund}.")
            if ziel.offene_aufgaben:
                pruefungen.append(f"In {p.thema} stehen {len(ziel.offene_aufgaben)} Aufgaben oder Prüfungen aus.")

    if not blocker and not pruefungen:
        return "Aktuell stehen keine Prüfungen aus und alle Workflows laufen ohne gemeldete Blocker."

    ergebnis = []
    if blocker:
        ergebnis.append("Es gibt folgende Wartegründe oder Blocker: " + " ".join(blocker))
    if pruefungen:
        ergebnis.append("Anstehende Aufgaben: " + " ".join(pruefungen))

    return " ".join(ergebnis)


def fragen_an_sebastian() -> str:
    """Sprachausgabe für 'Was muss ich entscheiden? Wo gibt es Fragen an mich?'."""
    themen = paare.lesen()
    fragen = []

    for p in themen:
        ziel = ziele.goal_lesen(p.thema)
        kosten = kosten_budget.budget_status_lesen(p.thema)

        if kosten.warnung_aktiv or kosten.stopp_aktiv:
            fragen.append(
                f"Im Projekt {p.thema} wurde die Budgetgrenze von {kosten.budget_limit_usd:.2f} Dollar erreicht. "
                f"Verbraucht sind {kosten.verbraucht_usd:.2f} Dollar. Bitte gib neues Budget frei."
            )

        if ziel and ziel.wartegrung and ("Sebastian" in ziel.wartegrung or "Entscheidung" in ziel.wartegrung):
            fragen.append(f"Im Projekt {p.thema} wartet das Team auf dich: {ziel.wartegrung}.")

    if not fragen:
        return "Sebastian, aktuell sind keine Entscheidungen von dir offen. Alles läuft autonom im grünen Bereich."

    return "Sebastian, hier sind Punkte für dich: " + " ".join(fragen)


def thema_ansage(thema: str) -> str:
    """Kompakte Einzelansage für ein bestimmtes Thema."""
    paare.thema_pruefen(thema)
    profil = modi.profil(thema)
    ziel = ziele.goal_lesen(thema)
    kosten = kosten_budget.budget_status_lesen(thema)

    if ziel is None:
        return (
            f"Im Projekt {thema} führt {profil.master}. Es ist noch kein strukturiertes Goal hinterlegt. "
            f"Kosten bisher: {kosten.verbraucht_usd:.2f} Dollar."
        )

    titel = ziel.titel or thema
    naechster = f" Nächster Schritt: {ziel.naechster_schritt}." if ziel.naechster_schritt else ""
    warte = f" Wartegrund: {ziel.wartegrung}." if ziel.wartegrung else " Status: " + ziel.status + "."
    return (
        f"Projekt {thema}, {titel}. Master ist {profil.master}, Worker ist {profil.worker}. "
        f"{ziel.laufende_arbeit or 'Bereit.'}{naechster}{warte} "
        f"Verbrauchte Kosten: {kosten.verbraucht_usd:.2f} von {kosten.budget_limit_usd:.2f} Dollar."
    )
