"""Tests für KI-Bildgeschichten (Ich-Form vs. neutrale Erzählersicht).

Seit G1 (02.11.2026) sammelt das Backend die Notizen selbst
(``erzaehl_service.eigene_notizen``); ein übergebenes ``notiz`` ist keine Quelle
mehr. Die Tests legen ihre Notizen deshalb als Zeilen in eine
``geschichten.jsonl`` in ``tmp_path`` (erfundene Daten, kein echter Ordner).
"""
import json
from pathlib import Path
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.router import erzaehlen as erzaehlen_router
from app.services import erzaehl_service as es


@pytest.fixture(autouse=True)
def _geschichten_in_tmp(tmp_path, monkeypatch):
    """Nie die echte ``~/foto_sortierung/geschichten.jsonl`` lesen."""
    ziel = tmp_path / "geschichten.jsonl"
    monkeypatch.setenv("ERZAEHL_GESCHICHTEN_PFAD", str(ziel))
    monkeypatch.setenv("ERZAEHL_EREIGNISSE_PFAD", str(tmp_path / "ereignisse.jsonl"))
    return ziel


def _notiz_ablegen(pfad, text, ereignis_kennung, datei_kennung=None, nr=1):
    zeile = {
        "id": f"n{nr}", "zeit": f"2026-11-0{nr}T10:00:00", "schicht": "mensch",
        "ereignis_kennung": ereignis_kennung, "datei_kennung": datei_kennung,
        "text": text, "quelle": "tippen", "ersetzt": None,
    }
    with open(pfad, "a", encoding="utf-8") as datei:
        datei.write(json.dumps(zeile, ensure_ascii=False) + "\n")


def test_format_datum_de():
    assert es.format_datum_de("2018-07-15") == "am 15. Juli 2018"
    assert es.format_datum_de("2018") == "im Jahr 2018"
    assert es.format_datum_de(None) == ""


def test_ki_geschichte_generieren_ich_form(_geschichten_in_tmp):
    _notiz_ablegen(_geschichten_in_tmp, "Das war vor unserem Konzert.", "E-x", 12345)
    res = es.ki_geschichte_generieren(
        fileid="12345",
        perspektive="ich",
        ereignis_kennung="E-x",
        datum="2018-07-15",
        ort="Hamburg",
        personen=["Sebastian", "Matthias"],
        beschreibung="Zwei Freunde lachend am Flussufer.",
    )
    assert res["ok"] is True
    assert res["perspektive"] == "ich"
    txt = res["geschichte"]
    assert "Ich erinnere mich" in txt
    assert "Hamburg" in txt
    assert "Matthias" in txt
    assert "Zwei Freunde" in txt or "zwei Freunde" in txt
    assert "Konzert" in txt


def test_ki_geschichte_generieren_erzaehler(_geschichten_in_tmp):
    _notiz_ablegen(_geschichten_in_tmp, "Das war vor unserem Konzert.", "E-x", 12345)
    res = es.ki_geschichte_generieren(
        fileid="12345",
        perspektive="erzaehler",
        ereignis_kennung="E-x",
        datum="2018-07-15",
        ort="Hamburg",
        personen=["Sebastian", "Matthias"],
        beschreibung="Zwei Freunde lachend am Flussufer.",
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

def test_anlass_geschichte_generieren_ich(_geschichten_in_tmp):
    _notiz_ablegen(_geschichten_in_tmp, "Das ist das Titelbild meines Fotobuchs mit Papa.", "ev_fotobuch")
    res = es.anlass_geschichte_generieren(
        ereignis_kennung="ev_fotobuch",
        titel="Fotobuch Sebastian - Umschlag",
        datum="2026-10-07",
        ort="Wohnzimmer",
        personen=["Matthias Wenck", "Sebastian"],
        anzahl_dateien=1,
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


def test_anlass_geschichte_generieren_erzaehler(_geschichten_in_tmp):
    _notiz_ablegen(_geschichten_in_tmp, "Großes Grillen mit allen.", "ev_sommerfest")
    res = es.anlass_geschichte_generieren(
        ereignis_kennung="ev_sommerfest",
        titel="Sommerfest 2025",
        datum="2025-08-15",
        ort="Stadtpark",
        personen=["Matthias", "Sebastian"],
        anzahl_dateien=5,
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

def test_anlass_geschichte_bildanalyse_und_keine_zitate(_geschichten_in_tmp):
    _notiz_ablegen(_geschichten_in_tmp, "Das ist das Titelbild meines Fotobuchs mit Papa.", "ev_fotobuch_test")
    res = es.anlass_geschichte_generieren(
        ereignis_kennung="ev_fotobuch_test",
        titel="Fotobuch Sebastian - Umschlag",
        datum="2026-10-07",
        ort="Wohnzimmer",
        personen=["Matthias Wenck", "Sebastian"],
        anzahl_dateien=1,
        beschreibungen=["An adult lies down indoors playing with a small baby lying beside them."],
        perspektive="ich",
    )
    assert res["ok"] is True
    txt = res["geschichte"]
    # 1. Bildanalyse eingearbeitet (deutsch)
    assert "Mein Papa liegt drinnen und spielt mit mir als kleinem Baby" in txt
    # 2. Notiz inhaltlich übernommen, NICHT zitiert
    assert "Das ist das Titelbild meines Fotobuchs mit Papa" in txt
    assert "Meine Notiz dazu:" not in txt
    assert "„Das ist das Titelbild" not in txt
