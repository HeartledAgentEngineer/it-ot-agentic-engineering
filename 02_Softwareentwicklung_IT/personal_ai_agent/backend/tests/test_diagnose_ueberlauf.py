"""Tests: Ueberlauf-Messwerte ablegen (app/router/diagnose.py, 01.10.2026)."""
from __future__ import annotations

import json
import os
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.router import diagnose  # noqa: E402


def _client():
    app = FastAPI()
    app.include_router(diagnose.router)
    return TestClient(app)


MESSUNG = {"phase": "fertig", "fenster": 375, "skala": 1, "seite_scroll": 412,
           "blase_rechts": 398.4, "inhalt_scroll": 380, "inhalt_breite": 309,
           "taeter": [{"tag": "table", "klasse": "md-tabelle <script>", "rechts": 520,
                       "breite": 480, "ws": "nowrap", "display": "table"}]}


def test_messung_landet_als_zeile_ohne_gefaehrliche_zeichen(tmp_path, monkeypatch):
    monkeypatch.setenv("DIAG_ORDNER", str(tmp_path))
    r = _client().post("/api/diagnose/ueberlauf", json=MESSUNG)
    assert r.status_code == 200 and r.json() == {"ok": True}
    zeilen = (tmp_path / diagnose.DATEINAME).read_text(encoding="utf-8").splitlines()
    z = json.loads(zeilen[0])
    assert z["phase"] == "fertig" and z["blase_rechts"] == 398.4 and z["seite_scroll"] == 412
    assert z["taeter"][0]["klasse"] == "md-tabelle script"      # < > entfernt
    assert "zeit" in z


def test_zu_viele_oder_zu_lange_felder_werden_abgelehnt(tmp_path, monkeypatch):
    monkeypatch.setenv("DIAG_ORDNER", str(tmp_path))
    c = _client()
    zu_viele = dict(MESSUNG, taeter=MESSUNG["taeter"] * 9)
    assert c.post("/api/diagnose/ueberlauf", json=zu_viele).status_code == 422
    assert c.post("/api/diagnose/ueberlauf", json=dict(MESSUNG, phase="x" * 21)).status_code == 422
    assert not (tmp_path / diagnose.DATEINAME).exists()


def test_grosse_datei_wird_auf_die_letzten_zeilen_gekuerzt(tmp_path, monkeypatch):
    monkeypatch.setenv("DIAG_ORDNER", str(tmp_path))
    monkeypatch.setattr(diagnose, "MAX_BYTES", 1000)
    pfad = tmp_path / diagnose.DATEINAME
    pfad.write_text("".join(json.dumps({"n": i}) + "\n" for i in range(500)), encoding="utf-8")
    _client().post("/api/diagnose/ueberlauf", json=MESSUNG)
    zeilen = pfad.read_text(encoding="utf-8").splitlines()
    assert len(zeilen) == diagnose.BEHALTEN + 1 and json.loads(zeilen[0]) == {"n": 300}


def test_route_im_backend_mit_schluessel_geschuetzt():
    quelle = open(os.path.join(BACKEND, "app", "main.py"), encoding="utf-8").read()
    assert "app.include_router(diagnose.router, dependencies=[Depends(auth.require_api_key)])" in quelle
