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
