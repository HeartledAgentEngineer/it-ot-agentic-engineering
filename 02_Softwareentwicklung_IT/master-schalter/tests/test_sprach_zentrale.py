"""Tests für die Sprachzentrale (`sprach_zentrale.py`)."""
from __future__ import annotations

from pathlib import Path
import pytest

from master_schalter import kosten_budget, paare, sprach_zentrale, ziele

THEMA = "orbitdesk"


@pytest.fixture
def umgebung(tmp_path, monkeypatch):
    daten = tmp_path / "daten"
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(daten))
    monkeypatch.setenv("MASTER_SCHALTER_REPO", str(repo))
    paare.setzen(THEMA, "019a2de5-bb88-71d2-8522-91ba62a9f4b2", paare.laufend_bilden(THEMA), aktiv=True)
    return repo


def test_was_laeuft_wo_mit_aktivem_goal(umgebung):
    ziele.goal_anlegen_oder_aktualisieren(
        THEMA,
        titel="OrbitDesk Ausbau",
        zieltext="Test",
        laufende_arbeit="Implementiert Sprachadapter",
        naechster_schritt="Gesamtabnahme",
    )
    ansage = sprach_zentrale.was_laeuft_wo()
    assert "orbitdesk" in ansage
    assert "Implementiert Sprachadapter" in ansage
    assert "Gesamtabnahme" in ansage


def test_offene_pruefungen_und_blocker(umgebung):
    ziele.goal_anlegen_oder_aktualisieren(
        THEMA,
        titel="OrbitDesk",
        zieltext="Test",
        offene_aufgaben=["Prüfbericht erstellen", "Codex Gegenprüfung"],
        wartegrung="Wartet auf Codex-Freigabe",
    )
    ansage = sprach_zentrale.offene_pruefungen_und_blocker()
    assert "Wartet auf Codex-Freigabe" in ansage
    assert "2 Aufgaben oder Prüfungen" in ansage


def test_fragen_an_sebastian_bei_budget_warnung(umgebung):
    kosten_budget.budget_limit_setzen(THEMA, limit_usd=1.00)
    # Budget überschreiten
    try:
        kosten_budget.verbrauch_buchen(THEMA, modell="gpt-6-luna", input_tokens=2_500_000, output_tokens=0)
    except Exception:
        pass
    # Manuell auf Warnschwelle setzen
    kosten_budget.budget_limit_setzen(THEMA, limit_usd=0.10)

    ansage = sprach_zentrale.fragen_an_sebastian()
    assert "Sebastian" in ansage


def test_thema_ansage_einzeln(umgebung):
    ziele.goal_anlegen_oder_aktualisieren(
        THEMA,
        titel="OrbitDesk Leitwarte",
        zieltext="Steuerung",
        laufende_arbeit="Schritt 5 aktiv",
        naechster_schritt="Endtest",
    )
    ansage = sprach_zentrale.thema_ansage(THEMA)
    assert "Projekt orbitdesk" in ansage
    assert "Schritt 5 aktiv" in ansage
    assert "Endtest" in ansage
