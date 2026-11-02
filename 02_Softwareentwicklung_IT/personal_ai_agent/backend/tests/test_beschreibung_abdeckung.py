"""Tests G2: Zählwerkzeug ``tools/foto_sortierung/beschreibung_abdeckung.py`` (02.11.2026).

Plan: ``.hermes/plans/2026-11-02_geschichte-sprachmodell.md``, Schritt G2 Punkt 1,
Prüfkriterium (h): das Werkzeug gibt keine fileid und keinen Beschreibungstext aus.

Nur erfundene Daten in ``tmp_path`` (Pfade über ``ERZAEHL_*_PFAD``); das Werkzeug wird
NIE gegen echte Daten ausgeführt.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_beschreibung_abdeckung.py -q
"""
from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJEKT = os.path.dirname(BACKEND)
sys.path.insert(0, BACKEND)

from app.services import erzaehl_service as es  # noqa: E402


def _laden():
    pfad = os.path.join(PROJEKT, "tools", "foto_sortierung", "beschreibung_abdeckung.py")
    spez = importlib.util.spec_from_file_location("beschreibung_abdeckung", pfad)
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


FID_A, FID_B, FID_C, FID_D = 987601, 987602, 987603, 987604
GEHEIM = "Geheimtext Sonnenuntergang"


def _jsonl(pfad, zeilen):
    with open(pfad, "w", encoding="utf-8") as datei:
        for z in zeilen:
            datei.write((z if isinstance(z, str) else json.dumps(z, ensure_ascii=False)) + "\n")


@pytest.fixture
def daten(tmp_path, monkeypatch):
    monkeypatch.setenv("ERZAEHL_EREIGNISSE_PFAD", str(tmp_path / "ereignisse.jsonl"))
    monkeypatch.setenv("ERZAEHL_GESCHICHTEN_PFAD", str(tmp_path / "geschichten.jsonl"))
    monkeypatch.delenv("ERZAEHL_FOTOBUCH_PFAD", raising=False)
    es._BILDINFO_SPEICHER.clear()
    # Ereignisse: zwei Anlässe, drei Dateien (A, B, C); B hat keine Beschreibung
    _jsonl(tmp_path / "ereignisse.jsonl", [
        {"kennung": "E-1", "event": "Test", "datei_kennungen": [FID_A, FID_B]},
        {"kennung": "E-2", "event": "Test 2", "datei_kennungen": [FID_C]},
    ])
    # Fotobuch: eine Seite mit C und D (D unbeschrieben), eine Seite mit nur D
    _jsonl(tmp_path / "fotobuch_ereignisse.jsonl", [
        {"kennung": "FB-1", "titel": "Seite 1", "datei_kennungen": [FID_C, FID_D]},
        {"kennung": "FB-2", "titel": "Seite 2", "datei_kennungen": [FID_D]},
        "kaputt",
    ])
    _jsonl(tmp_path / "bild_beschreibungen.jsonl", [
        {"fileid": FID_A, "beschreibung": GEHEIM + " eins"},
        {"fileid": FID_A, "beschreibung": GEHEIM + " zwei", "quelle": "hand"},
    ])
    _jsonl(tmp_path / "bild_beschreibungen_reich.jsonl", [
        {"fileid": FID_C, "beschreibung_reich": GEHEIM + " drei"},
        {"fileid": 111, "beschreibung_reich": GEHEIM + " fremdes Bild"},
    ])
    return tmp_path


def test_zaehlen_liefert_die_erwarteten_zahlen(daten):
    ergebnis = _laden().zaehlen()
    quellen = {q["name"]: q for q in ergebnis["quellen"]}
    assert quellen["bild_beschreibungen.jsonl"]["zeilen"] == 2
    assert quellen["bild_beschreibungen_reich.jsonl"]["zeilen"] == 2
    assert ergebnis["bilder_mit_beschreibung"] == 3          # A, C, 111
    assert ergebnis["herkunft"] == {"ki": 2, "hand": 1, "einzel_ki": 0}
    fb = ergebnis["fotobuch"]
    assert fb["seiten"] == 2 and fb["fileids"] == 2 and fb["mit_beschreibung"] == 1   # C ja, D nein
    ev = ergebnis["ereignisse"]
    assert ev["seiten"] == 2 and ev["fileids"] == 3 and ev["mit_beschreibung"] == 2   # A, C ja; B nein


