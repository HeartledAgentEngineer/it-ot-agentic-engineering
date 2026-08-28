"""Tests für den Kontext-Service (Ein-Chat: Rolling-Summary + Kontext-Paket)."""
import os
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.services.kontext_service import (  # noqa: E402
    LETZTE_ANZAHL,
    ROLL_AB,
    baue_kontext,
)


def _hist(num):
    """Baut eine Historie mit 'num' Nachrichten."""
    return [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"Nachricht {i}"}
        for i in range(num)
    ]


def test_kurze_historie_keine_summary():
    """Unter der Roll-Schwelle bleibt alles voll, kein Summary."""
    r = baue_kontext(_hist(20), "Frage?", memory_extractor=None)
    assert r["gerollt"] is False
    assert r["summary"] == ""
    assert "[Aktueller Verlauf:]" in r["kontext"]
    assert "Nachricht 19" in r["kontext"]


def test_lange_historie_rollt_summary():
    """Ab der Schwelle + genug neuen Nachrichten wird der Summary gerollt."""
    r = baue_kontext(_hist(100), "Frage?", memory_extractor=None,
                     anzahl_seit_roll=50)
    assert r["gerollt"] is True
    assert "Zusammenfassung" in r["summary"]
    assert "Nachricht 99" in r["kontext"]   # letzte bleiben voll


def test_rate_limit_verhindert_zu_haefiges_rollen():
    """Ohne genug neue Nachrichten seit dem letzten Roll wird nicht neu gerollt."""
    r = baue_kontext(_hist(100), "Frage?", memory_extractor=None,
                     gespeichertes_summary="ALT", anzahl_seit_roll=1)
    assert r["gerollt"] is False
    assert r["summary"] == "ALT"  # bestehender Summary bleibt


def test_erinnerungen_mit_extractor():
    """Mit memory_extractor kommen relevante Erinnerungen in den Kontext."""
    def extractor(frage, top_k):
        return [{"content": "Sebastian arbeitet an AI-Engineering."}]
    r = baue_kontext(_hist(10), "Karriere?", memory_extractor=extractor)
    assert "Erinnerung:" in r["kontext"]
    assert "AI-Engineering" in r["kontext"]


def test_kontext_budget_kappt_laenge():
    """Der Kontext wird grob aufs Token-Budget gekappt (kein Explodieren)."""
    r = baue_kontext(_hist(1000), "Frage?", memory_extractor=None,
                     anzahl_seit_roll=0)
    assert len(r["kontext"]) <= 2000 * 4 + 100  # Budget-Abschätzung
