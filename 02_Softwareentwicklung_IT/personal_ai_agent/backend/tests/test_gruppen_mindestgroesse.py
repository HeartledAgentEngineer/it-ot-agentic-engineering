"""Mini-Gesichter immer ausblenden (F2, 03.11.2026) — erfundene Daten.

Bisher filterte das Backend Gesichter unter 50 px nur, wenn der Haken „Nur Gesichter
≥ 50 px" mitgeschickt wurde. Wunsch: Haken weg, Filter immer. Dabei darf eine Gruppe,
die nur aus Video-Gesichtern besteht, nicht mehr herausfallen (Befund zu F3): Der
Filter las bisher nur Foto-Beispiele.
"""
from __future__ import annotations

import json
import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.router import gruppen as gruppen_router  # noqa: E402
from app.services import gruppen_quiz as gq  # noqa: E402


def _foto(fid, bbox):
    return {"bild_id": str(fid), "index": 0, "bbox": list(bbox), "breite": 1000, "hoehe": 750,
            "anteil": 0.01, "score": 0.9, "aufnahme": "2022-06-18T11:21:00"}


GRUPPEN = [
    # Groesste Gruppe, aber nur Mini-Gesichter (40 px).
    {"kennung": "Person_3001", "groesse": 90, "bilder": 9, "videos": 0, "zwilling_kandidaten": [],
     "beispiele": [_foto(500, (10, 20, 30, 40))]},
    # Nur Video-Gesichter, gross genug (300x400 * 0.5).
    {"kennung": "Person_3002", "groesse": 60, "bilder": 0, "videos": 1, "zwilling_kandidaten": [],
     "beispiele": []},
    # Normales Foto-Gesicht, 120x150.
    {"kennung": "Person_3003", "groesse": 30, "bilder": 3, "videos": 0, "zwilling_kandidaten": [],
     "beispiele": [_foto(600, (5, 5, 120, 150))]},
]


@pytest.fixture
def basis(tmp_path, monkeypatch):
    monkeypatch.setenv("GRUPPEN_QUIZ_BASIS", str(tmp_path))
    gq._CACHE.clear()
    ordner = tmp_path / gq.UNTERORDNER
    ordner.mkdir()
    (ordner / gq.BEISPIELE_DATEINAME).write_text(json.dumps({"stand": "x", "gruppen": GRUPPEN}),
                                                 encoding="utf-8")
    video = {"bild_id": "21#t=2.0", "video_id": "21", "zeit_s": 2.0, "index": 0,
             "kennung": "Person_3002", "bbox": [100, 200, 300, 400], "anteil": 0.05, "score": 0.9}
    (ordner / gq.ZUORDNUNG_DATEINAME).write_text(json.dumps(video) + "\n", encoding="utf-8")
    yield tmp_path
    gq._CACHE.clear()


def _karte(basis):
    zeile = {"bild_id": "21#t=2.0", "video_id": "21", "zeit_s": 2.0, "standbild_fileid": 9101,
             "breite": 960, "hoehe": 540, "skala": 0.5}
    (basis / gq.UNTERORDNER / gq.VIDEO_STANDBILDER_DATEINAME).write_text(json.dumps(zeile) + "\n",
                                                                       encoding="utf-8")
    gq._CACHE.clear()


@pytest.fixture
def client(basis):
    app = FastAPI()
    app.include_router(gruppen_router.router)
    return TestClient(app)


def test_mindestgroesse_ist_fuenfzig():
    assert gq.MIN_GESICHT_PX == 50


def test_naechste_filtert_ohne_parameter(client):
    g = client.get("/api/gruppen/naechste").json()["gruppe"]
    assert g["kennung"] != "Person_3001"


def test_liste_filtert_ohne_parameter(client):
    kennungen = [g["kennung"] for g in client.get("/api/gruppen/liste?status=offen").json()["gruppen"]]
    assert "Person_3001" not in kennungen and "Person_3003" in kennungen


def test_null_schaltet_den_filter_ab(client):
    assert client.get("/api/gruppen/naechste?min_px=0").json()["gruppe"]["kennung"] == "Person_3001"


def test_video_gruppe_mit_grossem_gesicht_bleibt(basis, client):
    _karte(basis)
    g = client.get("/api/gruppen/naechste").json()["gruppe"]
    assert g["kennung"] == "Person_3002"
    assert g["beispiele"] and g["beispiele"][0]["video"] is True


def test_video_gruppe_ohne_standbild_bleibt_draussen(client):
    # Ohne Standbild-Karte ist das Video-Gesicht nicht darstellbar -> nicht fragen.
    assert client.get("/api/gruppen/naechste").json()["gruppe"]["kennung"] == "Person_3003"
