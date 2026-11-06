"""Tests für Kosten-, Token- und Delegations-Schutz (`kosten_budget.py`)."""
from __future__ import annotations

from pathlib import Path
import pytest

from master_schalter import kosten_budget, paare
from master_schalter.kosten_budget import BudgetFehler, DelegationsPflichtFehler

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


def test_berechne_kosten_usd_sol_vs_luna():
    # 1.000.000 Input Tokens auf Sol = $10.00
    kosten_sol = kosten_budget.berechne_kosten_usd("gpt-6-sol", 1_000_000, 0, 0)
    assert kosten_sol == 10.00

    # 1.000.000 Input Tokens auf Luna = $0.50 (Faktor 20 günstiger!)
    kosten_luna = kosten_budget.berechne_kosten_usd("gpt-6-luna", 1_000_000, 0, 0)
    assert kosten_luna == 0.50

    # DeepSeek Flash = $0.14
    kosten_ds = kosten_budget.berechne_kosten_usd("deepseek-v4.1-flash", 1_000_000, 0, 0)
    assert kosten_ds == 0.14


def test_delegationspflicht_blockiert_sol_bei_dokumentenscan():
    # Routine-Dokumentenscan mit GPT-6 Sol -> DelegationsPflichtFehler!
    with pytest.raises(DelegationsPflichtFehler) as fehler:
        kosten_budget.pruefe_delegationspflicht("gpt-6-sol", aufgabe_art="dokumenten_scan")
    assert "Delegationspflicht verletzt" in str(fehler.value)
    assert "gpt-6-luna" in str(fehler.value)

    # Mit Luna oder DeepSeek ist der Scan problemlos erlaubt
    kosten_budget.pruefe_delegationspflicht("gpt-6-luna", aufgabe_art="dokumenten_scan")
    kosten_budget.pruefe_delegationspflicht("deepseek-v4.1-flash", aufgabe_art="dokumenten_scan")


def test_delegationspflicht_blockiert_sol_bei_grosser_tokenmenge():
    # > 15.000 Tokens mit Sol blockiert
    with pytest.raises(DelegationsPflichtFehler):
        kosten_budget.pruefe_delegationspflicht("gpt-6.1-sol", geschaetzte_input_tokens=20_000)

    # 5.000 Tokens mit Sol (gezielter Thinker-Plan) erlaubt
    kosten_budget.pruefe_delegationspflicht("gpt-6-sol", geschaetzte_input_tokens=5_000)


def test_verbrauch_buchen_und_budgetgrenze(umgebung):
    kosten_budget.budget_limit_setzen(THEMA, limit_usd=2.00, warnschwelle_prozent=75.0)

    # Buchung 1: Luna mit 500k Tokens = $0.25
    e1 = kosten_budget.verbrauch_buchen(
        THEMA, modell="gpt-6-luna", input_tokens=500_000, output_tokens=0, auftrag_id="a-1"
    )
    assert e1.kosten_usd == 0.25

    status1 = kosten_budget.budget_status_lesen(THEMA)
    assert status1.verbraucht_usd == 0.25
    assert status1.verbleibend_usd == 1.75
    assert status1.warnung_aktiv is False
    assert status1.stopp_aktiv is False

    # Buchung 2: Großer Verbrauch nahe ans Limit
    kosten_budget.verbrauch_buchen(
        THEMA, modell="gpt-6-luna", input_tokens=3_000_000, output_tokens=0, auftrag_id="a-2"
    )
    # 3M Tokens Luna = $1.50 -> Gesamt $1.75 / $2.00 = 87.5 % -> Warnung aktiv!
    status2 = kosten_budget.budget_status_lesen(THEMA)
    assert status2.verbraucht_usd == 1.75
    assert status2.warnung_aktiv is True
    assert status2.stopp_aktiv is False

    # Buchung 3: Überschreitet Budget von $2.00 -> Blockiert!
    with pytest.raises(BudgetFehler) as fehler:
        kosten_budget.verbrauch_buchen(
            THEMA, modell="gpt-6-luna", input_tokens=1_000_000, output_tokens=0, auftrag_id="a-3"
        )
    assert "Budgetgrenze für 'orbitdesk' überschritten" in str(fehler.value)
