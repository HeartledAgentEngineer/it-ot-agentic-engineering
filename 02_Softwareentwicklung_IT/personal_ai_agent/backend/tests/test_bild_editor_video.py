"""Bild-Editor auf Video-Standbildern (F3, 03.11.2026) — erfundene Daten.

Befund: Auf Ausschnitten aus Videos liessen sich Gesichter weder ändern noch speichern noch
löschen. Ursache: Die Bildsicht (``_bild_sicht``) las nur Foto-Zeilen; ein Video-Gesicht
mit Standbild (gid ``<standbild_fileid>:<index>``) gab es dort nicht, jede Änderung endete in
„Dieses Gesicht gibt es auf dem Bild nicht". Ausschliessen und Zuordnen kannten die gid schon (S2).
"""
from __future__ import annotations

import json
import os
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.services import gruppen_quiz as gq  # noqa: E402


def _gruppe(kennung, groesse=10, videos=0):
    return {"kennung": kennung, "groesse": groesse, "bilder": groesse, "videos": videos,
            "von": None, "bis": None, "zwilling_kandidaten": [], "beispiele": []}


def _vzeile(vid, zeit, kennung, index=0):
    return {"bild_id": f"{vid}#t={zeit:.1f}", "video_id": str(vid), "zeit_s": zeit, "index": index,
            "kennung": kennung, "bbox": [100, 200, 300, 400], "anteil": 0.05, "score": 0.9}


def _foto(fid, index, kennung):
    return {"bild_id": str(fid), "index": index, "kennung": kennung, "bbox": [10, 20, 300, 400],
            "breite": 1000, "hoehe": 800, "anteil": 0.05, "score": 0.9}


@pytest.fixture
def basis(tmp_path, monkeypatch):
    monkeypatch.setenv("GRUPPEN_QUIZ_BASIS", str(tmp_path))
    gq._CACHE.clear()
    ordner = tmp_path / gq.UNTERORDNER
    ordner.mkdir()
    (ordner / gq.BEISPIELE_DATEINAME).write_text(json.dumps({"stand": "x", "gruppen": [
        _gruppe("Person_5001", 20, videos=2), _gruppe("Person_5002", 10)]}), encoding="utf-8")
    zeilen = [_vzeile(31, 2.0, "Person_5001"), _vzeile(31, 2.0, "Person_5002", index=1),
              _foto(700, 0, "Person_5002")]
    (ordner / gq.ZUORDNUNG_DATEINAME).write_text("\n".join(json.dumps(z) for z in zeilen) + "\n",
                                               encoding="utf-8")
    karte = {"bild_id": "31#t=2.0", "video_id": "31", "zeit_s": 2.0, "standbild_fileid": 9201,
             "breite": 960, "hoehe": 540, "skala": 0.5}
    (ordner / gq.VIDEO_STANDBILDER_DATEINAME).write_text(json.dumps(karte) + "\n", encoding="utf-8")
    gq._CACHE.clear()
    yield tmp_path
    gq._CACHE.clear()


def test_standbild_zeigt_seine_video_gesichter(basis):
    r = gq.gesichter_auf_bild("9201")
    assert r["ok"]
    nach_gid = {g["gid"]: g for g in r["gesichter"]}
    assert set(nach_gid) == {"9201:0", "9201:1"}
    g = nach_gid["9201:0"]
    assert g["kennung"] == "Person_5001" and g["bbox"] == [50, 100, 150, 200]
    assert g["breite"] == 960 and g["hoehe"] == 540


def test_name_auf_dem_standbild_speichern(basis):
    r = gq.bild_rahmen("9201", [{"gid": "9201:0", "name": "Testperson Neu"}])
    assert r["ok"] is True, r.get("fehler")
    namen = {g["gid"]: g["name"] for g in gq.gesichter_auf_bild("9201")["gesichter"]}
    assert namen["9201:0"] == "Testperson Neu"


def test_rahmen_auf_dem_standbild_verschieben(basis):
    r = gq.bild_rahmen("9201", [{"gid": "9201:1", "bbox_norm": [0.5, 0.2, 0.2, 0.3]}])
    assert r["ok"] is True, r.get("fehler")
    g = {g["gid"]: g for g in gq.gesichter_auf_bild("9201")["gesichter"]}["9201:1"]
    assert g["bbox_norm"] == [0.5, 0.2, 0.2, 0.3]


def test_gesicht_auf_dem_standbild_loeschen(basis):
    r = gq.bild_rahmen("9201", [{"gid": "9201:0", "entfernen": True}])
    assert r["ok"] is True, r.get("fehler")
    assert "9201:0" not in {g["gid"] for g in gq.gesichter_auf_bild("9201")["gesichter"]}
    # Auch die Quiz-Gesichterliste des Vorschlags zeigt es nicht mehr.
    assert "9201:0" not in {g["gid"] for g in gq.gesichter("Person_5001")["gesichter"]}


def test_fotos_bleiben_wie_bisher(basis):
    r = gq.gesichter_auf_bild("700")
    assert [g["gid"] for g in r["gesichter"]] == ["700:0"]


def test_ohne_standbild_karte_kein_wurf(basis):
    (basis / gq.UNTERORDNER / gq.VIDEO_STANDBILDER_DATEINAME).unlink()
    gq._CACHE.clear()
    r = gq.gesichter_auf_bild("9201")
    assert r["ok"] and r["gesichter"] == []
