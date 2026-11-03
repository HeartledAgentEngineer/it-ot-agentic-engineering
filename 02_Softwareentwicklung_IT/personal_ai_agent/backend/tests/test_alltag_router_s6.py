"""Alltagsprotokoll S6, Backend-Teil (03.11.2026): Schnellknöpfe für den Schlaf und Vorgaben.

Die Knöpfe „Ich gehe schlafen" usw. brauchen kein Modell: ``POST /api/alltag/ereignis`` speichert
das Ereignis sofort. ``GET /api/alltag/vorgaben`` liefert Grundgefühle und Stimmungsstufen für
die Rückfragen der Oberfläche. Daten erfunden.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.router import alltag
from app.services import alltag_speicher, alltag_struktur


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ALLTAGSPROTOKOLL_PFAD", str(tmp_path / "eintraege.jsonl"))
    app = FastAPI()
    app.include_router(alltag.router)
    return TestClient(app)


def test_schlaf_knopf_speichert_ohne_modell(client, monkeypatch):
    monkeypatch.setattr(alltag_struktur, "strukturieren", lambda *a, **k: pytest.fail("kein Modell"))
    r = client.post("/api/alltag/ereignis", json={"ereignis": "schlafen"})
    assert r.status_code == 200
    e = r.json()["eintrag"]
    assert e["art"] == "schlaf" and e["ereignis"] == "schlafen" and e["quelle"] == "knopf"
    assert e["zeit"][10] == "T" and e["zeit"][-6] in "+-"            # ISO mit Zeitzone
    assert client.get("/api/alltag/offen").json()["schlaeft"] is True


def test_alle_vier_knoepfe(client):
    for ereignis in ("schlafen", "wach_liegen", "wieder_schlafen", "aufwachen"):
        assert client.post("/api/alltag/ereignis", json={"ereignis": ereignis}).status_code == 200
    assert [e["ereignis"] for e in alltag_speicher.eintraege(art="schlaf")] == [
        "schlafen", "wach_liegen", "wieder_schlafen", "aufwachen"]
    assert client.get("/api/alltag/offen").json()["schlaeft"] is False


def test_unbekanntes_ereignis_ist_400(client):
    assert client.post("/api/alltag/ereignis", json={"ereignis": "tanzen"}).status_code == 400
    assert client.post("/api/alltag/ereignis", json=["schlafen"]).status_code == 400
    assert alltag_speicher.eintraege() == []


def test_vorgaben_fuer_die_rueckfragen(client):
    v = client.get("/api/alltag/vorgaben").json()
    assert v["ok"] and v["grundgefuehle"] == list(alltag_struktur.GRUNDGEFUEHLE)
    assert v["stimmung"] == [{"wert": 5, "wort": "sehr gut"}, {"wert": 4, "wort": "gut"},
                             {"wert": 3, "wort": "mittel"}, {"wert": 2, "wort": "schlecht"},
                             {"wert": 1, "wort": "sehr schlecht"}]
