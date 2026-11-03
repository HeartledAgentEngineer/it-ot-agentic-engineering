"""Alltagsprotokoll S14: Wochenübersicht (03.11.2026). Nur erfundene Einträge, Plan .hermes/plans/alltag-s14-woche.md."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.router import alltag
from app.services import alltag_auswertung as aw
from app.services import alltag_speicher


def _stunde(tag, von="10:00", bis="11:00", **felder):
    return {"art": "stunde", "von": f"{tag}T{von}:00+01:00", "bis": f"{tag}T{bis}:00+01:00", **felder}


def _nacht(kennung, beginn, ende):
    return {"quelle_kennung": kennung, "beginn": beginn + ":00+01:00", "ende": ende + ":00+01:00", "phasen": []}


def test_sieben_tage_auch_ohne_daten():
    w = aw.woche([], [], "2026-11-03")
    assert [t["datum"] for t in w["tage"]] == [
        "2026-10-28", "2026-10-29", "2026-10-30", "2026-10-31", "2026-11-01", "2026-11-02", "2026-11-03"]
    assert [t["wochentag"] for t in w["tage"]] == ["Mi", "Do", "Fr", "Sa", "So", "Mo", "Di"]
    leer = w["tage"][0]
    assert leer == {"datum": "2026-10-28", "wochentag": "Mi", "eintraege": 0, "stimmung": None,
                    "anspannung": None, "gefuehle": [], "schlaf_min": None, "einschlafen": None,
                    "aufwachen": None}
    assert w["schnitt"] == {"stimmung": None, "anspannung": None, "schlaf_min": None}
    assert w["erkenntnisse"] == []


def test_tag_mit_stimmung_gefuehlen_und_nacht():
    stunden = [_stunde("2026-11-03", stimmung=4, anspannung=20, gefuehle=["Freude", "stolz auf jemanden"]),
               _stunde("2026-11-03", "12:00", "13:00", stimmung=2, anspannung=40, gefuehle=["Freude"])]
    naechte = [_nacht("n1", "2026-11-02T23:10", "2026-11-03T06:40")]
    t = aw.woche(stunden, naechte, "2026-11-03")["tage"][-1]
    assert (t["eintraege"], t["stimmung"], t["anspannung"]) == (2, 3.0, 30.0)
    assert t["gefuehle"] == ["Freude"]   # nur Grundgefühle, kein eigenes Wort
    assert (t["schlaf_min"], t["einschlafen"], t["aufwachen"]) == (450, "23:10", "06:40")


def test_doppelte_und_unterbrochene_naechte_und_nickerchen():
    naechte = [
        _nacht("uhr", "2026-11-02T23:00", "2026-11-03T03:00"),
        _nacht("uhr-2", "2026-11-03T03:30", "2026-11-03T07:00"),
        _nacht("andere-app", "2026-11-02T23:05", "2026-11-03T02:55"),   # dieselbe Nacht, kürzer
        _nacht("nickerchen", "2026-11-03T14:00", "2026-11-03T14:30"),
    ]
    t = aw.woche([], naechte, "2026-11-03")["tage"][-1]
    assert t["schlaf_min"] == 240 + 210
    assert (t["einschlafen"], t["aufwachen"]) == ("23:00", "07:00")


def test_schnitt_ueber_die_tage_mit_werten():
    stunden = [_stunde("2026-11-01", stimmung=2, anspannung=60), _stunde("2026-11-03", stimmung=4, anspannung=20)]
    naechte = [_nacht("a", "2026-10-31T23:00", "2026-11-01T06:00"), _nacht("b", "2026-11-02T23:00", "2026-11-03T08:00")]
    assert aw.woche(stunden, naechte, "2026-11-03")["schnitt"] == {"stimmung": 3.0, "anspannung": 40.0, "schlaf_min": 480}


def test_kein_freitext_in_der_woche():
    stunden = [_stunde("2026-11-03", stimmung=3, aktivitaet="Geheime Tätigkeit", originalworte="Geheimer Satz",
                       gefuehle=["Trauer", "Sehnsucht nach Erfunden"])]
    text = repr(aw.woche(stunden, [], "2026-11-03"))
    assert "Geheim" not in text and "Erfunden" not in text and "Sehnsucht" not in text


def test_erkenntnisse_ab_genug_tagen():
    stunden, naechte = [], []
    for i, (schlaf_h, stimmung) in enumerate([(5, 2), (6, 2), (8, 4), (9, 5)]):
        tag = f"2026-11-0{i + 1}"
        stunden.append(_stunde(tag, stimmung=stimmung, anspannung=50 - 10 * i))
        naechte.append(_nacht(f"n{i}", f"{tag}T00:00", f"{tag}T0{schlaf_h}:00"))
    w = aw.woche(stunden, naechte, "2026-11-04")
    assert w["erkenntnisse"] and all(isinstance(z, str) and z for z in w["erkenntnisse"])
    assert any("kein Beweis" in z for z in w["erkenntnisse"])


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ALLTAGSPROTOKOLL_PFAD", str(tmp_path / "eintraege.jsonl"))
    app = FastAPI()
    app.include_router(alltag.router)
    return TestClient(app)


def test_router_woche(client):
    assert alltag_speicher.eintrag_anhaengen(_stunde("2026-11-03", stimmung=5))["ok"]
    alltag_speicher.schlafnaechte_uebernehmen([_nacht("hc-1", "2026-11-02T23:00", "2026-11-03T06:30")])
    daten = client.get("/api/alltag/woche", params={"bis": "2026-11-03"}).json()
    assert daten["ok"] and daten["bis"] == "2026-11-03" and len(daten["tage"]) == 7
    assert daten["tage"][-1]["stimmung"] == 5.0 and daten["tage"][-1]["schlaf_min"] == 450


def test_router_woche_standard_heute(client):
    daten = client.get("/api/alltag/woche").json()
    assert daten["ok"] and len(daten["tage"]) == 7


def test_router_woche_kaputtes_datum(client):
    assert client.get("/api/alltag/woche", params={"bis": "3.11."}).status_code == 400
