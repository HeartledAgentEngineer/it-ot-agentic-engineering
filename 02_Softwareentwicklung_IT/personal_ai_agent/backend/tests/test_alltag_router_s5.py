"""Alltagsprotokoll S5, Teil ohne Sprachmodell (03.11.2026): offen, Tag, korrigieren, löschen.

``POST /api/alltag/eintrag`` (Text → Struktur) braucht S3 und folgt dort. Daten erfunden.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.router import alltag
from app.services import alltag_speicher


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ALLTAGSPROTOKOLL_PFAD", str(tmp_path / "eintraege.jsonl"))
    app = FastAPI()
    app.include_router(alltag.router)
    return TestClient(app)


def _iso(zeit: datetime) -> str:
    return zeit.isoformat(timespec="seconds")


def _stunde(von, bis, **felder):
    r = alltag_speicher.eintrag_anhaengen({"art": "stunde", "von": von, "bis": bis, **felder})
    assert r["ok"], r
    return r["eintrag"]


def test_offen_ohne_eintraege(client):
    assert client.get("/api/alltag/offen").json() == {
        "ok": True, "offene_stunden": 1, "schlaeft": False, "letzter_eintrag": None}


def test_offen_zaehlt_volle_stunden_seit_dem_letzten_eintrag(client):
    jetzt = datetime.now().astimezone()
    bis = _iso(jetzt - timedelta(hours=3, minutes=10))
    _stunde(_iso(jetzt - timedelta(hours=4, minutes=10)), bis, stimmung=3)
    daten = client.get("/api/alltag/offen").json()
    assert daten == {"ok": True, "offene_stunden": 3, "schlaeft": False, "letzter_eintrag": bis}


def test_offen_im_schlaf_still(client):
    jetzt = datetime.now().astimezone()
    alltag_speicher.eintrag_anhaengen({"art": "schlaf", "ereignis": "schlafen",
                                       "zeit": _iso(jetzt - timedelta(hours=5))})
    daten = client.get("/api/alltag/offen").json()
    assert daten["schlaeft"] is True and daten["offene_stunden"] == 0


def test_tag_mit_luecken_und_uhrnacht(client):
    _stunde("2026-11-03T09:00:00+01:00", "2026-11-03T10:00:00+01:00",
            stimmung=4, anspannung=20, gefuehle=["Ruhe"], aktivitaet="Frühstück")
    _stunde("2026-11-03T10:00:00+01:00", "2026-11-03T11:00:00+01:00", aktivitaet="Lesen")
    _stunde("2026-11-04T10:00:00+01:00", "2026-11-04T11:00:00+01:00", aktivitaet="anderer Tag")
    alltag_speicher.eintrag_anhaengen({"art": "schlaf", "ereignis": "aufwachen",
                                       "zeit": "2026-11-03T07:00:00+01:00"})
    alltag_speicher.schlafnaechte_uebernehmen([{
        "quelle_kennung": "hc-1", "beginn": "2026-11-02T23:00:00+01:00",
        "ende": "2026-11-03T06:50:00+01:00", "phasen": []}])
    daten = client.get("/api/alltag/tag", params={"datum": "2026-11-03"}).json()
    assert daten["ok"] and daten["datum"] == "2026-11-03"
    arten = [(e["art"], e.get("aktivitaet") or e.get("ereignis")) for e in daten["eintraege"]]
    assert arten == [("schlaf", "aufwachen"), ("stunde", "Frühstück"), ("stunde", "Lesen")]
    assert [e["fehlt"] for e in daten["eintraege"]] == [[], [], ["stimmung", "anspannung", "gefuehle"]]
    assert [n["nacht_zum"] for n in daten["naechte_uhr"]] == ["2026-11-03"]


def test_tag_braucht_ein_datum(client):
    assert client.get("/api/alltag/tag", params={"datum": "3.11."}).status_code == 400


def test_korrigieren_und_loeschen(client):
    alt = _stunde("2026-11-03T09:00:00+01:00", "2026-11-03T10:00:00+01:00", stimmung=2)
    r = client.patch(f"/api/alltag/eintrag/{alt['id']}", json={"stimmung": 4, "unbekannt": "weg"})
    assert r.status_code == 200
    neu = r.json()["eintrag"]
    assert neu["stimmung"] == 4 and neu["ersetzt"] == alt["id"] and "unbekannt" not in neu
    assert client.delete(f"/api/alltag/eintrag/{neu['id']}").json() == {"ok": True}
    tag = client.get("/api/alltag/tag", params={"datum": "2026-11-03"}).json()
    assert tag["eintraege"] == []


def test_unbekannter_eintrag_ist_404(client):
    assert client.patch("/api/alltag/eintrag/gibtsnicht", json={"stimmung": 1}).status_code == 404
    assert client.delete("/api/alltag/eintrag/gibtsnicht").status_code == 404
    assert client.patch("/api/alltag/eintrag/x", content=b"kein json",
                        headers={"content-type": "application/json"}).status_code == 400
