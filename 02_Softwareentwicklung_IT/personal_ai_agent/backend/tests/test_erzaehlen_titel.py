"""Tests: eigene Anlass-Titel im Erzählen (06.10.2026).

``erzaehl_service.titel_setzen`` / ``eigene_titel`` + Route
``POST /api/erzaehlen/ereignisse/{kennung}/titel``. Offline, erfundene Anlässe in
``tmp_path``.
"""
from __future__ import annotations

import json

import pytest

from app.services import erzaehl_service as es

EREIGNIS = {"kennung": "E-t1", "anzahl_dateien": 2, "datei_kennungen": [11, 12], "event": "Testband",
            "thema": "Konzert", "jahr": 2022, "datum": "2022-08-21"}
ANDERES = {"kennung": "E-t2", "anzahl_dateien": 1, "datei_kennungen": [21], "event": None,
           "thema": "Park", "jahr": 2021}


@pytest.fixture
def ablage(tmp_path, monkeypatch):
    ereignisse = tmp_path / "ereignisse.jsonl"
    ereignisse.write_text("\n".join(json.dumps(e) for e in (EREIGNIS, ANDERES)) + "\n", encoding="utf-8")
    monkeypatch.setenv("ERZAEHL_EREIGNISSE_PFAD", str(ereignisse))
    monkeypatch.setenv("ERZAEHL_GESCHICHTEN_PFAD", str(tmp_path / "geschichten.jsonl"))
    return tmp_path


def test_ohne_eigenen_titel_gilt_der_automatische(ablage):
    d = es.ereignis_detail("E-t1")
    assert (d["titel"], d["titel_eigen"], d["titel_automatisch"]) == ("Testband", False, "Testband")


def test_eigener_titel_gewinnt_in_liste_und_detail(ablage):
    r = es.titel_setzen("E-t1", "  Testfestival   2022 \n mit Freunden ")
    assert r == {"kennung": "E-t1", "titel": "Testfestival 2022 mit Freunden", "titel_eigen": True,
                 "titel_automatisch": "Testband"}
    assert es.ereignis_detail("E-t1")["titel"] == "Testfestival 2022 mit Freunden"
    eintrag = next(e for e in es.ereignisse_liste()["eintraege"] if e["kennung"] == "E-t1")
    assert eintrag["titel"] == "Testfestival 2022 mit Freunden" and eintrag["titel_eigen"] is True
    assert es.ereignis_detail("E-t2")["titel_eigen"] is False             # andere bleiben


def test_suche_findet_eigenen_und_automatischen_titel(ablage):
    es.titel_setzen("E-t1", "Sommerabend am See")
    finde = lambda s: [e["kennung"] for e in es.ereignisse_liste(suche=s)["eintraege"]]  # noqa: E731
    assert finde("sommerabend") == ["E-t1"]
    assert finde("testband") == ["E-t1"]


def test_nur_anhaengend_neuester_gilt_leer_setzt_zurueck(ablage):
    es.titel_setzen("E-t1", "Erster Name")
    es.titel_setzen("E-t1", "Zweiter Name")
    assert es.eigene_titel() == {"E-t1": "Zweiter Name"}
    r = es.titel_setzen("E-t1", "   ")
    assert r["titel"] == "Testband" and r["titel_eigen"] is False
    with open(es.titel_pfad(), encoding="utf-8") as datei:
        zeilen = [json.loads(z) for z in datei]
    assert [z["name"] for z in zeilen] == ["Erster Name", "Zweiter Name", ""]   # nichts überschrieben
    assert zeilen[1]["vorher"] == "Erster Name"                                  # Rückweg


def test_grenzen(ablage):
    with pytest.raises(es.GeschichteValidierungsfehler, match="existiert nicht"):
        es.titel_setzen("E-gibtsnicht", "x")
    with pytest.raises(es.GeschichteValidierungsfehler, match="zu lang"):
        es.titel_setzen("E-t1", "x" * (es.TITEL_MAX_LAENGE + 1))
    assert not (ablage / es.TITEL_DATEINAME).exists()                            # nichts geschrieben


def test_kaputte_zeilen_werfen_nicht(ablage):
    (ablage / es.TITEL_DATEINAME).write_text('kaputt\n{"kennung": "E-t1", "name": "Gut"}\n[1]\n', encoding="utf-8")
    assert es.eigene_titel() == {"E-t1": "Gut"}


def test_geschichte_merkt_sich_den_gueltigen_titel(ablage):
    es.titel_setzen("E-t1", "Mein Name")
    assert es.geschichte_speichern("E-t1", "Text", "tippen")["ereignis_titel"] == "Mein Name"


def test_route(ablage, monkeypatch):
    from fastapi.testclient import TestClient

    from app.config import settings
    from app.main import app

    monkeypatch.setattr(settings, "api_key", None)
    c = TestClient(app)
    r = c.post("/api/erzaehlen/ereignisse/E-t1/titel", json={"name": "Routen-Name"})
    assert r.status_code == 200 and r.json()["titel"] == "Routen-Name" and r.json()["ok"] is True
    assert c.get("/api/erzaehlen/ereignisse/E-t1").json()["ereignis"]["titel"] == "Routen-Name"
    falsch = c.post("/api/erzaehlen/ereignisse/E-nix/titel", json={"name": "x"})
    assert falsch.status_code == 400 and "existiert nicht" in falsch.json()["detail"]
    zurueck = c.post("/api/erzaehlen/ereignisse/E-t1/titel", json={"name": ""})
    assert zurueck.status_code == 200 and zurueck.json()["titel"] == "Testband"
