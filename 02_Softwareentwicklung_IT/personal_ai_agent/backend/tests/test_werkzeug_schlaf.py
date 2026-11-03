"""Chat-Werkzeug ``schlaf_abfragen`` (03.11.2026): „Wie habe ich geschlafen?". Daten erfunden."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.services import alltag_speicher, werkzeuge


@pytest.fixture(autouse=True)
def _pfad(tmp_path, monkeypatch):
    monkeypatch.setenv("ALLTAGSPROTOKOLL_PFAD", str(tmp_path / "eintraege.jsonl"))


def _nacht_zum(tag: date, kennung: str, stunden: int = 7):
    vorher = tag - timedelta(days=1)
    return {"quelle_kennung": kennung, "beginn": f"{vorher.isoformat()}T23:00:00+01:00",
            "ende": f"{tag.isoformat()}T{stunden - 1:02d}:00:00+01:00", "phasen": []}


def test_werkzeug_ist_registriert_und_ausfuehrbar():
    assert "schlaf_abfragen" in werkzeuge.REGISTER
    assert werkzeuge.pruefe_register() == []


def test_letzte_nacht():
    heute = date.today()
    alltag_speicher.schlafnaechte_uebernehmen([_nacht_zum(heute, "a"), _nacht_zum(heute - timedelta(days=3), "b")])
    erg = werkzeuge.ausfuehren("schlaf_abfragen", {"datum": "heute"})
    assert erg.ok and heute.strftime("%d.%m.%Y") in erg.text
    assert (heute - timedelta(days=3)).strftime("%d.%m.%Y") not in erg.text


def test_letzte_tage_mit_schnitt():
    heute = date.today()
    alltag_speicher.schlafnaechte_uebernehmen([_nacht_zum(heute - timedelta(days=i), f"n{i}") for i in range(3)])
    erg = werkzeuge.ausfuehren("schlaf_abfragen", {"tage": 7})
    assert "Schnitt über 3 Nächte" in erg.text


def test_bestimmtes_datum():
    alltag_speicher.schlafnaechte_uebernehmen([_nacht_zum(date(2026, 10, 5), "x")])
    erg = werkzeuge.ausfuehren("schlaf_abfragen", {"datum": "2026-10-05"})
    assert "05.10.2026" in erg.text


def test_ohne_daten_ehrlicher_hinweis():
    erg = werkzeuge.ausfuehren("schlaf_abfragen", {})
    assert "Keine Schlafdaten" in erg.text


def test_falsches_datum():
    erg = werkzeuge.ausfuehren("schlaf_abfragen", {"datum": "irgendwann"})
    assert erg.ok is False


def test_statuszeile_nennt_den_zeitraum():
    assert "letzte 7 Tage" in werkzeuge.status_text("schlaf_abfragen", {"tage": 7})
