"""Chat-Werkzeug ``alltag_abfragen`` (S8, 03.11.2026): „Wie war meine Stimmung?". Daten erfunden."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.services import alltag_speicher, werkzeuge


@pytest.fixture(autouse=True)
def _pfad(tmp_path, monkeypatch):
    monkeypatch.setenv("ALLTAGSPROTOKOLL_PFAD", str(tmp_path / "eintraege.jsonl"))
    monkeypatch.setattr(werkzeuge, "namen_fuer_maskierung", lambda: ["Testperson Erfunden"])


def _stunde(tag: date, aktivitaet: str = "Gelesen", stimmung: int = 4):
    t = tag.isoformat()
    return alltag_speicher.eintrag_anhaengen({
        "art": "stunde", "von": f"{t}T09:00:00+01:00", "bis": f"{t}T10:00:00+01:00",
        "aktivitaet": aktivitaet, "stimmung": stimmung, "anspannung": 30, "quelle": "tastatur",
        "originalworte": "erfundener Originalsatz"})


def test_werkzeug_ist_registriert_und_ausfuehrbar():
    assert "alltag_abfragen" in werkzeuge.REGISTER
    assert werkzeuge.pruefe_register() == []


def test_heute_mit_taetigkeit():
    _stunde(date.today())
    erg = werkzeuge.ausfuehren("alltag_abfragen", {"datum": "heute"})
    assert erg.ok and "Gelesen" in erg.text and "Stimmung gut (4)" in erg.text
    assert "Originalsatz" not in erg.text


def test_namen_bleiben_beim_rechner():
    _stunde(date.today(), aktivitaet="Spaziergang mit Testperson")
    erg = werkzeuge.ausfuehren("alltag_abfragen", {"datum": "heute"})
    assert "Spaziergang mit [Name]" in erg.text and "Testperson" not in erg.text


def test_ohne_namensliste_keine_taetigkeit(monkeypatch):
    monkeypatch.setattr(werkzeuge, "namen_fuer_maskierung", lambda: None)
    _stunde(date.today(), aktivitaet="Spaziergang mit Testperson")
    erg = werkzeuge.ausfuehren("alltag_abfragen", {"datum": "heute"})
    assert erg.ok and "Spaziergang" not in erg.text and "Stimmung gut" in erg.text


def test_zeitraum_mit_tageszeilen_und_verknuepfung():
    heute = date.today()
    for i in range(3):
        _stunde(heute - timedelta(days=i))
    erg = werkzeuge.ausfuehren("alltag_abfragen", {"tage": 7})
    assert "Stimmung im Schnitt 4,0" in erg.text
    assert "Schlaf und Stimmung" in erg.text


def test_beschreibung_nennt_tageszeiten_und_tiefschlaf():
    # S10: Das Modell soll wissen, dass das Werkzeug diese Fragen beantwortet.
    beschreibung = werkzeuge.REGISTER["alltag_abfragen"].beschreibung
    assert "Tageszeit" in beschreibung and "Tiefschlaf" in beschreibung


def test_falsches_datum():
    assert werkzeuge.ausfuehren("alltag_abfragen", {"datum": "irgendwann"}).ok is False


def test_statuszeile_nennt_den_zeitraum():
    assert "letzte 7 Tage" in werkzeuge.status_text("alltag_abfragen", {"tage": 7})
    assert "Tag heute" in werkzeuge.status_text("alltag_abfragen", {"datum": "heute"})
