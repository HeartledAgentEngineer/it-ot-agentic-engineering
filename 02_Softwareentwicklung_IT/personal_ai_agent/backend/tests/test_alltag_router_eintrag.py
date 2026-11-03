"""Alltagsprotokoll S5, Teil 2 (03.11.2026): ``POST /api/alltag/eintrag`` — Satz → Struktur → gespeichert.

Plan S5 „Fertig": Router-Tests mit Attrappe; ohne Schlüssel ehrliche Meldung, nichts gespeichert,
was nicht strukturiert ist (Originalworte werden trotzdem gesichert). Alles erfunden, kein Netz.
"""
from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.router import alltag
from app.services import alltag_speicher, alltag_struktur, werkzeuge


class Attrappe:
    def __init__(self, antwort):
        self.antwort = antwort
        self.aufrufe = []

    def chat_completion(self, messages, model, temperature, max_tokens, extra_payload):
        self.aufrufe.append(messages)
        return {"choices": [{"message": {"content": json.dumps(self.antwort)}}], "usage": {"cost": 0.0001}}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ALLTAGSPROTOKOLL_PFAD", str(tmp_path / "eintraege.jsonl"))
    monkeypatch.setattr(werkzeuge, "namen_fuer_maskierung", lambda: ["Testperson Anna"])
    app = FastAPI()
    app.include_router(alltag.router)
    return TestClient(app)


def _modell(monkeypatch, antwort):
    kasten = Attrappe(antwort)
    monkeypatch.setattr(alltag_struktur, "standard_client", lambda: kasten)
    monkeypatch.setattr(alltag_struktur, "_schluessel", lambda: "test-schluessel")
    return kasten


def test_satz_wird_strukturiert_und_gespeichert(client, monkeypatch):
    kasten = _modell(monkeypatch, {"art": "stunde", "stimmung": 4, "anspannung": 30,
                                   "gefuehle": ["Ärger"], "vorherrschend": "Ärger",
                                   "aktivitaet": "Wäsche mit [PERSON_01]"})
    r = client.post("/api/alltag/eintrag",
                    json={"text": "Wäsche mit Testperson Anna, gut, Anspannung 30, genervt", "quelle": "sprache"})
    daten = r.json()
    assert r.status_code == 200 and daten["ok"] is True, daten
    assert daten["fehlt"] == []
    assert "Testperson" not in json.dumps(kasten.aufrufe, ensure_ascii=False)
    gespeichert = alltag_speicher.eintraege(art="stunde")
    assert len(gespeichert) == 1 and gespeichert[0]["id"] == daten["eintrag"]["id"]
    assert gespeichert[0]["aktivitaet"] == "Wäsche mit Testperson Anna"
    assert gespeichert[0]["quelle"] == "sprache"


def test_schlaf_satz(client, monkeypatch):
    _modell(monkeypatch, {"art": "schlaf", "ereignis": "schlafen"})
    daten = client.post("/api/alltag/eintrag", json={"text": "Ich gehe schlafen"}).json()
    assert daten["ok"] and daten["eintrag"]["ereignis"] == "schlafen"
    assert len(alltag_speicher.eintraege(art="schlaf")) == 1


def test_ohne_schluessel_nur_originalworte(client, monkeypatch):
    monkeypatch.setattr(alltag_struktur, "_schluessel", lambda: "")
    daten = client.post("/api/alltag/eintrag", json={"text": "Gelesen, mittel", "quelle": "tastatur"}).json()
    assert daten["ok"] is False and "Schlüssel" in daten["grund"]
    e = daten["eintrag"]
    assert e["originalworte"] == "Gelesen, mittel" and e.get("stimmung") is None and e.get("aktivitaet") is None
    assert set(daten["fehlt"]) >= {"stimmung", "anspannung", "gefuehle", "aktivitaet"}
    assert [x["originalworte"] for x in alltag_speicher.eintraege(art="stunde")] == ["Gelesen, mittel"]


def test_ohne_namensliste_kein_modellaufruf(client, monkeypatch):
    kasten = _modell(monkeypatch, {"art": "stunde"})
    monkeypatch.setattr(werkzeuge, "namen_fuer_maskierung", lambda: None)
    daten = client.post("/api/alltag/eintrag", json={"text": "Kaffee getrunken"}).json()
    assert kasten.aufrufe == []
    assert daten["ok"] is False and "Namensliste" in daten["grund"]
    assert daten["eintrag"]["originalworte"] == "Kaffee getrunken"


def test_unbrauchbare_antwort_sichert_originalworte(client, monkeypatch):
    _modell(monkeypatch, {"art": "essen"})
    daten = client.post("/api/alltag/eintrag", json={"text": "Nudeln gegessen"}).json()
    assert daten["ok"] is False and daten["eintrag"]["originalworte"] == "Nudeln gegessen"


def test_namen_fuer_maskierung_behaelt_umlaute(monkeypatch):
    monkeypatch.setattr(werkzeuge, "_personen_namen_streng", lambda: ["Jürgen Testmüller", None, " "])
    monkeypatch.setattr(werkzeuge, "_kontakt_namen", lambda: ["Jürgen Testmüller", "Zoë Probe"])
    assert werkzeuge.namen_fuer_maskierung() == ["Jürgen Testmüller", "Zoë Probe"]


def test_namen_fuer_maskierung_sperrt_bei_fehler_und_leere(monkeypatch):
    def kaputt():
        raise ValueError("kaputt")
    monkeypatch.setattr(werkzeuge, "_kontakt_namen", lambda: [])
    monkeypatch.setattr(werkzeuge, "_personen_namen_streng", lambda: [])
    assert werkzeuge.namen_fuer_maskierung() is None
    monkeypatch.setattr(werkzeuge, "_personen_namen_streng", kaputt)
    assert werkzeuge.namen_fuer_maskierung() is None


def test_leerer_text_ist_400_und_speichert_nichts(client):
    assert client.post("/api/alltag/eintrag", json={"text": "  "}).status_code == 400
    assert client.post("/api/alltag/eintrag", json=["liste"]).status_code == 400
    assert alltag_speicher.eintraege() == []