def test_sqlite_quelle_wird_gezaehlt(daten):
    with sqlite3.connect(daten / "life_archive.db") as conn:
        conn.execute("CREATE TABLE photos (fileid INTEGER PRIMARY KEY, beschreibung TEXT, beschreibung_reich TEXT)")
        conn.execute("INSERT INTO photos VALUES (?, ?, NULL)", (FID_B, GEHEIM + " db"))
        conn.execute("INSERT INTO photos VALUES (?, '', NULL)", (FID_D,))
    ergebnis = _laden().zaehlen()
    db = {q["name"]: q for q in ergebnis["quellen"]}["life_archive.db"]
    assert db["zeilen"] == 2 and db["mit_text"] == 1
    assert ergebnis["bilder_mit_beschreibung"] == 4
    assert ergebnis["ereignisse"]["mit_beschreibung"] == 3        # B kommt dazu


def test_fehlende_dateien_ergeben_nullen_statt_fehler(tmp_path, monkeypatch):
    monkeypatch.setenv("ERZAEHL_EREIGNISSE_PFAD", str(tmp_path / "gibt_es_nicht.jsonl"))
    monkeypatch.delenv("ERZAEHL_FOTOBUCH_PFAD", raising=False)
    es._BILDINFO_SPEICHER.clear()
    ergebnis = _laden().zaehlen()
    assert ergebnis["quellen"] == []
    assert ergebnis["bilder_mit_beschreibung"] == 0
    assert ergebnis["fotobuch"] == {"seiten": 0, "fileids": 0, "mit_beschreibung": 0}
    assert ergebnis["ereignisse"] == {"seiten": 0, "fileids": 0, "mit_beschreibung": 0}


def test_h_ausgabe_enthaelt_keine_fileid_und_keinen_text(daten, capsys):
    modul = _laden()
    assert modul.main([]) == 0
    ausgabe = capsys.readouterr().out
    assert ausgabe.strip()
    for verboten in (str(FID_A), str(FID_B), str(FID_C), str(FID_D), "987", "111", "Geheimtext",
                     "Sonnenuntergang", "Test 2", "Seite 1", "E-1", "FB-1"):
        assert verboten not in ausgabe, verboten
    text_zeilen = "\n".join(modul.bericht(modul.zaehlen()))
    assert text_zeilen.strip() and "Geheimtext" not in text_zeilen and str(FID_A) not in text_zeilen


def test_h_bericht_ist_nur_zahlen_und_feste_woerter(daten):
    modul = _laden()
    for zeile in modul.bericht(modul.zaehlen()):
        # Dateinamen der festen Quellen sind erlaubt, sonst nur Wörter ohne Ziffernfolgen > 4 Stellen
        import re
        assert not re.search(r"\d{5,}", zeile), zeile


def test_werkzeug_liest_pfade_ueber_die_dienstfunktionen(daten):
    """Die Pfade kommen aus erzaehl_service (Umgebungsvariablen-Übersteuerung gilt)."""
    quelltext = open(os.path.join(PROJEKT, "tools", "foto_sortierung", "beschreibung_abdeckung.py"),
                     encoding="utf-8").read()
    for name in ("fotobuch_pfad", "ereignisse_pfad", "beschreibungen_alle_pfade", "_beschreibungen_mit_herkunft"):
        assert name in quelltext, name


def test_werkzeug_schreibt_nichts(daten):
    vorher = sorted(os.listdir(daten))
    _laden().zaehlen()
    assert sorted(os.listdir(daten)) == vorher
