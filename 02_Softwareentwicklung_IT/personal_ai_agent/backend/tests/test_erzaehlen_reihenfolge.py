"""Anlässe „neueste zuerst" (F1, 03.11.2026) — erfundene Daten.

Sebastian möchte bei den letzten Anlässen beginnen. ``neueste_zuerst`` dreht die
gewohnte (chronologische) Reihenfolge um; Filter und Blättern gelten danach.
"""
from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.router import erzaehlen
from app.services import erzaehl_service


def _jsonl(pfad, zeilen):
    pfad.write_text("\n".join(json.dumps(z, ensure_ascii=False) for z in zeilen) + "\n", encoding="utf-8")


def _drei_anlaesse(tmp_path, monkeypatch):
    ereignisse = tmp_path / "ereignisse.jsonl"
    _jsonl(ereignisse, [
        {"kennung": "E-1", "event": "Früh", "datum": "2015-03-01", "jahr": 2015, "datei_kennungen": [1]},
        {"kennung": "E-2", "event": "Mitte", "datum": "2017-03-01", "jahr": 2017, "datei_kennungen": [2]},
        {"kennung": "E-3", "event": "Spät", "datum": "2019-03-01", "jahr": 2019, "datei_kennungen": [3]},
        {"kennung": "E-4", "event": "Auch spät", "datum": "2019-08-01", "jahr": 2019, "datei_kennungen": [4]},
    ])
    monkeypatch.setenv("ERZAEHL_EREIGNISSE_PFAD", str(ereignisse))
    monkeypatch.delenv("ERZAEHL_FOTOBUCH_PFAD", raising=False)
    monkeypatch.delenv("ERZAEHL_ORDNER_EREIGNISSE_PFAD", raising=False)
    monkeypatch.setenv("ERZAEHL_GESCHICHTEN_PFAD", str(tmp_path / "geschichten.jsonl"))


def _kennungen(ergebnis):
    return [e["kennung"] for e in ergebnis["eintraege"]]


def test_standard_bleibt_chronologisch(tmp_path, monkeypatch):
    _drei_anlaesse(tmp_path, monkeypatch)
    assert _kennungen(erzaehl_service.ereignisse_liste()) == ["E-1", "E-2", "E-3", "E-4"]


def test_neueste_zuerst_dreht_die_reihenfolge(tmp_path, monkeypatch):
    _drei_anlaesse(tmp_path, monkeypatch)
    assert _kennungen(erzaehl_service.ereignisse_liste(neueste_zuerst=True)) == ["E-4", "E-3", "E-2", "E-1"]


def test_neueste_zuerst_mit_jahr_und_blaettern(tmp_path, monkeypatch):
    _drei_anlaesse(tmp_path, monkeypatch)
    erg = erzaehl_service.ereignisse_liste(jahr=2019, neueste_zuerst=True)
    assert _kennungen(erg) == ["E-4", "E-3"] and erg["gesamt"] == 2
    seite2 = erzaehl_service.ereignisse_liste(neueste_zuerst=True, limit=2, offset=2)
    assert _kennungen(seite2) == ["E-2", "E-1"]


def test_router_reicht_neueste_zuerst_durch(tmp_path, monkeypatch):
    _drei_anlaesse(tmp_path, monkeypatch)
    app = FastAPI()
    app.include_router(erzaehlen.router)
    antwort = TestClient(app).get("/api/erzaehlen/ereignisse?neueste_zuerst=true&limit=2").json()
    assert antwort["ok"] is True
    assert [e["kennung"] for e in antwort["eintraege"]] == ["E-4", "E-3"]
    assert antwort["gesamt"] == 4
