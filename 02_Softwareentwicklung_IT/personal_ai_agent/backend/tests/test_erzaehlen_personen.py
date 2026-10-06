"""Tests: Wer ist auf den Bildern eines Ereignisses? (Erzählen, 06.10.2026)

``gruppen_quiz.personen_auf_bildern`` + Route
``GET /api/erzaehlen/ereignisse/{kennung}/personen``. Offline, erfundene Daten in
``tmp_path`` — keine echten Namen, keine Gesichtsdaten.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_erzaehlen_personen.py -q
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.services import gruppen_quiz as gq  # noqa: E402

EREIGNIS = {"kennung": "E-t1", "anlass_id": "t1", "anzahl_dateien": 5, "art": "anlass",
            "datei_kennungen": [101, 102, 103, 104, 9], "event": "Testausflug", "jahr": 2021}

ZUORDNUNG = [
    {"bild_id": "101", "index": 0, "kennung": "Person_1001"},
    {"bild_id": "101", "index": 1, "kennung": "Person_1005"},     # zweiter Vorschlag, gleicher Name
    {"bild_id": "101", "index": 2, "kennung": "Person_1002"},     # noch ohne Namen
    {"bild_id": "102", "index": 0, "kennung": "Person_1003"},
    {"bild_id": "102", "index": 1, "kennung": "Person_1004"},     # „kenne ich nicht" (fremde Menge)
    {"bild_id": "103", "index": 0, "kennung": "Person_1001"},     # ausgeschlossen -> zaehlt nicht
    {"bild_id": "103", "index": 1, "kennung": None},              # Rauschen
    {"bild_id": "9#t=2", "video_id": "9", "kennung": "Person_1003"},
    {"bild_id": "555", "index": 0, "kennung": "Person_1001"},     # gehoert nicht zum Ereignis
]


def _schreibe(pfad, inhalt):
    pfad.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(inhalt, list):
        pfad.write_text("\n".join(json.dumps(z) for z in inhalt) + "\nkaputt\n", encoding="utf-8")
    else:
        pfad.write_text(json.dumps(inhalt), encoding="utf-8")


@pytest.fixture
def basis(tmp_path, monkeypatch):
    monkeypatch.setenv("GRUPPEN_QUIZ_BASIS", str(tmp_path))
    gq._CACHE.clear()
    _schreibe(tmp_path / gq.UNTERORDNER / gq.ZUORDNUNG_DATEINAME, ZUORDNUNG)
    _schreibe(tmp_path / gq.BESTAETIGT_DATEINAME,
              {"bestaetigt": {"Person_1001": "Testperson A", "Person_1005": "testperson a",
                              "Person_1003": "Testperson B"}})
    _schreibe(tmp_path / gq.STAND_DATEINAME, {"spaeter": ["Person_1002"], "unbekannt": ["Person_1004"]})
    _schreibe(tmp_path / gq.VORGABEN_DATEINAME,
              {"gleich": [], "verschieden": [],
               "ausgeschlossen": [{"kennung": "Person_1001", "bild_id": "103", "index": 0}]})
    yield tmp_path
    gq._CACHE.clear()


def _pruefsummen(ordner):
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(ordner.rglob("*")) if p.is_file()}


# ── Dienst ───────────────────────────────────────────────────────────────────

def test_namen_und_unbenannte_je_bild(basis):
    r = gq.personen_auf_bildern([101, 102, 103, 104, 9])
    assert r["ok"] is True and r["gesamt"] == 5
    # Zwei Vorschlaege mit demselben Namen zaehlen einmal; „spaeter" bleibt ohne Namen.
    assert r["bilder"]["101"] == {"namen": ["Testperson A"], "ohne_namen": ["Person_1002"]}
    # „kenne ich nicht" (fremde Menge) zaehlt nicht mit.
    assert r["bilder"]["102"] == {"namen": ["Testperson B"], "ohne_namen": []}
    # Ausgeschlossenes Gesicht fehlt; Rauschen auch -> Bild ohne Personen faellt weg.
    assert "103" not in r["bilder"] and "104" not in r["bilder"]
    # Videos laufen ueber ihre Video-Kennung.
    assert r["bilder"]["9"]["namen"] == ["Testperson B"]
    assert r["mit_personen"] == 3


def test_zusammenfassung_haeufigste_zuerst(basis):
    r = gq.personen_auf_bildern(["101", "102", "9"])
    assert r["benannt"] == [{"name": "Testperson B", "bilder": 2}, {"name": "Testperson A", "bilder": 1}]
    assert r["ohne_namen"] == {"personen": 1, "bilder": 1}


def test_bild_ausserhalb_der_anfrage_zaehlt_nicht(basis):
    r = gq.personen_auf_bildern([101])
    assert r["benannt"] == [{"name": "Testperson A", "bilder": 1}]     # Bild 555 nicht mitgezaehlt


def test_doppelte_und_kaputte_kennungen(basis):
    r = gq.personen_auf_bildern([101, "101", None, "", " 102 "])
    assert r["gesamt"] == 2 and set(r["bilder"]) == {"101", "102"}
    assert gq.personen_auf_bildern(None) == {"ok": True, "gesamt": 0, "mit_personen": 0, "bilder": {},
                                             "benannt": [], "ohne_namen": {"personen": 0, "bilder": 0}}
    assert gq.personen_auf_bildern("101")["gesamt"] == 0               # keine Liste -> nichts


def test_ohne_zuordnung_ehrlicher_hinweis(tmp_path, monkeypatch):
    monkeypatch.setenv("GRUPPEN_QUIZ_BASIS", str(tmp_path))
    gq._CACHE.clear()
    r = gq.personen_auf_bildern([101])
    assert r["ok"] is False and "personen_gruppieren.py" in r["fehler"]
    assert list(tmp_path.iterdir()) == []                              # nichts angelegt


def test_nur_lesend(basis):
    vorher = _pruefsummen(basis)
    gq.personen_auf_bildern([101, 102, 103, 9])
    assert _pruefsummen(basis) == vorher


def test_kaputte_namensdatei_wirft_nicht(basis):
    (basis / gq.BESTAETIGT_DATEINAME).write_text("{kaputt", encoding="utf-8")
    r = gq.personen_auf_bildern([101])
    assert r["ok"] is False and "nicht lesbar" in r["fehler"]


# ── Route ────────────────────────────────────────────────────────────────────

@pytest.fixture
def client(basis, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.config import settings
    from app.main import app

    ereignisse = tmp_path / "ereignisse.jsonl"
    ereignisse.write_text(json.dumps(EREIGNIS) + "\n", encoding="utf-8")
    monkeypatch.setenv("ERZAEHL_EREIGNISSE_PFAD", str(ereignisse))
    monkeypatch.setenv("ERZAEHL_GESCHICHTEN_PFAD", str(tmp_path / "geschichten.jsonl"))
    monkeypatch.setattr(settings, "api_key", None)
    return TestClient(app)


def test_route_liefert_personen(client):
    r = client.get("/api/erzaehlen/ereignisse/E-t1/personen")
    assert r.status_code == 200
    daten = r.json()
    assert daten["ok"] is True and daten["error"] is None
    assert daten["personen"]["gesamt"] == 5 and daten["personen"]["mit_personen"] == 3
    assert daten["personen"]["benannt"][0] == {"name": "Testperson B", "bilder": 2}


def test_route_unbekanntes_ereignis_200(client):
    r = client.get("/api/erzaehlen/ereignisse/E-gibtsnicht/personen")
    assert r.status_code == 200 and r.json()["ok"] is False and "nicht gefunden" in r.json()["error"]


def test_route_ohne_zuordnung_200(client, basis):
    (basis / gq.UNTERORDNER / gq.ZUORDNUNG_DATEINAME).unlink()
    gq._CACHE.clear()
    r = client.get("/api/erzaehlen/ereignisse/E-t1/personen")
    assert r.status_code == 200 and r.json()["ok"] is False and r.json()["error"]


def test_route_ohne_ereignisdatei_200(client, tmp_path):
    (tmp_path / "ereignisse.jsonl").unlink()
    r = client.get("/api/erzaehlen/ereignisse/E-t1/personen")
    assert r.status_code == 200 and r.json()["ok"] is False and "Ereignisdatei" in r.json()["error"]
