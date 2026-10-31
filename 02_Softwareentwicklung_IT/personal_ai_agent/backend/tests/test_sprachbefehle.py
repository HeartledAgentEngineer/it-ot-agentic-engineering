"""
Unit-Tests fuer sprachbefehl_service.py: Natuerliche Sprachsteuerung & App-Aktionen.
"""

import pytest
from app.services.sprachbefehl_service import analysiere_sprachbefehl


def test_quiz_oeffnen():
    res = analysiere_sprachbefehl("Öffne das Quiz")
    assert res["ist_befehl"] is True
    assert res["aktion"] == "quiz_oeffnen"
    assert "Quiz" in res["antwort"]


def test_erzaehlmodus_oeffnen():
    res = analysiere_sprachbefehl("öffne den Erzählmodus")
    assert res["ist_befehl"] is True
    assert res["aktion"] == "erzaehlen_oeffnen"
    assert "Erzählmodus" in res["antwort"]


def test_blaettern_fuenf_seiten():
    res = analysiere_sprachbefehl("gehe mal fünf Seiten weiter")
    assert res["ist_befehl"] is True
    assert res["aktion"] == "blaettern"
    assert res["parameter"]["richtung"] == "vor"
    assert res["parameter"]["anzahl"] == 5


def test_blaettern_drei_zurueck():
    res = analysiere_sprachbefehl("gehe drei Bilder zurück")
    assert res["ist_befehl"] is True
    assert res["aktion"] == "blaettern"
    assert res["parameter"]["richtung"] == "zurueck"
    assert res["parameter"]["anzahl"] == 3


def test_mehrschritt_event_und_bild_oeffnen():
    # Sebastians genaue Formulierung:
    # "öffne das oberste Event oder den obersten Anlass und zeig mir das erste Bild"
    res = analysiere_sprachbefehl("öffne das oberste Event oder den obersten Anlass und zeig mir das erste Bild")
    assert res["ist_befehl"] is True
    assert len(res["aktionen"]) == 2
    assert res["aktionen"][0]["aktion"] == "event_oeffnen"
    assert res["aktionen"][0]["parameter"]["index"] == 0
    assert res["aktionen"][1]["aktion"] == "bild_oeffnen"
    assert res["aktionen"][1]["parameter"]["index"] == 0


def test_notizen_hinzufuegen():
    res = analysiere_sprachbefehl("Notizen hinzufügen Das war ein wunderschöner Tag am See")
    assert res["ist_befehl"] is True
    assert res["aktion"] == "notiz_hinzufuegen"
    assert "Das war ein wunderschöner Tag am See" in res["parameter"]["text"]


def test_geschichte_erzaehlen():
    res = analysiere_sprachbefehl("Erzähl mir von da jetzt die Geschichte")
    assert res["ist_befehl"] is True
    assert res["aktion"] == "geschichte_erzaehlen"


def test_neu_vorsortieren():
    res = analysiere_sprachbefehl("Neu vorsortieren")
    assert res["ist_befehl"] is True
    assert res["aktion"] == "neu_vorsortieren"


def test_speichern():
    res = analysiere_sprachbefehl("bitte speichern!")
    assert res["ist_befehl"] is True
    assert res["aktion"] == "speichern"


def test_allgemeine_frage_ist_kein_befehl():
    res = analysiere_sprachbefehl("Wer ist auf diesem Bild alles zu sehen?")
    assert res["ist_befehl"] is False
    assert res["aktion"] is None
