"""Alltagsprotokoll: API für Schlafnächte (03.11.2026). Daten erfunden."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.router import alltag


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ALLTAGSPROTOKOLL_PFAD", str(tmp_path / "eintraege.jsonl"))
    app = FastAPI()
    app.include_router(alltag.router)
    return TestClient(app)


NACHT = {
    "quelle_kennung": "hc-9",
    "beginn": "2026-11-02T23:00:00+01:00",
    "ende": "2026-11-03T06:30:00+01:00",
    "phasen": [{"stufe": "tief", "beginn": "2026-11-02T23:00:00+01:00", "ende": "2026-11-03T06:30:00+01:00"}],
}


def test_schlaf_uebernehmen_und_lesen(client):
    r = client.post("/api/alltag/schlaf", json={"naechte": [NACHT]})
    assert r.status_code == 200 and r.json()["neu"] == 1
    r = client.get("/api/alltag/schlaf", params={"von": "2026-11-01", "bis": "2026-11-05"})
    daten = r.json()
    assert daten["ok"] and daten["naechte"][0]["nacht_zum"] == "2026-11-03"
    assert daten["naechte"][0]["tief_min"] == 450
    assert daten["zusammenfassung"]["naechte"] == 1
    assert "Nacht zum 03.11.2026" in daten["text"]


def test_zweimal_senden_bleibt_eine_nacht(client):
    client.post("/api/alltag/schlaf", json={"naechte": [NACHT]})
    r = client.post("/api/alltag/schlaf", json={"naechte": [NACHT]})
    assert r.json()["unveraendert"] == 1


def test_falscher_koerper_ist_400(client):
    assert client.post("/api/alltag/schlaf", json={"naechte": "x"}).status_code == 400
    assert client.post("/api/alltag/schlaf", content=b"kein json",
                       headers={"content-type": "application/json"}).status_code == 400


def test_stand_nennt_letzte_uebernahme(client):
    assert client.get("/api/alltag/schlaf/stand").json()["anzahl"] == 0
    client.post("/api/alltag/schlaf", json={"naechte": [NACHT]})
    stand = client.get("/api/alltag/schlaf/stand").json()
    assert stand["anzahl"] == 1 and stand["letzte_nacht_zum"] == "2026-11-03" and stand["letzter_abgleich"]


def test_ohne_zeitraum_letzte_14_tage(client):
    r = client.get("/api/alltag/schlaf")
    assert r.status_code == 200 and r.json()["ok"]


def test_main_haengt_router_hinter_die_anmeldung():
    from app import main
    from app.router import auth
    pfade = {}
    for route in main.app.routes:
        if getattr(route, "path", "").startswith("/api/alltag/schlaf"):
            pfade[route.path] = [d.call for d in route.dependant.dependencies]
    assert "/api/alltag/schlaf" in pfade
    assert all(auth.require_api_key in deps for deps in pfade.values())
