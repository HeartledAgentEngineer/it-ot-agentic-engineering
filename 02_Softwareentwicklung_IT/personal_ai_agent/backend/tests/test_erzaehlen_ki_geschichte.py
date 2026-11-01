"""Tests für KI-Bildgeschichten (Ich-Form vs. neutrale Erzählersicht)."""
from pathlib import Path
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.router import erzaehlen as erzaehlen_router
from app.services import erzaehl_service as es


def test_format_datum_de():
    assert es.format_datum_de("2018-07-15") == "am 15. Juli 2018"
    assert es.format_datum_de("2018") == "im Jahr 2018"
    assert es.format_datum_de(None) == ""


def test_ki_geschichte_generieren_ich_form():
    res = es.ki_geschichte_generieren(
        fileid="12345",
        perspektive="ich",
        datum="2018-07-15",
        ort="Hamburg",
        personen=["Sebastian", "Matthias"],
        beschreibung="Zwei Freunde lachend am Flussufer.",
        notiz="Das war vor unserem Konzert.",
    )
    assert res["ok"] is True
    assert res["perspektive"] == "ich"
    txt = res["geschichte"]
    assert "Ich erinnere mich" in txt
    assert "Hamburg" in txt
    assert "Matthias" in txt
    assert "Zwei Freunde" in txt or "zwei Freunde" in txt
    assert "Konzert" in txt


def test_ki_geschichte_generieren_erzaehler():
    res = es.ki_geschichte_generieren(
        fileid="12345",
        perspektive="erzaehler",
        datum="2018-07-15",
        ort="Hamburg",
        personen=["Sebastian", "Matthias"],
        beschreibung="Zwei Freunde lachend am Flussufer.",
        notiz="Das war vor unserem Konzert.",
    )
    assert res["ok"] is True
    assert res["perspektive"] == "erzaehler"
    txt = res["geschichte"]
    assert "Eine Aufnahme" in txt
    assert "Sebastian und Matthias" in txt
    assert "Hamburg" in txt
    assert "Konzert" in txt


def test_ki_geschichte_route():
    app = FastAPI()
    app.include_router(erzaehlen_router.router)
    client = TestClient(app)

    r = client.post(
        "/api/erzaehlen/ki-geschichte",
        json={
            "fileid": "999",
            "perspektive": "ich",
            "datum": "2020-05-01",
            "ort": "Berlin",
            "personen": ["Sebastian"],
            "beschreibung": "Ein Spaziergang im Park.",
        },
    )
    assert r.status_code == 200
    daten = r.json()
    assert daten["ok"] is True
    assert "Ich erinnere mich" in daten["geschichte"]
    assert "Berlin" in daten["geschichte"]

def test_anlass_geschichte_generieren_ich():
    res = es.anlass_geschichte_generieren(
        ereignis_kennung="ev_fotobuch",
        titel="Fotobuch Sebastian - Umschlag",
        datum="2026-10-07",
        ort="Wohnzimmer",
        personen=["Matthias Wenck", "Sebastian"],
        anzahl_dateien=1,
        notiz="Das ist das Titelbild meines Fotobuchs mit Papa.",
        perspektive="ich",
    )
    assert res["ok"] is True
    assert res["perspektive"] == "ich"
    txt = res["geschichte"]
    assert "Fotobuch Sebastian" in txt
    assert "am 7. Oktober 2026" in txt
    assert "Wohnzimmer" in txt
    assert "Matthias Wenck" in txt
    assert "Titelbild meines Fotobuchs" in txt


def test_anlass_geschichte_generieren_erzaehler():
    res = es.anlass_geschichte_generieren(
        ereignis_kennung="ev_sommerfest",
        titel="Sommerfest 2025",
        datum="2025-08-15",
        ort="Stadtpark",
        personen=["Matthias", "Sebastian"],
        anzahl_dateien=5,
        notiz="Großes Grillen mit allen.",
        perspektive="erzaehler",
    )
    assert res["ok"] is True
    assert res["perspektive"] == "erzaehler"
    txt = res["geschichte"]
    assert "Fotodokumentation" in txt
    assert "Sommerfest 2025" in txt
    assert "5 Aufnahmen" in txt
    assert "Matthias und Sebastian" in txt


def test_anlass_geschichte_route():
    app = FastAPI()
    app.include_router(erzaehlen_router.router)
    client = TestClient(app)

    r = client.post(
        "/api/erzaehlen/anlass-geschichte",
        json={
            "ereignis_kennung": "ev_test_123",
            "titel": "Urlaub an der Ostsee",
            "datum": "2024-06-20",
            "ort": "Rügen",
            "personen": ["Sebastian"],
            "anzahl_dateien": 3,
            "perspektive": "ich",
        },
    )
    assert r.status_code == 200
    daten = r.json()
    assert daten["ok"] is True
    assert "Urlaub an der Ostsee" in daten["geschichte"]
    assert "Rügen" in daten["geschichte"]

def test_anlass_geschichte_bildanalyse_und_keine_zitate():
    res = es.anlass_geschichte_generieren(
        ereignis_kennung="ev_fotobuch_test",
        titel="Fotobuch Sebastian - Umschlag",
        datum="2026-10-07",
        ort="Wohnzimmer",
        personen=["Matthias Wenck", "Sebastian"],
        anzahl_dateien=1,
        beschreibungen=["An adult lies down indoors playing with a small baby lying beside them."],
        notiz="Das ist das Titelbild meines Fotobuchs mit Papa.",
        perspektive="ich",
    )
    assert res["ok"] is True
    txt = res["geschichte"]
    # 1. Bildanalyse eingearbeitet (deutsch)
    assert "Ein Erwachsener liegt drinnen und spielt mit einem kleinen Baby" in txt
    # 2. Notiz inhaltlich übernommen, NICHT zitiert
    assert "Das ist das Titelbild meines Fotobuchs mit Papa" in txt
    assert "Meine Notiz dazu:" not in txt
    assert "„Das ist das Titelbild" not in txt
