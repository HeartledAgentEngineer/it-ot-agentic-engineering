"""Umbenennen erreicht auch die Rahmen des Bild-Editors (F5, 03.11.2026) — erfundene Daten.

Befund: Nach „Name ändern" im Kontaktbuch zeigten Bildersuche und Rahmen weiter den alten
Namen. Ursache: Rahmen-Namen aus ``bild_korrekturen.json`` (Quelle „handy") haben Vorrang
vor dem Gruppennamen, ``umbenennen()`` liess sie aber unverändert. Rückgängig muss sie
genau zurückholen.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.services import gruppen_quiz as gq  # noqa: E402


def _gruppe(kennung, groesse=10):
    return {"kennung": kennung, "groesse": groesse, "bilder": groesse, "videos": 0,
            "von": None, "bis": None, "zwilling_kandidaten": [], "beispiele": []}


def _zeile(bild, index, kennung, bbox):
    return {"bild_id": str(bild), "index": index, "kennung": kennung, "bbox": bbox,
            "breite": 1000, "hoehe": 800, "anteil": 0.05, "score": 0.95}


KORREKTUREN = {"version": 1, "bilder": {
    "111": {"rahmen": {
        "0": {"bbox_norm": [0.1, 0.1, 0.2, 0.2], "name": "Person A"},
        "1": {"bbox_norm": [0.6, 0.1, 0.1, 0.1], "name": "Jemand Anders"},
        "1000": {"bbox_norm": [0.4, 0.4, 0.1, 0.1], "name": "person a", "breite": 1000, "hoehe": 800},
    }},
    # Nur ein Hand-Gesicht, die Erkennung kennt das Bild nicht.
    "222": {"rahmen": {"1000": {"bbox_norm": [0.2, 0.2, 0.2, 0.2], "name": "Person A",
                                "breite": 800, "hoehe": 600}}},
}}


@pytest.fixture
def basis(tmp_path, monkeypatch):
    monkeypatch.setenv("GRUPPEN_QUIZ_BASIS", str(tmp_path))
    gq._CACHE.clear()
    ordner = tmp_path / gq.UNTERORDNER
    ordner.mkdir()
    (ordner / gq.BEISPIELE_DATEINAME).write_text(
        json.dumps({"stand": "x", "gruppen": [_gruppe("Person_4001", 40), _gruppe("Person_4002", 20)]}),
        encoding="utf-8")
    zeilen = [_zeile(111, 0, "Person_4001", [100, 80, 200, 160]),
              _zeile(111, 1, "Person_4002", [600, 80, 100, 100])]
    (ordner / gq.ZUORDNUNG_DATEINAME).write_text("\n".join(json.dumps(z) for z in zeilen) + "\n",
                                               encoding="utf-8")
    gq._CACHE.clear()
    assert gq.antworten("Person_4001", "name", "Person A")["ok"] is not False
    (tmp_path / gq.KORREKTUREN_DATEINAME).write_text(json.dumps(KORREKTUREN), encoding="utf-8")
    gq._CACHE.clear()
    yield tmp_path
    gq._CACHE.clear()


def _rahmen_namen(basis):
    daten = json.loads((basis / gq.KORREKTUREN_DATEINAME).read_text(encoding="utf-8"))
    return {(f, i): r.get("name") for f, e in daten["bilder"].items() for i, r in e["rahmen"].items()}


def test_umbenennen_aendert_die_rahmen_namen(basis):
    assert gq.umbenennen("Person A", "Anna Test")["ok"] is not False
    namen = _rahmen_namen(basis)
    assert namen[("111", "0")] == "Anna Test"
    assert namen[("111", "1000")] == "Anna Test"          # Gross/Klein egal
    assert namen[("222", "1000")] == "Anna Test"
    assert namen[("111", "1")] == "Jemand Anders"          # andere Person unberuehrt


def test_bildersuche_findet_den_neuen_namen(basis):
    gq.umbenennen("Person A", "Anna Test")
    neu = gq.bilder_mit(["Anna Test"])
    assert neu["ok"] and {t["fileid"] for t in neu["treffer"]} == {"111", "222"}
    alt = gq.bilder_mit(["Person A"])
    assert alt["anzahl"] == 0 and alt["unbekannte_namen"] == ["Person A"]


def test_bild_sicht_zeigt_den_neuen_namen(basis):
    gq.umbenennen("Person A", "Anna Test")
    q = gq._sicht_quellen()
    namen = {g["index"]: g["name"] for g in gq._bild_sicht("111", q)}
    assert namen[0] == "Anna Test" and namen[1000] == "Anna Test"


def test_rueckgaengig_holt_die_alten_rahmen_namen(basis):
    vorher = _rahmen_namen(basis)
    gq.umbenennen("Person A", "Anna Test")
    gq.rueckgaengig()
    assert _rahmen_namen(basis) == vorher


def test_ohne_korrekturdatei_bleibt_alles_wie_bisher(basis):
    (basis / gq.KORREKTUREN_DATEINAME).unlink()
    gq._CACHE.clear()
    assert gq.umbenennen("Person A", "Anna Test")["ok"] is not False
    assert not (basis / gq.KORREKTUREN_DATEINAME).exists()
